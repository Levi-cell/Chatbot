"""Extração pura e conservadora de campos explícitos da primeira mensagem."""

import re
import unicodedata
from copy import deepcopy

from core.validacoes.email import validar_email_estrutural
from core.validacoes.nomes_compostos import PRIMEIROS_NOMES_COMPOSTOS
from core.validacoes.apresentacao_nome import extrair_apresentacao_nome
from core.validacoes.preferencia_turno import extrair_preferencia_turno
from core.validacoes.relacoes_destinatario import RELACOES, destinatario_sem_rotulo

CAMPOS = ('nome', 'email', 'destinatario')
EVENTO_NOME_DESTINO_COLETADO = 'nome_cliente_valido_destino_coletado'


def normalizar(valor):
    base = unicodedata.normalize('NFKD', str(valor or '').casefold())
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', ''.join(
        c for c in base if not unicodedata.combining(c))).split())


def nome(valor):
    # Um título profissional/sufixo não invalida o nome explícito do titular.
    original = str(valor or '').strip()
    palavras = re.findall(r"[^\W\d_]+(?:[-'][^\W\d_]+)*", original.split('|', 1)[0], re.UNICODE)
    if not palavras or normalizar(palavras[0]) in {'ola', 'oi', 'nome', 'teste', 'email', 'nao'}:
        return None
    primeiro = palavras[0]
    composto = ' '.join(palavras[:2])
    if tuple(normalizar(composto).split()) in PRIMEIROS_NOMES_COMPOSTOS:
        primeiro = composto
    return primeiro.title()


def email(valor):
    validacao = validar_email_estrutural(valor)
    return validacao.email if validacao.valido else None


def destinatario(valor):
    chave = normalizar(valor)
    if chave in {'para mim', 'mim', 'titular', 'para o titular', 'eu', 'para voce'}:
        return {'dependente': False, 'chave': 'titular', 'texto': str(valor).strip()}
    palavras = set(chave.split())
    parentes_presentes = sorted(palavras & RELACOES)
    if parentes_presentes or 'dependente' in palavras or any(t in chave for t in ('outra pessoa', 'outras pessoas')):
        # Guardar a relação específica para priorizá-la na seleção do dashboard.
        identidade = '+'.join(parentes_presentes) if parentes_presentes else 'dependente'
        if 'mim' in palavras:
            identidade = 'titular+' + identidade
        return {'dependente': True, 'chave': identidade, 'texto': str(valor).strip()}
    return None  # Faixa etária não define para quem é o atendimento.


def campo(valores, tipo, fonte='mensagem'):
    candidatos = list(dict.fromkeys(str(v).strip() for v in valores if str(v).strip()))
    extrair = {'nome': nome, 'email': email, 'destinatario': destinatario,
               'turno': extrair_preferencia_turno}[tipo]
    validos = {}
    for bruto in candidatos:
        valor = extrair(bruto)
        if valor is None:
            continue
        chave = valor['chave'] if tipo == 'destinatario' else (
            normalizar(bruto.split('|', 1)[0]) if tipo == 'nome' else valor.casefold())
        validos.setdefault(chave, (valor, bruto))
    status = 'ausente' if not candidatos else 'invalido'
    resultado = {'status': status, 'valor': None, 'candidatos': candidatos, 'fonte': fonte}
    if len(validos) > 1:
        resultado['status'] = 'conflitante'
    elif len(validos) == 1:
        chave, (valor, bruto) = next(iter(validos.items()))
        resultado.update(status='aceito', valor=valor, identidade=chave, bruto=bruto)
    return resultado


