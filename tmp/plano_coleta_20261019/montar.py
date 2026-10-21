from pathlib import Path
import json
import textwrap
import re
import shutil

ROOT = Path(__file__).parent / 'candidate'
CHANGES = []
BASE = Path(__file__).resolve().parents[2]
for path in set(re.findall(r"edit\('([^']+)'", Path(__file__).read_text(encoding='utf-8'))):
    shutil.copy2(BASE / path, ROOT / path)

def put(path, source):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(source).lstrip('\n'), encoding='utf-8', newline='\n')
    if path not in CHANGES:
        CHANGES.append(path)

def edit(path, old, new, count=1):
    source = (ROOT / path).read_text(encoding='utf-8')
    assert source.count(old) == count, (path, source.count(old), old[:100])
    put(path, source.replace(old, new))

put('core/validacoes/coleta_abertura.py', r'''
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
''')

put('core/integrations/fireads/coleta_abertura.py', r'''
"""Completa campos a partir de uma única inscrição compatível da aba geral."""

from copy import deepcopy
from core.validacoes.coleta_abertura import CAMPOS, campo, aceito, completo, normalizar
from core.integrations.fireads.aba_geral import ORIGENS, mais_recente, referencia_registro
from core.integrations.fireads.contrato import localizar
from core.integrations.fireads.extratores import extrair_nome, extrair_email

COLUNAS = {'nome': 'Nome', 'email': 'Email', 'destinatario': 'Para quem é'}


def campos_registro(row):
    campos = {c: campo([row.get(coluna) or ''], c, 'dashboard') for c, coluna in COLUNAS.items()}
    # Campos estruturados preservam os extratores FireAds existentes. A validação
    # de texto livre do WhatsApp não é imposta novamente ao formulário externo.
    for tipo, extrator in (('nome', extrair_nome), ('email', extrair_email)):
        bruto = str(row.get(COLUNAS[tipo]) or '').strip()
        valor = extrator(bruto)
        if valor:
            identidade = normalizar(bruto.split('|', 1)[0]) if tipo == 'nome' else valor.casefold()
            campos[tipo].update(status='aceito', valor=valor, identidade=identidade, bruto=bruto)
    return campos


def compativel(conhecidos, candidatos, *, campos=CAMPOS):
    for c in campos:
        a, b = conhecidos[c], candidatos[c]
        if a['status'] != 'aceito':
            continue
        if b['status'] != 'aceito':
            return False
        if c == 'nome':
            # Mesmo nome extraído, mas sobrenomes explícitos divergentes bloqueiam.
            ca, cb = a['identidade'].split(), b['identidade'].split()
            if ca != cb and not (len(ca) == 1 and ca[0] == cb[0]):
                return False
        elif c == 'destinatario' and a['identidade'] == 'dependente' and b['valor']['dependente']:
            continue
        elif a['identidade'] != b['identidade']:
            return False
    return True


def interpretar_parcial(rows, numero, fuso, aba, estado):
    resultado = deepcopy(estado)
    encontrados = localizar(rows, numero, 'WhatsApp', incluir_equivalentes=True)
    candidatos = [r for r in encontrados if normalizar(r.get('Canal')) in ORIGENS
                  and compativel(estado['campos'], campos_registro(r))]
    row = mais_recente(candidatos, fuso)
    if row is not None:
        for c, recebido in campos_registro(row).items():
            if not aceito(resultado, c) and recebido['status'] == 'aceito':
                resultado['campos'][c] = recebido
        resultado['formulario_identificado'] = True
    return {'resultado': 'importado' if completo(resultado) else ('incompleto' if row else 'ausente'),
            'origem': ORIGENS[normalizar(row.get('Canal'))] if row else (
                'meta' if estado['rota_formulario_chat'] else 'organico'),
            'referencia': referencia_registro(row, aba, fuso), 'coleta': resultado,
            'motivo': None if row else 'sem_registro_compativel', 'dados_titular': {}}
''')

put('core/repositories/atendimento/coleta_abertura.py', r'''
"""Persistência da coleta na transação já protegida pelo lock da conversa."""

from copy import deepcopy
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from core.repositories.atendimento.dependentes import inserir_dependente_para_conversa
from core.validacoes.coleta_abertura import aceito, valor, campo, etapa_inicial


def salvar(id_conversa, estado, cursor):
    cursor.execute('UPDATE chatbot.conversa SET contexto_coleta=%s WHERE id_conversa=%s',
                   (Jsonb(estado), id_conversa))
    if cursor.rowcount != 1:
        raise ValueError('Conversa ausente ao salvar coleta')


def importar(abertura, id_conversa, estado, cursor):
    estado = deepcopy(estado)
    if aceito(estado, 'nome'):
        cursor.execute('UPDATE chatbot.cliente SET nome=%s WHERE id_cliente=%s',
                       (valor(estado, 'nome'), abertura['id_cliente']))
    if aceito(estado, 'email'):
        cursor.execute('SAVEPOINT coleta_email')
        try:
            cursor.execute('UPDATE chatbot.cliente SET email=%s WHERE id_cliente=%s',
                           (valor(estado, 'email'), abertura['id_cliente']))
        except UniqueViolation:
            cursor.execute('ROLLBACK TO SAVEPOINT coleta_email')
            estado['campos']['email'].update(status='conflitante', valor=None, motivo='email_em_outro_cliente')
        finally:
            cursor.execute('RELEASE SAVEPOINT coleta_email')
    if aceito(estado, 'destinatario'):
        dependente = valor(estado, 'destinatario')['dependente']
        cursor.execute('UPDATE chatbot.conversa SET status_dependente=%s WHERE id_conversa=%s',
                       (dependente, id_conversa))
        if dependente:
            inserir_dependente_para_conversa(id_conversa, cursor)
    estado.update(status='pronto', etapa_inicial=etapa_inicial(estado))
    salvar(id_conversa, estado, cursor)
    return estado


def guardar_coletas(contexto, efeitos, cursor):
    if not contexto.get('contexto_coleta') or not efeitos:
        return
    cursor.execute('SELECT contexto_coleta FROM chatbot.conversa WHERE id_conversa=%s FOR UPDATE',
                   (contexto['id_conversa'],))
    estado = cursor.fetchone()[0]
    if efeitos.get('cliente_nome_atualizado'):
        estado['campos']['nome'] = campo([efeitos['primeiro_nome_cliente']], 'nome', 'atendimento')
    if efeitos.get('cliente_email_atualizado'):
        cursor.execute('SELECT email FROM chatbot.cliente WHERE id_cliente=%s', (contexto['id_cliente'],))
        estado['campos']['email'] = campo([cursor.fetchone()[0] or ''], 'email', 'atendimento')
        estado['resultado_email'] = efeitos['resultado_coleta_email']
    if efeitos.get('status_dependente_atualizado'):
        texto = 'Para dependente' if efeitos['status_dependente'] else 'Para mim'
        estado['campos']['destinatario'] = campo([texto], 'destinatario', 'atendimento')
    if efeitos.get('destino_dado') == 'cliente':
        cursor.execute('SELECT idade FROM chatbot.cliente WHERE id_cliente=%s', (contexto['id_cliente'],))
        estado['idade_titular'] = cursor.fetchone()[0]
    salvar(contexto['id_conversa'], estado, cursor)
''')

