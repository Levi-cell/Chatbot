"""Pedidos de endereço e dúvidas comerciais durante o atendimento.

Classificação pura; o contexto já contém os dados preparados antes do envio.
Os tratamentos existentes conservam sua prioridade e seus resolvers.
"""

from core.validacoes.endereco import TIPO_TRATAMENTO_ENDERECO, validar_pedido_endereco
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import validar_midia
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import validar_pergunta_financeira
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import validar_duvida_reforco_escolar
from workers.worker_flow.response_flow.etapas.validadores_contexto.validador_financeiro_etapa4 import validar_pergunta_financeira_etapa4
from workers.worker_flow.response_flow.etapas.validadores_contexto.validador_reforco_escolar_etapa4 import validar_duvida_reforco_escolar_etapa4
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_8_OFERTA_ADIADA


ETAPAS_TRATAMENTO_ENDERECO = frozenset({None, *range(1, 23)})
# Nos demais pontos, financeiro/reforço conservam os resolvers existentes.
# Comentário livre (23) e finalização (24) não são reinterpretados.
ETAPAS_TRATAMENTOS_COMPARTILHADOS = frozenset({8, *range(12, 18), 19, 21})


def classificar_tratamento_informativo(contexto):
    etapa = contexto.get("id_etapa_atual")
    if etapa not in ETAPAS_TRATAMENTO_ENDERECO or validar_midia(contexto.get("tipo_mensagem_atual")):
        return None
    texto = contexto.get("texto_cliente_atual")
    reforco = validar_duvida_reforco_escolar_etapa4 if etapa == 4 else validar_duvida_reforco_escolar
    financeiro = validar_pergunta_financeira_etapa4 if etapa == 4 else validar_pergunta_financeira
    if reforco(texto):
        return "duvida_reforco_escolar" if etapa in ETAPAS_TRATAMENTOS_COMPARTILHADOS else None
    if financeiro(texto):
        return "pergunta_financeira" if etapa in ETAPAS_TRATAMENTOS_COMPARTILHADOS else None
    if validar_pedido_endereco(texto):
        return TIPO_TRATAMENTO_ENDERECO
    return None


def enviar_tratamento_informativo(contexto):
    from core.integrations.whatsapp.messages.tratamentos.endereco import montar_mensagem_tratamento_endereco
    from core.integrations.whatsapp.messages.tratamentos.financeiro import montar_mensagem_tratamento_financeiro
    from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import montar_mensagem_tratamento_reforco_escolar
    from core.integrations.whatsapp.pywa_functions.cliente import usar_prefixo_mensagem_bot, aplicar_prefixo_mensagem_bot
    from core.integrations.whatsapp.messages.componentes_compartilhados import montar_texto_com_cabecalho
    from core.integrations.whatsapp.messages.tratamentos.composicao import unir_blocos_mensagem
    from workers.worker_flow.response_flow.repeticao_etapa import SENDERS_TRIAGEM, selecionar_sender_repeticao

    tratamento = classificar_tratamento_informativo(contexto)
    if tratamento is None:
        raise ValueError("Pedido informativo sem classificação")
    etapa = contexto.get("id_etapa_atual")
    if etapa is None:
        from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa1 import enviar_etapa1_endereco_inicio
        msg = contexto["mensagem_cliente_atual"]
        return enviar_etapa1_endereco_inicio(
            msg["cliente_telefone"], msg["id_phone_unidade"], contexto["nome_unidade"],
            contexto["nome_agente"], contexto["genero"], contexto.get("endereco_unidade"),
            contexto.get("horarios_funcionamento"),
        )
    prefixo = {
        "pergunta_financeira": montar_mensagem_tratamento_financeiro,
        "duvida_reforco_escolar": montar_mensagem_tratamento_reforco_escolar,
        TIPO_TRATAMENTO_ENDERECO: lambda pergunta: montar_mensagem_tratamento_endereco(
            pergunta, contexto.get("endereco_unidade"), contexto.get("horarios_funcionamento"),
        ),
    }[tratamento]("")
    prefixo = unir_blocos_mensagem(contexto.get("saudacao_retorno"), prefixo)
    msg = contexto["mensagem_cliente_atual"]
    with usar_prefixo_mensagem_bot(prefixo):
        if etapa == ETAPA_8_OFERTA_ADIADA:
            from workers.worker_flow.response_flow.etapas.resolver_etapa8 import resolve_etapa8

            # A dúvida acompanha a abertura da 9. Reutiliza a transição validada
            # antes do envio; não repete a espera nem interpreta aceite da reserva.
            envio = resolve_etapa8(contexto, incluir_saudacao=False)
        else:
            sender, extras = selecionar_sender_repeticao(etapa, contexto["dados_repeticao"])
            # A triagem já reapresenta sua pergunta canônica sem repeticao=True.
            opcoes_envio = {} if etapa in SENDERS_TRIAGEM else {"repeticao": True}
            envio = sender(msg["cliente_telefone"], msg["id_phone_unidade"], *extras, **opcoes_envio)
            envio["tratamento"] = True
    texto = envio["mensagem_bot"]
    if envio.get("cabecalho_mensagem"):
        texto = montar_texto_com_cabecalho(texto, envio["cabecalho_mensagem"])
    envio.update(
        mensagem_bot=aplicar_prefixo_mensagem_bot(texto, prefixo),
        tipo_tratamento=tratamento,
    )
    # Na 8, tipo_tratamento descreve a orientação na abertura da 9; o flag
    # tratamento permanece reservado às respostas sem avanço das demais etapas.
    return envio
