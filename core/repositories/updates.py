import logging


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
