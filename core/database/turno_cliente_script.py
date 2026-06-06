import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.turno_cliente_setup")


def criar_indices_turno_cliente():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute("""
            DROP INDEX IF EXISTS chatbot.uq_fila_cliente_unidade_aberta;

            CREATE INDEX IF NOT EXISTS idx_fila_cliente_unidade_aberta
            ON chatbot.fila_mensagens (
                cliente_telefone,
                id_phone_unidade,
                status,
                received_data_hora,
                id_mensagem
            )
            WHERE status IN ('pending', 'processing');

            CREATE INDEX IF NOT EXISTS idx_fila_cliente_unidade_conversa_aberta
            ON chatbot.fila_mensagens (
                cliente_telefone,
                id_phone_unidade,
                id_conversa,
                id_hash_msg,
                id_mensagem
            )
            WHERE status IN ('pending', 'processing');
        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_indices_turno_cliente")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "banco_setup_erro | acao=criar_indices_turno_cliente erro=%s",
            erro,
        )

    finally:
        if conn:
            conn.close()
