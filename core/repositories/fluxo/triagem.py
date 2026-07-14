import logging


logger = logging.getLogger("db.respostas_triagem")


def registrar_resposta_triagem(
    id_conversa,
    id_etapa,
    resposta,
    id_historico_mensagem_cliente,
    cursor,
):
    """
    Registra uma resposta por conversa e pergunta sem permitir divergência.

    Um retry pode reaplicar a mesma transição. Nesse caso, a resposta já
    existente é reutilizada; uma resposta diferente para o mesmo turno é
    tratada como inconsistência transacional.
    """
    cursor.execute(
        """
        INSERT INTO chatbot.respostas_desafios (
            id_conversa,
            id_etapa,
            resposta,
            id_historico_mensagem_cliente
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (id_conversa, id_etapa) DO NOTHING
        RETURNING
            id_resposta_desafio,
            resposta,
            id_historico_mensagem_cliente;
        """,
        (
            id_conversa,
            id_etapa,
            resposta,
            id_historico_mensagem_cliente,
        ),
    )
    resultado = cursor.fetchone()
    inserido = resultado is not None

    if resultado is None:
        cursor.execute(
            """
            SELECT
                id_resposta_desafio,
                resposta,
                id_historico_mensagem_cliente
            FROM chatbot.respostas_desafios
            WHERE id_conversa = %s
              AND id_etapa = %s
            FOR UPDATE;
            """,
            (id_conversa, id_etapa),
        )
        resultado = cursor.fetchone()

    if resultado is None:
        raise ValueError(
            "Resposta da triagem não foi inserida nem encontrada "
            f"(id_conversa={id_conversa}, id_etapa={id_etapa})"
        )

    if resultado[1] != resposta:
        raise ValueError(
            "Resposta divergente para a mesma pergunta da triagem "
            f"(id_conversa={id_conversa}, id_etapa={id_etapa}, "
            f"existente={resultado[1]}, recebida={resposta})"
        )

    id_historico_persistido = resultado[2]

    if (
        id_historico_persistido is None
        and id_historico_mensagem_cliente is not None
    ):
        cursor.execute(
            """
            UPDATE chatbot.respostas_desafios
            SET id_historico_mensagem_cliente = %s
            WHERE id_resposta_desafio = %s;
            """,
            (id_historico_mensagem_cliente, resultado[0]),
        )
        id_historico_persistido = id_historico_mensagem_cliente

    logger.info(
        "resposta_triagem_persistida | acao=registrar_resposta "
        "id_resposta=%s id_conversa=%s id_etapa=%s resposta=%s "
        "id_historico_cliente=%s inserido=%s",
        resultado[0],
        id_conversa,
        id_etapa,
        resposta,
        id_historico_persistido,
        inserido,
    )

    return {
        "id_resposta_desafio": resultado[0],
        "resposta": resposta,
        "id_historico_mensagem_cliente": id_historico_persistido,
        "inserido": inserido,
    }
