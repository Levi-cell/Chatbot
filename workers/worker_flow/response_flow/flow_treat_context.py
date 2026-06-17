import logging


logger = logging.getLogger("worker.treat_context")


def flow_treat_context(contexto_historico, contexto_validacao):
    # Esqueleto reservado para a V1 quando as regras de contexto por etapa
    # forem definidas. Tratamento de contexto deve usar id_etapa_cliente,
    # repetir a pergunta/opcoes da etapa atual e nao avancar a conversa.
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_cliente = contexto_historico["id_etapa_cliente"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.warning(
        "flow_treat_context_nao_implementado | acao=erro id_conversa=%s etapa_cliente=%s id_mensagem_fila=%s resultado=%s",
        id_conversa,
        id_etapa_cliente,
        mensagem_cliente_atual["id_mensagem_fila"],
        contexto_validacao["resultado"],
    )
    raise NotImplementedError(
        "Tratamento de mensagem fora de contexto ainda nao implementado"
    )