put('workers/worker_flow/coleta_abertura.py', r'''
"""Coordena a coleta da primeira mensagem, sem HTTP, commits ou envio WhatsApp."""

from copy import deepcopy
from core.validacoes.coleta_abertura import criar_contexto, completo, aceito, valor
from core.repositories.atendimento.coleta_abertura import salvar, importar
from core.repositories.atendimento.followup import proteger_conversa
from core.repositories.fireads.consulta import proteger_mensagem_abertura, aplicar_decisao
from core.repositories.fireads import pendencias
from core.integrations.fireads.aba_geral import configuracao_compativel
from workers.worker_consulta_dash.resultado import decisao_organica
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente


def anexar(contexto, estado, fireads=None):
    novo = dict(contexto, contexto_coleta=estado)
    if fireads is not None:
        novo['contexto_fireads'] = fireads
    if aceito(estado, 'destinatario'):
        novo['conversa'] = dict(novo['conversa'], status_dependente=valor(estado, 'destinatario')['dependente'])
    return novo


def preparar(contexto, mensagem, lock_version, cursor, abertura, consulta):
    cid = contexto['conversa']['id_conversa']
    estado = abertura.get('coleta')
    if estado and estado.get('status') == 'pronto':
        return anexar(contexto, estado, abertura.get('contexto'))
    proteger_conversa(cid, lock_version, cursor)
    proteger_mensagem_abertura(mensagem, cursor)
    if estado is None:
        estado = criar_contexto(cid, mensagem)
        estado['fireads_aplicavel'] = bool(abertura['aplicavel'])
        estado['formulario_identificado'] = bool(abertura['aplicavel'] and estado['rota_formulario_chat'])
        salvar(cid, estado, cursor)
    # Não substituir o primeiro formulário por outra mensagem enquanto espera.
    if estado['id_mensagem'] != mensagem['id_mensagem']:
        raise ConsultaFireAdsPendente('primeira_mensagem_ainda_pendente', consulta_nova=False)
    consulta_nova = False
    decisao = None
    if estado['fireads_aplicavel'] and not completo(estado):
        if consulta is None:
            consulta_nova = pendencias.solicitar(dict(abertura, coleta=estado), cid,
                                                 mensagem['cliente_telefone'], cursor)
            consulta = pendencias.buscar(cid, cursor)
        motivo = None
        if not abertura['aplicavel']:
            motivo = 'integracao_desativada'
        elif consulta['id_integracao'] != abertura['id_integracao'] or not configuracao_compativel(consulta['entrada'], abertura):
            motivo = 'configuracao_alterada'
        elif consulta['expirada'] and consulta['status'] != 'concluida':
            motivo = 'tempo_limite_300s'
        if motivo and consulta['status'] != 'concluida':
            pendencias.concluir_sem_http(consulta['id_consulta'], decisao_organica('erro', motivo), cursor)
            consulta = pendencias.buscar(cid, cursor)
        if consulta['status'] != 'concluida':
            estado['status'] = 'aguardando_consulta'
            salvar(cid, estado, cursor)
            raise ConsultaFireAdsPendente('aguardando_resultado', consulta_nova=consulta_nova)
        if consulta['aplicacao'] is not None:
            raise ValueError('Consulta aplicada sem coleta pronta')
        decisao = decisao_organica('erro', motivo) if motivo else deepcopy(consulta['dados']['decisao'])
        if decisao.get('coleta'):
            recebido = decisao['coleta']
            if recebido.get('id_conversa') != cid or recebido.get('id_mensagem') != estado['id_mensagem']:
                raise ValueError('Resultado da consulta não pertence à abertura')
            estado = recebido
        abertura = dict(abertura, id_integracao=consulta['id_integracao'])
    estado = importar(abertura, cid, estado, cursor)
    if not estado['fireads_aplicavel']:
        return anexar(contexto, estado)
    if decisao is None:
        decisao = {'resultado': 'importado', 'origem': 'meta', 'referencia': None, 'motivo': 'formulario_chat_completo'}
    elif estado['rota_formulario_chat'] and decisao.get('origem') == 'organico' and not decisao.get('referencia'):
        decisao['origem'] = 'meta'
    decisao.pop('coleta', None)
    if decisao.get('resultado') == 'importado' and not completo(estado):
        decisao['resultado'] = 'incompleto'
        decisao['motivo'] = 'campo_pendente_apos_importacao'
    decisao['dados_titular'] = {c: valor(estado, c) for c in ('nome', 'email') if aceito(estado, c)}
    if aceito(estado, 'email'):
        decisao['dados_titular']['resultado_email'] = 'email_valido'
    if aceito(estado, 'destinatario'):
        decisao['status_dependente'] = valor(estado, 'destinatario')['dependente']
    decisao['coleta_parcial'] = True
    decisao = aplicar_decisao(abertura, cid, consulta['id_consulta'] if consulta else None, decisao, cursor)
    if consulta:
        pendencias.marcar_aplicada(consulta['id_consulta'], cid, decisao, cursor)
    return anexar(contexto, estado, decisao)
''')

