import logging

from core.integrations.whatsapp.sender_tratamento import (
    sender_tratamento_tipo_nao_suportado,
)


logger = logging.getLogger("worker.treat_unsupported_type")


def flow_treat_unsupported_type(contexto_historico, contexto_validacao):
    # Regra de negocio V1: esta versao nao trabalha com midias/anexos.
    # Midia recebida entra no historico, recebe tratamento e nao avanca etapa.
    id_conversa = contexto_historico["id_conversa"]
    retry_count = contexto_historico["retry_count"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_unsupported_type_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s tratamento=%s retry=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            contexto_validacao["tipo_tratamento"],
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
            "tratamento": True,
            "tipo_tratamento": contexto_validacao["tipo_tratamento"],
            "atualizar_conversa": False,
            "atualizar_last_from_bot": True,
        }

    if retry_count > 1:
        logger.info(
            "flow_treat_unsupported_type_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s tratamento=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            retry_count,
            contexto_validacao["tipo_tratamento"],
        )

    if contexto_validacao["tipo_tratamento"] == "tipo_mensagem_nao_suportado":
        mensagem_bot = _montar_mensagem_tipo_nao_suportado(contexto_historico)

        return sender_tratamento_tipo_nao_suportado(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=contexto_historico["id_etapa_cliente"],
            tipo_mensagem=contexto_validacao.get("tipo_mensagem"),
            mensagem_bot=mensagem_bot,
        )

    logger.warning(
        "flow_treat_unsupported_type_nao_implementado | acao=erro id_conversa=%s tratamento=%s",
        id_conversa,
        contexto_validacao["tipo_tratamento"],
    )
    raise NotImplementedError(
        f"Tratamento {contexto_validacao['tipo_tratamento']} ainda nao implementado"
    )


def _montar_mensagem_tipo_nao_suportado(contexto_historico):
    if contexto_historico.get("id_etapa_atual") is None:
        return (
            "Ola! Vi que voce iniciou o atendimento com uma midia.\n\n"
            "Por enquanto eu so consigo continuar por mensagem de texto ou botoes. "
            "Envie uma mensagem de texto para comecarmos."
        )

    return (
        "Recebi uma midia, mas nesta etapa eu preciso que voce responda por texto "
        "ou use os botoes disponiveis.\n\n"
        "Envie uma mensagem de texto para continuarmos."
    )