def extrair(texto, *, coletar_turno=False):
    texto = str(texto or '')
    valores = {c: [] for c in CAMPOS}
    if coletar_turno:
        valores['turno'] = []
    # E-mails diferentes nunca são resolvidos escolhendo a primeira ocorrência.
    valores['email'] = re.findall(r'[^\s@:,;<>]+@[^\s@,;<>]+', texto)
    for linha in texto.splitlines():
        if ':' in linha:
            rotulo, valor = linha.split(':', 1)
            rotulo = normalizar(rotulo)
            if rotulo in {'nome', 'nome completo', 'full name', 'nome do titular', 'seu nome', 'qual seu nome', 'qual e seu nome'}:
                valores['nome'].append(valor)
            elif rotulo.startswith('para quem') or rotulo in {
                'destinatario', 'atendimento para', 'treino para', 'quem vai fazer',
                'quem vai fazer o treino', 'quem vai fazer o curso', 'quem vai fazer o atendimento',
            }:
                valores['destinatario'].append(valor)
            elif rotulo in {'email', 'e mail', 'seu email', 'seu e mail'} and not valor.strip().count('@'):
                valores['email'].append(valor)
            elif coletar_turno and rotulo in {'turno', 'periodo', 'melhor periodo',
                                             'periodo preferido', 'turno preferido',
                                             'turno de preferencia', 'qual turno voce prefere'}:
                valores['turno'].append(valor)
        apresentacao = extrair_apresentacao_nome(linha)
        if apresentacao:
            valores['nome'].append(apresentacao)
        if coletar_turno and ':' not in linha:
            # Exige escolha explícita fora de um campo; 'boa tarde' não é turno.
            for frase in re.split(r'[.!;\n]+', linha):
                if re.match(r'^\s*(?:(?:eu|so|só)\s+)*(?:prefiro|posso|escolho|minha prefer)', frase, re.I):
                    valores['turno'].append(frase)
        if ':' not in linha and '?' not in linha and destinatario_sem_rotulo(normalizar(linha)):
            if destinatario(linha):
                valores['destinatario'].append(linha)
    return {c: campo(valores[c], c) for c in valores}


def aceito(estado, tipo):
    return (estado.get('campos', {}).get(tipo) or {}).get('status') == 'aceito'


def valor(estado, tipo):
    return estado['campos'][tipo]['valor'] if aceito(estado, tipo) else None


def etapa_inicial(estado):
    return 1 if not aceito(estado, 'nome') else (2 if not aceito(estado, 'destinatario') else 4)


def completo(estado):
    campos = CAMPOS + (('turno',) if estado.get('coletar_turno') else ())
    return all(aceito(estado, c) for c in campos)


def validar_contexto(contexto):
    estado = contexto.get('contexto_coleta')
    if not estado:
        return None
    if (estado.get('versao') != 1 or estado.get('id_conversa') != contexto.get('id_conversa')
            or estado.get('status') != 'pronto'):
        raise ValueError('Contexto de coleta não está pronto para esta conversa')
    return estado


def destinatario_coletado(contexto):
    estado = validar_contexto(contexto)
    return bool(estado and aceito(estado, 'destinatario'))


def email_coletado(contexto):
    estado = validar_contexto(contexto)
    return bool(estado and aceito(estado, 'email'))


def criar_contexto(id_conversa, mensagem, *, coletar_turno=False):
    campos = extrair(mensagem.get('conteudo_texto') if mensagem.get('tipo_mensagem') == 'text' else '',
                    coletar_turno=coletar_turno)
    return {'versao': 1, 'id_conversa': id_conversa, 'id_mensagem': mensagem['id_mensagem'],
            'id_hash': mensagem['id_hash'], 'status': 'preparando', 'campos': campos,
            'mensagem_original': deepcopy(campos), 'formulario_identificado': False,
            'coletar_turno': coletar_turno,
            'rota_formulario_chat': bool(re.search(
                r'(?im)^\s*(?:full name|nome(?: completo| do titular)?|para quem[^:\n]*|'
                r'quem vai fazer(?: o (?:treino|curso|atendimento))?|e-?mail)\s*[?:]',
                str(mensagem.get('conteudo_texto') or '')))}