edit('core/repositories/fireads/consulta.py',
     'AND c.iniciou_em >= i.ativada_em) AS aplicavel',
     'AND c.iniciou_em >= i.ativada_em) AS aplicavel, c.contexto_coleta, u.status_pagamento')
edit('core/repositories/fireads/consulta.py', '                "aplicavel",', '                "aplicavel",\n                "coleta",\n                "unidade_ativa",')
edit('core/repositories/fireads/pendencias.py', '    cursor.execute(\n        """INSERT INTO chatbot.consulta_fireads',
     '    if abertura.get("coleta") is not None:\n        entrada["coleta"] = abertura["coleta"]\n    cursor.execute(\n        """INSERT INTO chatbot.consulta_fireads')
edit('workers/worker_consulta_dash/consulta.py', 'from workers.worker_consulta_dash.resultado import',
     'from core.integrations.fireads.coleta_abertura import interpretar_parcial\nfrom workers.worker_consulta_dash.resultado import')
edit('workers/worker_consulta_dash/consulta.py',
     '        decisao = interpretar(geral["rows"], numero, entrada["fuso"], aba=entrada["aba"])',
     '''        if entrada.get("coleta") is not None:
            if entrada['coleta'].get('versao') != 1:
                raise ErroFireAds('Versão de coleta desconhecida')
            decisao = interpretar_parcial(geral['rows'], numero, entrada['fuso'], entrada['aba'], entrada['coleta'])
        else:
            decisao = interpretar(geral["rows"], numero, entrada["fuso"], aba=entrada["aba"])''')

edit('workers/worker_flow/fireads.py', 'def preparar_abertura(contexto_banco, mensagem, lock_version, cursor):',
     '''def preparar_abertura(contexto_banco, mensagem, lock_version, cursor):
    from workers.worker_flow.coleta_abertura import preparar, anexar
    cid = contexto_banco['conversa']['id_conversa']
    abertura = buscar_abertura(cid, cursor)
    if 'unidade_ativa' in abertura and abertura['unidade_ativa'] is not True:
        return contexto_banco
    if abertura.get('coleta'):
        if abertura['etapa'] is not None:
            return anexar(contexto_banco, abertura['coleta'], abertura.get('contexto'))
        return preparar(contexto_banco, mensagem, lock_version, cursor, abertura, pendencias.buscar(cid, cursor))
    # Contextos e consultas anteriores ao deploy conservam o contrato original.
    if 'coleta' not in abertura or abertura.get('contexto') or abertura['etapa'] is not None:
        return _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor)
    consulta = pendencias.buscar(cid, cursor)
    if consulta is not None:
        return _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor)
    return preparar(contexto_banco, mensagem, lock_version, cursor, abertura, None)


def _preparar_abertura_legada(contexto_banco, mensagem, lock_version, cursor):''')
edit('workers/worker_flow/fireads.py', '    estado = contexto.get("contexto_fireads") or {}',
     '''    # Nome histórico da API mantido para replay dos eventos 7/9 -> 11.
    if contexto.get('contexto_coleta'):
        from core.validacoes.coleta_abertura import email_coletado
        return email_coletado(contexto)
    estado = contexto.get("contexto_fireads") or {}''')

put('core/integrations/whatsapp/messages/abertura_coleta.py', r'''
"""Apresentação única e pergunta correspondente ao primeiro campo necessário."""

from core.validacoes.coleta_abertura import valor, validar_contexto
from core.integrations.whatsapp.messages.etapa2_messages import MENSAGEM_REPETICAO_ETAPA2
from core.integrations.whatsapp.messages.etapa4_messages import MENSAGEM_REPETICAO_ETAPA4
from core.integrations.whatsapp.messages.tratamentos.financeiro import montar_mensagem_tratamento_financeiro
from core.integrations.whatsapp.messages.tratamentos.midia import montar_mensagem_tratamento_midia
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import montar_mensagem_tratamento_reforco_escolar


def montar_abertura(contexto, saudacao, tratamento=None):
    estado = validar_contexto(contexto)
    if not estado:
        raise ValueError('Abertura parcial sem contexto')
    genero = contexto.get('genero')
    if genero not in {'feminino', 'masculino'} or not all(contexto.get(c) for c in ('nome_agente', 'nome_unidade')):
        raise ValueError('Apresentação da unidade incompleta')
    nome = valor(estado, 'nome')
    saudacao = f'{saudacao}, {nome}!' if nome else f'{saudacao}!'
    artigo = 'a' if genero == 'feminino' else 'o'
    apresentacao = f"{saudacao} Sou {artigo} {contexto['nome_agente']}, assistente do {contexto['nome_unidade']}. ☺️"
    if estado['formulario_identificado']:
        apresentacao += ('\n\nVi que você já preencheu um dos nossos formulários. Para continuarmos '
                         'com sua reserva por cortesia da unidade vamos precisar fazer mais algumas perguntinhas, ok?')
    pergunta = {1: 'Me diz, qual o seu nome?', 2: MENSAGEM_REPETICAO_ETAPA2,
                4: MENSAGEM_REPETICAO_ETAPA4}[estado['etapa_inicial']]
    tratamentos = {'pergunta_financeira': montar_mensagem_tratamento_financeiro,
                   'duvida_reforco_escolar': montar_mensagem_tratamento_reforco_escolar,
                   'tipo_mensagem_nao_suportado': montar_mensagem_tratamento_midia}
    if tratamento:
        pergunta = tratamentos[tratamento](pergunta)
    return apresentacao + '\n\n' + pergunta
''')

