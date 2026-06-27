import logging

from core.logging_config import short_value


logger = logging.getLogger("db.updates")


def marcar_mensagem_como_enviada(id_mensagem, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET status = 'sent',
            processing_started_at = NULL,
            last_error = NULL
        WHERE id_mensagem = %s
    """, (id_mensagem,))
    logger.debug(
        "fila_update | acao=marcar_sent id_mensagem=%s linhas=%s",
        id_mensagem,
        cursor.rowcount,
    )


def vincular_mensagem_fila_a_conversa(id_mensagem, id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET id_conversa = %s
        WHERE id_mensagem = %s
          AND (
              id_conversa IS NULL
              OR id_conversa = %s
          );
    """, (id_conversa, id_mensagem, id_conversa))
    logger.debug(
        "fila_update | acao=vincular_conversa id_mensagem=%s id_conversa=%s linhas=%s",
        id_mensagem,
        id_conversa,
        cursor.rowcount,
    )
    return cursor.rowcount


def atualizar_conversa_mensagem_cliente(
    id_conversa,
    data_interacao,
    cursor,
):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar mensagem do cliente"
        )

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'cliente',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_mensagem_cliente id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com mensagem do cliente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_resposta_bot(
    id_conversa,
    id_etapa_resultante,
    data_interacao,
    cursor,
):
    if id_etapa_resultante is None:
        raise ValueError("id_etapa_resultante nao informado para atualizar conversa")

    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar resposta do bot"
        )

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = CASE
                WHEN id_etapa_atual IS NULL THEN %s
                ELSE GREATEST(id_etapa_atual, %s)
            END,
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s
          AND (
              (id_etapa_atual IS NULL AND %s = 1)
              OR
              (
                  id_etapa_atual IS NOT NULL
                  AND %s <= id_etapa_atual + 1
              )
          );
    """, (
        id_etapa_resultante,
        id_etapa_resultante,
        data_interacao,
        id_conversa,
        id_etapa_resultante,
        id_etapa_resultante,
    ))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot id_conversa=%s etapa=%s data_interacao=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot; conversa "
            "inexistente ou transicao de etapa invalida "
            f"(id_conversa={id_conversa}, etapa={id_etapa_resultante}, "
            f"linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_resposta_bot_sem_avancar(
    id_conversa,
    data_interacao,
    cursor,
):
    if data_interacao is None:
        raise ValueError(
            "data_interacao nao informada para registrar resposta do bot"
        )

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'bot',
            last_interaction_at = %s
        WHERE id_conversa = %s;
    """, (data_interacao, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot_sem_avancar id_conversa=%s data_interacao=%s linhas=%s",
        id_conversa,
        data_interacao,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot sem avancar etapa "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_nome_cliente_por_telefone(waid_telefone, nome, cursor):
    if not waid_telefone:
        raise ValueError("waid_telefone nao informado para atualizar nome do cliente")

    if not nome:
        raise ValueError("nome nao informado para atualizar cliente")

    cursor.execute("""
        UPDATE chatbot.cliente
        SET nome = %s
        WHERE waid_telefone = %s;
    """, (nome, waid_telefone))

    logger.debug(
        "cliente_update | acao=atualizar_nome telefone=%s linhas=%s",
        short_value(waid_telefone),
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Cliente nao foi atualizado com nome "
            f"(telefone={short_value(waid_telefone)}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def reagendar_mensagem_sem_erro(id_mensagem, cursor, delay_seconds=30):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET
            status = 'pending',
            next_attempt_at = NOW() + (%s * INTERVAL '1 second'),
            processing_started_at = NULL,
            retry_count = GREATEST(COALESCE(retry_count, 0) - 1, 0),
            last_error = NULL
        WHERE id_mensagem = %s;
    """, (delay_seconds, id_mensagem))
    logger.debug(
        "fila_update | acao=reagendar_sem_erro id_mensagem=%s delay=%s linhas=%s",
        id_mensagem,
        delay_seconds,
        cursor.rowcount,
    )
    return cursor.rowcount


def reagendar_mensagem(id_mensagem, erro, max_retry, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET
            status = 'pending',
            next_attempt_at = NOW() + INTERVAL '2 minutes',
            processing_started_at = NULL,
            last_error = %s
        WHERE id_mensagem = %s AND retry_count < %s;
    """, (str(erro), id_mensagem, max_retry))
    logger.debug(
        "fila_update | acao=reagendar_com_erro id_mensagem=%s max_retry=%s linhas=%s",
        id_mensagem,
        max_retry,
        cursor.rowcount,
    )
    return cursor.rowcount
