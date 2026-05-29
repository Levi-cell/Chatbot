import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.connection_test")


def connection_teste_psql():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT version();")
        version = cursor.fetchone()

        logger.info(
            "banco_conexao_ok | acao=healthcheck versao=%s",
            version[0] if version else "-",
        )

    except Exception as erro:
        logger.exception("banco_conexao_erro | acao=healthcheck erro=%s", erro)
        raise

    finally:
        if conn:
            conn.close()