put('core/integrations/whatsapp/pywa_functions/pywa_senders/abertura_coleta.py', r'''
"""Envio da abertura adaptada com o contrato de persistência dos demais senders."""

from pywa.types import Button
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.abertura_coleta import montar_abertura
from core.integrations.whatsapp.messages.etapa2_messages import montar_botoes_etapa2
from core.integrations.whatsapp.messages.componentes_compartilhados import RODAPE_OPCAO_UNICA, montar_texto_com_rodape
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import extrair_id_hash_msg_bot
from core.integrations.whatsapp.pywa_functions.saudacao import obter_saudacao_por_horario


def enviar_abertura_coleta(contexto, *, tratamento=None):
    mensagem = contexto['mensagem_cliente_atual']
    etapa = contexto['contexto_coleta']['etapa_inicial']
    texto = montar_abertura(contexto, obter_saudacao_por_horario(), tratamento)
    argumentos = {'to': mensagem['cliente_telefone'], 'text': texto}
    if etapa == 2:
        texto = montar_texto_com_rodape(texto, RODAPE_OPCAO_UNICA)
        argumentos.update(text=texto, buttons=[Button(title=b, callback_data=b) for b in montar_botoes_etapa2()])
    try:
        enviado = conta_wa(mensagem['id_phone_unidade']).send_message(**argumentos)
        resultado = {'enviou': True, 'resposta_ja_existia': False, 'mensagem_bot': texto,
                     'id_hash_msg_bot': extrair_id_hash_msg_bot(enviado), 'id_etapa_resultante': etapa,
                     'tipo_mensagem': 'interactive_button' if etapa == 2 else 'text',
                     'canal': 'meta_whatsapp', 'atualizar_conversa': True, 'atualizar_last_from_bot': True}
        if etapa == 2:
            resultado['rodape_mensagem'] = RODAPE_OPCAO_UNICA
        if tratamento:
            resultado.update(tratamento=True, tipo_tratamento=tratamento)
        return resultado
    except Exception as erro:
        raise ErroEnvioMeta('Meta falhou ao enviar abertura adaptada', id_etapa=etapa,
                            phone_id_unidade=mensagem['id_phone_unidade'],
                            cliente_telefone=mensagem['cliente_telefone']) from erro
''')

edit('workers/worker_flow/valida_historico.py', 'from workers.worker_flow.fireads import email_importado',
     'from workers.worker_flow.fireads import email_importado\nfrom core.validacoes.coleta_abertura import validar_contexto')
edit('workers/worker_flow/valida_historico.py', '    # A primeira interação importada pertence à pergunta de profissão.',
     '''    coleta = contexto_banco.get('contexto_coleta')
    if coleta and contexto_conversa.get('id_etapa_atual') is None:
        estado = validar_contexto({'id_conversa': id_conversa, 'contexto_coleta': coleta})
        id_etapa_para_insert = estado['etapa_inicial']
    # A primeira interação importada pertence à pergunta de profissão.''')
edit('workers/worker_flow/valida_historico.py',
     '    if contexto_conversa.get("id_etapa_atual") is None and email_importado({',
     '    if not coleta and contexto_conversa.get("id_etapa_atual") is None and email_importado({')
edit('workers/worker_flow/valida_historico.py',
     '        "contexto_fireads": contexto_banco.get("contexto_fireads"),\n        "id_conversa"',
     '        "contexto_fireads": contexto_banco.get("contexto_fireads"),\n        "contexto_coleta": contexto_banco.get("contexto_coleta"),\n        "id_conversa"')

edit('workers/worker_flow/response_flow/flow_sender.py', '    if id_etapa_atual is None and email_importado(contexto_historico):',
     '''    if id_etapa_atual is None and contexto_historico.get('contexto_coleta'):
        from core.validacoes.coleta_abertura import validar_contexto, aceito
        from core.integrations.whatsapp.pywa_functions.pywa_senders.abertura_coleta import enviar_abertura_coleta
        coleta = validar_contexto(contexto_historico)
        if coleta['formulario_identificado'] or any(aceito(coleta, c) for c in ('nome', 'email', 'destinatario')):
            return enviar_abertura_coleta(contexto_historico, tratamento=classificar_tratamento_abertura(contexto_historico))
    if id_etapa_atual is None and not contexto_historico.get('contexto_coleta') and email_importado(contexto_historico):''')

edit('workers/worker_flow/transacoes/movimento_conversa.py', 'from workers.worker_flow.fireads import email_importado',
     'from workers.worker_flow.fireads import email_importado\nfrom core.validacoes.coleta_abertura import validar_contexto')
edit('workers/worker_flow/transacoes/movimento_conversa.py',
     '''        if etapa_destino != ETAPA_1_NOME_CLIENTE and not (
            etapa_destino == 4 and email_importado(contexto_historico)
        ):''',
     '''        coleta = validar_contexto(contexto_historico)
        autorizada = coleta['etapa_inicial'] if coleta else (4 if email_importado(contexto_historico) else ETAPA_1_NOME_CLIENTE)
        if etapa_destino != autorizada:''')
edit('core/repositories/atendimento/conversas.py',
     'if id_etapa_resultante not in {ETAPA_INICIAL, 4}:', 'if id_etapa_resultante not in {ETAPA_INICIAL, 2, 4}:')
edit('core/repositories/atendimento/conversas.py',
     '''          AND (%s = 1 OR (contexto_fireads->>'resultado' = 'importado'
               AND contexto_fireads->>'concluida' = 'true'
               AND contexto_fireads->>'id_conversa' = id_conversa::text));''',
     '''          AND ((contexto_coleta IS NOT NULL
                AND contexto_coleta->>'status'='pronto'
                AND contexto_coleta->>'id_conversa'=id_conversa::text
                AND contexto_coleta->>'etapa_inicial'=%s::text)
              OR (contexto_coleta IS NULL AND (%s=1 OR (%s=4
                AND contexto_fireads->>'resultado'='importado'
                AND contexto_fireads->>'concluida'='true'
                AND contexto_fireads->>'id_conversa'=id_conversa::text))));''')
edit('core/repositories/atendimento/conversas.py',
     '''        id_conversa,
        id_etapa_resultante,
    ))''',
     '''        id_conversa,
        id_etapa_resultante,
        id_etapa_resultante,
        id_etapa_resultante,
    ))''')

edit('workers/worker_flow/response_flow/etapas/resolver_etapa1.py', 'import logging',
     '''import logging
from core.validacoes.coleta_abertura import destinatario_coletado, EVENTO_NOME_DESTINO_COLETADO
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import enviar_etapa4''')
edit('workers/worker_flow/response_flow/etapas/resolver_etapa1.py', '    # VALIDANDO DESTINO(S)',
     '''    if destinatario_coletado(contexto_historico):
        etapa = resolver_destino_transicao(contexto_historico, EVENTO_NOME_DESTINO_COLETADO, destinos_esperados={4})
        envio = enviar_etapa4(cliente_telefone, phone_id_unidade, status_dependente=contexto_historico['status_dependente'])
        envio['primeiro_nome_cliente'] = resultado_nome.primeiro_nome
        return anexar_transicao_ao_contexto_envio(contexto_historico, envio, EVENTO_NOME_DESTINO_COLETADO, etapa)

    # VALIDANDO DESTINO(S)''')
