import logging


logger = logging.getLogger("worker.treat_context")


def flow_treat_context(contexto_historico, contexto_validacao):
    # Esqueleto reservado para a V1 quando as regras de contexto por etapa
    # forem definidas. Tratamento de contexto deve usar id_etapa_cliente,
    # repetir a pergunta/opcoes da etapa atual e nao avancar a conversa.
    id_conversa = contexto_historico["id_conversa"]
    retry_count = contexto_historico["retry_count"]
    id_etapa_cliente = contexto_historico["id_etapa_cliente"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_context_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_cliente=%s tratamento=%s retry=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_cliente,
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

    logger.warning(
        "flow_treat_context_nao_implementado | acao=erro id_conversa=%s etapa_cliente=%s id_mensagem_fila=%s resultado=%s retry=%s",
        id_conversa,
        id_etapa_cliente,
        mensagem_cliente_atual["id_mensagem_fila"],
        contexto_validacao["resultado"],
        retry_count,
    )
    raise NotImplementedError(
        "Tratamento de mensagem fora de contexto ainda nao implementado"
    )
