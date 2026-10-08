import logging


logger = logging.getLogger("db.atendimento.fila")


def pegar_mensagens_da_fila(cursor):
    cursor.execute("SELECT * FROM chatbot.dequeue_message();")
    registro = cursor.fetchone()
    if registro:
        logger.debug(
            "fila_dequeue | acao=reservar id_mensagem=%s",
            registro[0],
        )
    return registro


def existe_mensagem_anterior_aberta_atendimento(
    cliente_telefone,
    id_phone_unidade,
    id_mensagem_atual,
    received_data_hora,
    cursor,
):
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM chatbot.fila_mensagens
            WHERE cliente_telefone = %s
              AND id_phone_unidade = %s
              AND id_mensagem <> %s
              AND status IN ('pending', 'processing')
              AND (
                  received_data_hora < %s
                  OR (
                      received_data_hora = %s
                      AND id_mensagem < %s
                  )
              )
            LIMIT 1
        );
    """, (
        cliente_telefone,
        id_phone_unidade,
        id_mensagem_atual,
        received_data_hora,
        received_data_hora,
        id_mensagem_atual,
    ))

    resultado = bool(cursor.fetchone()[0])
    logger.debug(
        "fila_ordem_consultada | acao=verificar_anterior "
        "cliente=%s phone_number_id=%s id_mensagem=%s existe_anterior=%s",
        cliente_telefone,
        id_phone_unidade,
        id_mensagem_atual,
        resultado,
    )
    return resultado


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


def vincular_mensagem_fila_a_conversa(
    id_mensagem,
    id_conversa,
    cursor,
):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET id_conversa = %s
        WHERE id_mensagem = %s
          AND status = 'processing'
          AND (
              id_conversa IS NULL
              OR id_conversa = %s
          );
    """, (id_conversa, id_mensagem, id_conversa))

    linhas = cursor.rowcount
    vinculo_reparado = False

    if linhas == 0:
        cursor.execute("""
            UPDATE chatbot.fila_mensagens AS fila
            SET id_conversa = %s
            WHERE fila.id_mensagem = %s
              AND fila.status = 'processing'
              AND fila.id_conversa IS DISTINCT FROM %s
              AND NOT EXISTS (
                  SELECT 1
                  FROM chatbot.historico_mensagens AS historico
                  WHERE historico.id_mensagem_fila = fila.id_mensagem
              );
        """, (id_conversa, id_mensagem, id_conversa))
        linhas = cursor.rowcount
        vinculo_reparado = linhas == 1

        if vinculo_reparado:
            logger.warning(
                "fila_vinculo_reparado | "
                "motivo=vinculo_legado_sem_historico "
                "id_mensagem=%s id_conversa=%s",
                id_mensagem,
                id_conversa,
            )

    logger.debug(
        "fila_update | acao=vincular_conversa id_mensagem=%s "
        "id_conversa=%s linhas=%s vinculo_reparado=%s",
        id_mensagem,
        id_conversa,
        linhas,
        vinculo_reparado,
    )
    return linhas


def reagendar_mensagem_sem_erro(
    id_mensagem,
    cursor,
    delay_seconds=30,
):
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


def deletar_mensagem_por_id(id_mensagem, cursor):
    """Remove uma linha da fila pelo id."""
    cursor.execute("""
        DELETE FROM chatbot.fila_mensagens
        WHERE id_mensagem = %s;
    """, (id_mensagem,))
    logger.debug(
        "fila_delete | acao=delete_por_id id_mensagem=%s linhas=%s",
        id_mensagem,
        cursor.rowcount,
    )
    return cursor.rowcount


def deletar_mensagem_se_max_retry(id_mensagem, max_retry, cursor):
    cursor.execute("""
        DELETE FROM chatbot.fila_mensagens
        WHERE id_mensagem = %s AND retry_count >= %s;
    """, (id_mensagem, max_retry))
    logger.debug(
        "fila_delete | acao=delete_max_retry id_mensagem=%s max_retry=%s linhas=%s",
        id_mensagem,
        max_retry,
        cursor.rowcount,
    )
    return cursor.rowcount