edit('workers/worker_flow/transacoes/efeitos_transicao.py', 'import logging',
     'import logging\nfrom core.validacoes.coleta_abertura import destinatario_coletado, EVENTO_NOME_DESTINO_COLETADO')
edit('workers/worker_flow/transacoes/efeitos_transicao.py', '        # 1 -> 2: o cliente informou o próprio nome.',
     '''        if evento == EVENTO_NOME_DESTINO_COLETADO:
            _exigir_destino(etapa_origem, evento, etapa_destino, 4)
            if not destinatario_coletado(contexto_historico):
                raise ValueError('Salto de destinatário sem dado aceito nesta conversa')
            return _persistir_nome_cliente_capturado_na_etapa1(contexto_historico, contexto_envio, cursor)
        # 1 -> 2: o cliente informou o próprio nome.''')
edit('workers/worker_flow/transacoes/persistencia_resposta.py',
     'from core.repositories.fireads.consulta import guardar_coletas',
     'from core.repositories.fireads.consulta import guardar_coletas\nfrom core.repositories.atendimento.coleta_abertura import guardar_coletas as guardar_coleta_abertura')
edit('workers/worker_flow/transacoes/persistencia_resposta.py',
     '    guardar_coletas(contexto_historico, efeitos_transicao, cursor)',
     '    guardar_coletas(contexto_historico, efeitos_transicao, cursor)\n    guardar_coleta_abertura(contexto_historico, efeitos_transicao, cursor)')
edit('callback/webhook/models.py', '    contexto_fireads = models.JSONField(null=True, blank=True)',
     '    contexto_fireads = models.JSONField(null=True, blank=True)\n    contexto_coleta = models.JSONField(null=True, blank=True, editable=False)')
# O seed histórico precede as migrações e conserva suas 30 arestas.
# A migração nova adiciona a 31a aresta depois dos validadores históricos.
shutil.copy2(BASE / 'core/database/deploy_database/etapa_transicao_script.py',
             ROOT / 'core/database/deploy_database/etapa_transicao_script.py')

edit('core/repositories/funil/leads.py', ') AS primeiro_atendimento', ') AS primeiro_atendimento, c.contexto_coleta')
edit('core/repositories/funil/leads.py', "    dados['primeiro_atendimento'] = resultado[17]", '''    coleta = resultado[18] if len(resultado) > 18 else None
    if coleta:
        from core.validacoes.coleta_abertura import validar_contexto, valor, aceito
        validar_contexto({'id_conversa': id_conversa, 'contexto_coleta': coleta})
        dados['contexto_coleta'] = coleta
        dados['nome_cliente'] = valor(coleta, 'nome')
        dados['email_cliente'] = valor(coleta, 'email')
        dados['idade_cliente'] = coleta.get('idade_titular')
        dados['resultado_email_coleta'] = 'email_valido' if aceito(coleta, 'email') else coleta.get('resultado_email')
        if not dados['nome_cliente'] or not dados['resultado_email_coleta']:
            raise ValueError('Coletas históricas incompletas para o Funil')
    dados['primeiro_atendimento'] = resultado[17]''')
edit('core/integrations/funil/oportunidades.py',
     "    if dados_lead.get('origem_fireads'):\n        classificacao = dados_lead['resultado_email_fireads']",
     "    if dados_lead.get('contexto_coleta') or dados_lead.get('origem_fireads'):\n        classificacao = dados_lead.get('resultado_email_coleta') or dados_lead.get('resultado_email_fireads')")

edit('core/repositories/funil/leads.py',
     "        if 'nome' not in retrato or 'resultado_email' not in retrato:\n            raise ValueError('Coletas históricas FireAds incompletas para o Funil')\n        dados.update(nome_cliente=retrato['nome'], email_cliente=retrato.get('email'),\n                     idade_cliente=retrato.get('idade'), resultado_email_fireads=retrato['resultado_email'])",
     "        if not (len(resultado) > 18 and resultado[18]):\n            if 'nome' not in retrato or 'resultado_email' not in retrato:\n                raise ValueError('Coletas históricas FireAds incompletas para o Funil')\n            dados.update(nome_cliente=retrato['nome'], email_cliente=retrato.get('email'),\n                         idade_cliente=retrato.get('idade'), resultado_email_fireads=retrato['resultado_email'])")

