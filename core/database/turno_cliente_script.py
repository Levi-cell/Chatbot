import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.turno_cliente_setup")


def criar_indices_turno_cliente():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_fila_cliente_unidade_aberta
            ON chatbot.fila_mensagens (cliente_telefone, id_phone_unidade)
            WHERE status IN ('pending', 'processing');
        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_indices_turno_cliente")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=criar_indices_turno_cliente erro=%s", erro)

    finally:
        if conn:
            conn.close()
