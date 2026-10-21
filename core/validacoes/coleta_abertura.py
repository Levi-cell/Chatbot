"""Extração pura e conservadora de campos explícitos da primeira mensagem."""

import re
import unicodedata
from copy import deepcopy

from core.validacoes.email import validar_email_estrutural
from core.validacoes.nomes_compostos import PRIMEIROS_NOMES_COMPOSTOS

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
    parentes = {'pai', 'mae', 'avo', 'avos', 'filho', 'filha', 'filhos', 'neto', 'neta',
                'irmao', 'irma', 'tio', 'tia', 'sobrinho', 'sobrinha', 'marido', 'esposa',
                'companheiro', 'companheira', 'sogro', 'sogra', 'primo', 'prima', 'enteado', 'enteada'}
    palavras = set(chave.split())
    parentes_presentes = sorted(palavras & parentes)
    if parentes_presentes or any(t in chave for t in ('outra pessoa', 'dependente', 'outras pessoas')):
        # Guardar o parentesco: mãe e filho não são a mesma inscrição no dashboard.
        identidade = '+'.join(parentes_presentes) if parentes_presentes else 'dependente'
        if 'mim' in palavras:
            identidade = 'titular+' + identidade
        return {'dependente': True, 'chave': identidade, 'texto': str(valor).strip()}
    return None  # Faixa etária não define para quem é o atendimento.


def campo(valores, tipo, fonte='mensagem'):
    candidatos = list(dict.fromkeys(str(v).strip() for v in valores if str(v).strip()))
    extrair = {'nome': nome, 'email': email, 'destinatario': destinatario}[tipo]
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


def extrair(texto):
    texto = str(texto or '')
    valores = {c: [] for c in CAMPOS}
    # E-mails diferentes nunca são resolvidos escolhendo a primeira ocorrência.
    valores['email'] = re.findall(r'[^\s@:,;<>]+@[^\s@,;<>]+', texto)
    for linha in texto.splitlines():
        if ':' in linha:
            rotulo, valor = linha.split(':', 1)
            rotulo = normalizar(rotulo)
            if rotulo in {'nome', 'nome completo', 'full name', 'nome do titular', 'seu nome', 'qual seu nome', 'qual e seu nome'}:
                valores['nome'].append(valor)
            elif rotulo.startswith('para quem') or rotulo in {'destinatario', 'atendimento para', 'treino para'}:
                valores['destinatario'].append(valor)
            elif rotulo in {'email', 'e mail', 'seu email', 'seu e mail'} and not valor.strip().count('@'):
                valores['email'].append(valor)
        apresentacao = re.match(r'^\s*(?:me chamo|meu nome é)\s+([^\n,.!?]+)', linha, re.I)
        if apresentacao:
            valores['nome'].append(apresentacao.group(1))
        if normalizar(linha).startswith('para ') and ':' not in linha:
            if destinatario(linha):
                valores['destinatario'].append(linha)
    return {c: campo(valores[c], c) for c in CAMPOS}


def aceito(estado, tipo):
    return (estado.get('campos', {}).get(tipo) or {}).get('status') == 'aceito'


def valor(estado, tipo):
    return estado['campos'][tipo]['valor'] if aceito(estado, tipo) else None


def etapa_inicial(estado):
    return 1 if not aceito(estado, 'nome') else (2 if not aceito(estado, 'destinatario') else 4)


def completo(estado):
    return all(aceito(estado, c) for c in CAMPOS)


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


def criar_contexto(id_conversa, mensagem):
    campos = extrair(mensagem.get('conteudo_texto') if mensagem.get('tipo_mensagem') == 'text' else '')
    return {'versao': 1, 'id_conversa': id_conversa, 'id_mensagem': mensagem['id_mensagem'],
            'id_hash': mensagem['id_hash'], 'status': 'preparando', 'campos': campos,
            'mensagem_original': deepcopy(campos), 'formulario_identificado': False,
            'rota_formulario_chat': bool(re.search(r'(?im)^\s*(?:full name|nome(?: completo| do titular)?|para quem[^:\n]*|e-?mail)\s*[?:]', str(mensagem.get('conteudo_texto') or '')))}