put('core/integrations/fireads/destino_coleta.py', r'''
"""Escolha persistível do alvo de entrega para a coleta por campo."""

from copy import deepcopy
from core.validacoes.coleta_abertura import aceito, campo
from core.integrations.fireads.coleta_abertura import campos_registro, compativel
from core.integrations.fireads.aba_geral import mais_recente, referencia_registro, relocalizar, numero_linha
from core.integrations.fireads.contrato import CANAIS, ErroFireAds, telefone, localizar, acrescentar_observacoes
from core.integrations.fireads.destino_dashboard import linhas_com_bloco


def identidade_entrega(estado):
    # Conhecidos no formulário não são substituídos por correções posteriores.
    campos = deepcopy(estado['mensagem_original'])
    for tipo in ('email', 'nome', 'destinatario'):
        if campos[tipo]['status'] != 'aceito':
            campos[tipo] = deepcopy(estado['campos'][tipo])
    return campos


def escolher(rows, snapshot):
    if snapshot.get('referencia') is not None:
        # Exclusão/edição de um registro já vinculado exige conferência.
        relocalizar(rows, snapshot['referencia'], snapshot['aba'])
        return {'tipo': 'update', 'referencia': snapshot['referencia']}
    encontrados = localizar(rows, snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
    candidatos = encontrados
    if snapshot['rota_formulario_chat']:
        identidade = snapshot['identidade_coleta']
        # Sem confirmação final de e-mail/destinatário não inventar equivalência.
        candidatos = [r for r in encontrados if all(identidade[c]['status'] == 'aceito' for c in ('email', 'destinatario'))
                       and compativel(identidade, campos_registro(r), campos=('email', 'destinatario'))]
    row = mais_recente(candidatos, snapshot.get('fuso'))
    if row:
        return {'tipo': 'update', 'referencia': referencia_registro(row, snapshot['aba'], snapshot.get('fuso'))}
    email = str(snapshot.get('email') or '').strip().casefold()
    outros = [r for r in rows if r not in encontrados]
    if email and any(str(r.get('Email') or '').strip().casefold() == email for r in outros):
        raise ErroFireAds('Email já presente em outro telefone; conferir identidade')
    return {'tipo': 'create'}


def preparar(rows, snapshot, bloco):
    acrescentar_observacoes(None, bloco)
    encontrados = localizar(rows, snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
    if linhas_com_bloco(encontrados, bloco):
        return None
    alvo = snapshot.get('destino')
    if not alvo:
        raise ErroFireAds('Destino da coleta ainda não foi persistido')
    if alvo['tipo'] == 'update':
        row = relocalizar(rows, alvo['referencia'], snapshot['aba'])
        if 'Observação' not in row:
            raise ErroFireAds('Observação ausente; não sobrescrever')
        obs, mudou = acrescentar_observacoes(row.get('Observação'), bloco)
        return {'row': numero_linha(row), 'observacoes': obs} if mudou else None
    if alvo['tipo'] != 'create':
        raise ErroFireAds('Tipo de destino desconhecido')
    # Rechecar identidade cruzada também em retries de um create planejado.
    email = str(snapshot.get('email') or '').strip().casefold()
    if email and any(r not in encontrados and str(r.get('Email') or '').strip().casefold() == email for r in rows):
        raise ErroFireAds('Email já presente em outro telefone; conferir identidade')
    return {'dados': {'Nome': snapshot['nome'], 'Email': snapshot['email'],
                       'WhatsApp': telefone(snapshot['telefone']), 'Perfil/Faixa': snapshot['perfil'],
                       'Para quem é': snapshot['para_quem'], 'Canal': CANAIS[snapshot['origem']][0], 'Observação': bloco}}
''')

edit('core/repositories/fireads/envios.py', '    cursor.execute(\n        """INSERT INTO chatbot.envios_dash',
     '''    if dados.get('contexto_coleta'):
        from core.integrations.fireads.destino_coleta import identidade_entrega
        coleta = dados['contexto_coleta']
        identidade = identidade_entrega(coleta)
        alvo = identidade['destinatario']
        snapshot.update(versao=3, rota_formulario_chat=coleta['rota_formulario_chat'],
                        identidade_coleta=identidade, destino=None,
                        para_quem=alvo['valor']['texto'] if alvo['status']=='aceito' else (
                            'Para dependente' if dados['status_dependente'] else 'Para mim'))
    cursor.execute(
        """INSERT INTO chatbot.envios_dash''')
put('core/repositories/fireads/destino_coleta.py', r'''
"""Congela a decisão de update/create sob a mesma reserva do envio."""

from psycopg.types.json import Jsonb
from core.repositories.fireads.envios import conferir_posse


def salvar_destino(envio, destino, cursor):
    conferir_posse(envio, cursor)
    cursor.execute("""UPDATE chatbot.envios_dash SET snapshot=jsonb_set(snapshot,'{destino}',%s),
                      atualizado_em=clock_timestamp()
                      WHERE id_envio_dash=%s AND status='processing' AND attempt_count=%s
                        AND (snapshot->'destino' IS NULL OR snapshot->'destino'='null'::jsonb)
                      RETURNING snapshot""", (Jsonb(destino), envio['id'], envio['tentativa']))
    row = cursor.fetchone()
    if row is None:
        raise ValueError('Destino já congelado ou reserva perdida')
    return row[0]
''')
edit('workers/worker_funil/fireads.py', 'def preparar_escrita(rows, snapshot, bloco):',
     '''def preparar_escrita(rows, snapshot, bloco):
    if snapshot.get('versao') == 3:
        from core.integrations.fireads.destino_coleta import preparar
        return preparar(rows, snapshot, bloco)''')
edit('workers/worker_funil/fireads.py', '        if snapshot.get("versao") == 2:',
     '''        if snapshot.get('versao') == 3 and not {'Para quem é', 'Canal', 'Data/Hora'} <= set(dados['headers']):
            raise ErroFireAds('Cabeçalhos da coleta incompletos')
        if snapshot.get("versao") in {2, 3}:''')
edit('workers/worker_funil/fireads.py', '        operacao = preparar_escrita(dados["rows"], snapshot, bloco)',
     '''        if snapshot.get('versao') == 3 and not snapshot.get('destino'):
            encontrados = localizar(dados['rows'], snapshot['telefone'], 'WhatsApp', incluir_equivalentes=True)
            if not linhas_com_bloco(encontrados, bloco):
                from core.integrations.fireads.destino_coleta import escolher
                from core.repositories.fireads.destino_coleta import salvar_destino
                snapshot = salvar_destino(envio, escolher(dados['rows'], snapshot), cursor)
                envio['snapshot'] = snapshot
                conn.commit()
        operacao = preparar_escrita(dados["rows"], snapshot, bloco)''')

