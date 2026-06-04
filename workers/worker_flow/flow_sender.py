import logging


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    """
    Decide futuramente qual mensagem enviar com base no contexto consolidado.

    Por enquanto monta mensagens simples por etapa para validar o fluxo seco.
    """

    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resposta = contexto_historico["id_etapa_resposta"]
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]
    texto_cliente_atual = mensagem_cliente_atual["conteudo_texto"]

    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_sender_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_resposta=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            resposta_bot_atual.get("id_mensagem"),
            resposta_bot_atual.get("id_etapa"),
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
        }

    if retry_count > 1:
        logger.info(
            "flow_sender_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            retry_count,
        )

    if id_etapa_resposta == 1:
        print("saudacao")
        mensagem_bot = "Ola! Seja bem-vindo."

    elif id_etapa_resposta == 2:
        print("pergunta atendimento")
        mensagem_bot = "O atendimento e para voce ou para outra pessoa?"

    elif id_etapa_resposta == 3:
        print("pergunta nome")
        mensagem_bot = "Qual e o seu nome?"

    elif id_etapa_resposta == 4:
        print("pergunta idade")
        mensagem_bot = "Qual e a sua idade?"

    elif id_etapa_resposta == 5:
        print("pergunta unidade/interesse")
        mensagem_bot = "Em qual unidade voce deseja atendimento?"

    elif id_etapa_resposta == 6:
        print("confirmacao final")
        mensagem_bot = "Perfeito. Vou te enviar o link de agendamento."

    elif id_etapa_resposta == 7:
        print("link agendamento")
        mensagem_bot = "Aqui esta seu link de agendamento: ..."

    else:
        logger.warning(
            "flow_sender_etapa_invalida | acao=nao_enviar id_conversa=%s etapa=%s",
            id_conversa,
            id_etapa_resposta,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": None,
            "id_etapa_resultante": id_etapa_resposta,
        }

    logger.debug(
        "flow_sender_mensagem_definida | acao=simular_envio id_conversa=%s etapa=%s texto_cliente=%s",
        id_conversa,
        id_etapa_resposta,
        texto_cliente_atual,
    )

    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": mensagem_bot,
        "id_hash_msg_bot": None,
        "id_etapa_resultante": id_etapa_resposta,
    }
