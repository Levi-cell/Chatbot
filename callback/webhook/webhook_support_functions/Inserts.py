from Database.connectionAWS import cursor, conn
import logging

logger = logging.getLogger(__name__)

def inserir_dados_na_tabela(dados):
    try:
        if not dados or dados.get("erro"):
            logger.warning("Dados inválidos não inseridos")
            return False

        cursor.execute("""
            INSERT INTO chatbot.fila_mensagens (
                status,
                retry_count,
                next_attempt_at,
                processing_started_at,
                received_data_hora,
                cliente_telefone,
                conteudo_texto,
                tipo_mensagem,
                id_hash_msg,
                id_phone_unidade,
                unidade_telefone
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id_hash_msg) DO NOTHING
        """, (
            dados["status"],
            dados["retry_count"],
            dados["next_attempt_at"],
            dados["processing_started_at"],
            dados["received_data_hora"],
            dados["cliente_telefone"],
            dados["conteudo_texto"],
            dados["tipo_mensagem"],
            dados["id_hash_msg"],
            dados["id_phone_unidade"],
            dados["unidade_telefone"],
        ))

        conn.commit()

        if cursor.rowcount == 0:
            logger.info(f"Mensagem duplicada ignorada | id_msg={dados['id_hash_msg']}")
        else:
            logger.info(f"Insert fila OK | id_msg={dados['id_hash_msg']}")
        return True

    except Exception:
        conn.rollback()
        logger.error("Erro ao inserir dados na fila", exc_info=True)
        return False