put('deploy/migrations/20261019_coleta_abertura.sql', r'''
-- Executar inteiro no DBeaver, com webhook e TODOS os workers parados.
-- Exige a migração 20261014_fireads_aba_geral_v1. Não chama serviços externos.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL COLETA ABERTURA
DO $migracao$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261014_fireads_aba_geral_v1') THEN
        RAISE EXCEPTION 'Aplicar primeiro a migração da aba geral.';
    END IF;
    LOCK TABLE chatbot.conversa, chatbot.etapa_transicao, chatbot.migracoes_fireads IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261019_coleta_abertura_v1') THEN
        RAISE NOTICE 'Coleta por campo já migrada; nenhum atendimento reprocessado.';
        RETURN;
    END IF;
    ALTER TABLE chatbot.conversa ADD COLUMN contexto_coleta JSONB NULL;
    ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_contexto_coleta CHECK (
        contexto_coleta IS NULL OR COALESCE((
            jsonb_typeof(contexto_coleta)='object'
            AND contexto_coleta->>'versao'='1'
            AND contexto_coleta->>'id_conversa'=id_conversa::text
            AND jsonb_typeof(contexto_coleta->'campos')='object'
            AND jsonb_typeof(contexto_coleta->'mensagem_original')='object'
            AND contexto_coleta->>'status' IN ('preparando','aguardando_consulta','pronto')
            AND (contexto_coleta->>'status'<>'pronto' OR contexto_coleta->>'etapa_inicial' IN ('1','2','4'))
        ), FALSE)
    );
    -- Preserva os IDs e o mapa atual. A aresta adicional só é usada com destino coletado.
    IF EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=1
               AND (evento='nome_cliente_valido_destino_coletado' OR id_etapa_destino=4)
               AND NOT (evento='nome_cliente_valido_destino_coletado' AND id_etapa_destino=4)) THEN
        RAISE EXCEPTION 'Aresta 1 -> 4 conflita com o mapa existente.';
    END IF;
    INSERT INTO chatbot.etapa_transicao(id_etapa_origem,evento,id_etapa_destino)
    VALUES (1,'nome_cliente_valido_destino_coletado',4)
    ON CONFLICT (id_etapa_origem,evento) DO NOTHING;
    INSERT INTO chatbot.migracoes_fireads(versao) VALUES ('20261019_coleta_abertura_v1');
END $migracao$;
-- FIM DDL COLETA ABERTURA

COMMIT;
SELECT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261019_coleta_abertura_v1') AS migracao_ok,
       EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=1
               AND evento='nome_cliente_valido_destino_coletado' AND id_etapa_destino=4) AS transicao_ok,
       (SELECT COUNT(*) FROM chatbot.conversa WHERE contexto_coleta IS NOT NULL) AS conversas_com_coleta;
''')

edit('core/database/deploy_database/fireads_script.py', '        )[0])', '''        )[0])
        coleta = caminho.with_name('20261019_coleta_abertura.sql').read_text(encoding='utf-8')
        cursor.execute(coleta.split('-- INICIO DDL COLETA ABERTURA\n', 1)[1].split(
            '-- FIM DDL COLETA ABERTURA', 1)[0])'''.replace('ABERTURA\n', 'ABERTURA\\n'))

edit('tests/fixtures/fireads.py', '\n\ndef como_aba_geral(google, meta):', '''
    coleta = MIGRACAO_FIREADS.with_name('20261019_coleta_abertura.sql').read_text(encoding='utf-8')
    cursor.execute(coleta.split('-- INICIO DDL COLETA ABERTURA\\n', 1)[1].split('-- FIM DDL COLETA ABERTURA', 1)[0])


def como_aba_geral(google, meta):''')
edit('tests/integration/test_fireads_postgres.py',
     '            "cliente_telefone": NUMERO,\n        }',
     '            "cliente_telefone": NUMERO,\n            "id_hash": "wamid.fireads",\n            "tipo_mensagem": "text",\n            "conteudo_texto": "Oi",\n        }')
edit('tests/integration/test_fireads_postgres.py',
     '    def resultado_google(self):\n        return {',
     '''    def resultado_google(self):
        entrada = self.conn.execute('SELECT entrada FROM chatbot.consulta_fireads ORDER BY id_consulta DESC LIMIT 1').fetchone()
        if entrada and entrada[0].get('coleta'):
            from core.integrations.fireads.coleta_abertura import interpretar_parcial
            e = entrada[0]
            rows = como_aba_geral([GOOGLE], [])
            return {'decisao': interpretar_parcial(rows, NUMERO, e['fuso'], e['aba'], e['coleta']), 'fontes': {'geral': rows}}
        return {''')
edit('tests/integration/test_fireads_postgres.py',
     '             ("20261014_fireads_aba_geral_v1",)],',
     '             ("20261014_fireads_aba_geral_v1",), ("20261019_coleta_abertura_v1",)],')
edit('tests/integration/test_fireads_postgres.py',
     '            30,\n        )\n\n    def test_importacao_dependente',
     '            31,\n        )\n\n    def test_importacao_dependente')
edit('tests/integration/test_fireads_postgres.py',
     '''    def test_conflito_email_preserva_referencia_sem_importacao_parcial(self):
        cid, mensagem, versao, contexto = self.solicitar_pendente()''',
     '''    def test_conflito_email_preserva_referencia_sem_importacao_parcial(self):
        # Consulta já existente antes do novo contrato mantém importação legada.
        cid, mensagem, versao, contexto = self.preparar_mensagem()
        pendencias.solicitar(consulta.buscar_abertura(cid, self.cursor), cid, NUMERO, self.cursor)
        self.conn.commit()''')
edit('tests/integration/test_fireads_postgres.py',
     '''        self.assertEqual(
            preparar_abertura(contexto, mensagem, versao, self.cursor), contexto
        )''',
     '''        preparado = preparar_abertura(contexto, mensagem, versao, self.cursor)
        self.assertEqual(preparado['conversa'], contexto['conversa'])
        self.assertEqual(preparado['contexto_coleta']['etapa_inicial'], 1)
        self.assertNotIn('contexto_fireads', preparado)''')

edit('tests/integration/test_fireads_postgres.py',
     '''            return_value={
                "decisao": interpretar(como_aba_geral([GOOGLE], []), NUMERO, None),
                "fontes": {"google": [GOOGLE], "meta": []},
            },''',
     '''            return_value=self.resultado_google(),''')
edit('tests/integration/test_fireads_postgres.py',
     '''        for _ in range(2):
            self.conn.execute(sql, prepare=False)
        pendente =''',
     '''        for _ in range(2):
            self.conn.execute(sql, prepare=False)
        # O runtime atual só entra depois de todas as migrações do deploy.
        self.conn.execute(MIGRACAO_FIREADS.with_name('20261019_coleta_abertura.sql').read_text(encoding='utf-8'), prepare=False)
        pendente =''')
