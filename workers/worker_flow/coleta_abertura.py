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
