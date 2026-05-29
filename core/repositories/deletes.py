import logging


logger = logging.getLogger("db.deletes")


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