edit('tests/integration/test_fireads_postgres.py',
     '''    def test_migracao_com_registro_legado_preserva_resultado_e_reexecucao(self):
        cid = self.nova_conversa()
        decisao = self.importar(cid)
        self.conn.commit()''',
     '''    def test_migracao_com_registro_legado_preserva_resultado_e_reexecucao(self):
        from psycopg.types.json import Jsonb
        cid = self.nova_conversa()
        # Semeia o contrato histórico sem chamar o runtime novo no esquema antigo.
        decisao = dict(interpretar(como_aba_geral([GOOGLE], []), NUMERO, None),
                       id_conversa=cid, concluida=True)
        self.cursor.execute('UPDATE chatbot.conversa SET origem_fireads=%s,contexto_fireads=%s WHERE id_conversa=%s',
                            (decisao['origem'], Jsonb(decisao), cid))
        self.conn.commit()''')
edit('tests/integration/test_fireads_postgres.py',
     '''        decisao = interpretar([row], NUMERO)
        self.assertTrue(pendencias.concluir''',
     '''        from core.integrations.fireads.coleta_abertura import interpretar_parcial
        decisao = interpretar_parcial([row], NUMERO, None, reserva['entrada']['aba'], reserva['entrada']['coleta'])
        self.assertTrue(pendencias.concluir''')
edit('tests/integration/test_fireads_postgres.py',
     '''            {'destino_dado': 'cliente'}, self.cursor,
        )
        fila_funil.sincronizar_envios_elegiveis(self.cursor)
        envio = fila_funil.reivindicar_proximo_envio(self.cursor)''',
     '''            {'destino_dado': 'cliente'}, self.cursor,
        )
        from core.repositories.atendimento.coleta_abertura import guardar_coletas
        guardar_coletas({'id_cliente': 1, 'id_conversa': cid,
                         'contexto_coleta': resultado['contexto_coleta']},
                        {'destino_dado': 'cliente'}, self.cursor)
        fila_funil.sincronizar_envios_elegiveis(self.cursor)
        envio = fila_funil.reivindicar_proximo_envio(self.cursor)''')

CHANGES.extend(['tests/unit/test_coleta_abertura.py', 'tests/integration/test_coleta_abertura_postgres.py'])
for path, complemento in {
    'REGRAS_DE_NEGOCIO.md': '''

## Coleta por campo na abertura (contrato 1)

Esta regra substitui, para novas conversas, a exigência de importação completa
FireAds. A primeira mensagem pode fornecer nome do titular, e-mail e destinatário
explícitos. Valores diferentes no mesmo campo ficam conflitantes; repetições
equivalentes são um único valor. O telefone é sempre o remetente WhatsApp.

Com os três campos aceitos, iniciar na profissão (etapa 4) sem consulta. Com
FireAds e coleta incompleta, consultar uma vez uma inscrição compatível; completar
somente o desconhecido a partir dessa inscrição. Sem FireAds, perguntar o que
falta. Nome pendente inicia na 1; destinatário pendente com nome conhecido inicia
na 2; nome e destinatário conhecidos iniciam na 4. E-mail pendente mantém a etapa
10 e sua política atual. Nome aceito na 1 com destinatário já coletado usa a nova
aresta autorizada 1 -> 4. Não antecipar profissão, idade ou dados do dependente.

Contexto próprio por conversa conserva candidatos, fonte de cada campo e dados
originais. Conversas e consultas legadas conservam o contrato antigo. Não
reinterpretar mensagens de conversas em andamento nem reconsultar por etapa.
Unidades sem FireAds preservam codigo_canal_venda da integração Funil (padrão
113340); a coleta não lhes atribui origem FireAds nem gera entrega ao dashboard.

Para formulário recebido no chat sem referência já vinculada, a entrega procura
telefone, e-mail e destinatário compatíveis e escolhe data/hora mais recente,
depois maior linha. Parentesco conhecido distingue inscrições para dependentes
diferentes. Ausência ou incompatibilidade gera nova linha preservando a origem.
Erro de leitura não autoriza criar. Salvar o destino antes do POST; retry mantém
esse destino e reconcilia primeiro o marcador técnico. Não substituir referência
vinculada apagada/alterada por uma inscrição nova. Somente Observação muda em
updates, preservando conteúdo anterior; append inclui Para quem é.
''',
    'PADROES_DE_ARQUITETURA.md': '''

## Coleta da primeira mensagem e dados parciais

`core/validacoes/coleta_abertura.py` extrai campos e mantém o contrato puro.
`core/integrations/fireads/coleta_abertura.py` cruza uma única inscrição externa.
`core/repositories/atendimento/coleta_abertura.py` persiste o JSON da conversa;
`workers/worker_flow/coleta_abertura.py` orquestra a abertura sem HTTP/commit.
O ciclo principal continua responsável pelas guardas, transações e envio.

`contexto_coleta` é independente de FireAds. O contrato 1 registra o estado por
campo e uma cópia imutável dos dados da primeira mensagem. Não usar cache ou
cadastro de outra conversa como fonte desses campos. As consultas reais usam a
fila existente; mensagem completa não cria consulta fictícia. Eventos históricos
`oferta_aceita_email_fireads` e `retorno_confirmado_email_fireads` conservam seus
nomes para replay, mas aceitam também e-mail previamente coletado nesta conversa.

Snapshots de entrega versão 3 acrescentam identidade de coleta e destino
persistido, sem mudar snapshots antigos. A escolha do alvo é feita na integração,
salva pelo repositório sob a reserva atual e confirmada pelo worker antes do POST.
As limitações da API externa entre leitura/escrita continuam as mesmas.
''',
    'tests/README.md': '''

## Coleta por campo na abertura

`python -m unittest tests.unit.test_coleta_abertura -q` cobre as oito combinações
de campos, conflitos, nomes compostos, fontes, recência e escolha de destino.
`tests.integration.test_coleta_abertura_postgres` usa FIREADS_TEST_DSN exclusivamente
em loopback, banco descartável test_chatbot_fireads sem schema chatbot preexistente.
O teste recusa outros destinos; usa o SQL real e substitui serviços externos.
Não fornecer credenciais de produção aos testes.
''',
}.items():
    put(path, (BASE / path).read_text(encoding='utf-8') + complemento)

Path(__file__).with_name('changes.json').write_text(json.dumps(CHANGES), encoding='utf-8')
