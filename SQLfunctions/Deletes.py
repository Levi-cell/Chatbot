def deletar_mensagem_por_id(id_mensagem, cursor):
    """Remove uma linha da fila pelo id (ex.: unidade órfã, sem retry)."""
    cursor.execute("""
        DELETE FROM chatbot.fila_mensagens
        WHERE id_mensagem = %s;
    """, (id_mensagem,))
    return cursor.rowcount


def deletar_mensagem_se_max_retry(id_mensagem, max_retry, cursor):
    cursor.execute("""
        DELETE FROM chatbot.fila_mensagens 
        WHERE id_mensagem = %s AND retry_count >= %s;
    """, (id_mensagem, max_retry))
    return cursor.rowcount