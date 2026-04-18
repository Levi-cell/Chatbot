import logging
from Database.connectionAWS import cursor

logger = logging.getLogger(__name__)

def buscar_timestamp_mensagem(id_hash):
    try:
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