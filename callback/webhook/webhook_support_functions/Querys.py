import logging
from Database.connectionAWS import get_conn

logger = logging.getLogger(__name__)

def buscar_timestamp_mensagem(id_hash):
    conn = None
    try:

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT received_data_hora
            FROM chatbot.fila_mensagens
            WHERE id_hash_msg = %s
        """, (id_hash,))

        resultado = cursor.fetchone()

        if not resultado:
            logger.warning(f"Mensagem não encontrada")
            return None

        timestamp = resultado[0]

        logger.info(f"Timestamp encontrado: {timestamp}")
        return None

    except Exception:
        logger.error("Erro ao buscar timestamp", exc_info=True)
        return None

    finally:
        if conn:
            conn.close()

def pegar_unidades_webhook(cursor):
    cursor.execute("""
        SELECT phone_number_id, id_unidade
        FROM chatbot.unidade
        WHERE status_ativo = TRUE
    """)

    resultado = {row[0]: row[1] for row in cursor.fetchall()}

    print(f"📦 Cache de unidades carregado: {len(resultado)} unidades")

    return resultado
