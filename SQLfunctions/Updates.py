from Database.connectionAWS import cursor


def marcar_mensagem_como_enviada(id_mensagem):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET status = 'sent',
            last_error = NULL
        WHERE id_mensagem = %s
    """, (id_mensagem,))

def reagendar_mensagem(id_mensagem, erro, max_retry):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET 
            status = 'pending',
            next_attempt_at = NOW() + INTERVAL '2 minutes',
            last_error = %s
        WHERE id_mensagem = %s AND retry_count < %s;
    """, (str(erro), id_mensagem, max_retry))
    return cursor.rowcount