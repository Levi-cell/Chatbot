from contextlib import contextmanager

from core.database.connection_aws import get_conn


APPLICATION_NAME_DEPLOY = "script_chatbot"


@contextmanager
def transacao_deploy(acao, logger):
    """Entrega um cursor e garante commit, rollback, fechamento e propagação."""
    conn = None

    try:
        conn = get_conn(application_name=APPLICATION_NAME_DEPLOY)
        cursor = conn.cursor()
        yield cursor
        conn.commit()

    except Exception as erro:
        if conn:
            conn.rollback()

        logger.exception(
            "banco_setup_erro | acao=%s erro=%s",
            acao,
            erro,
        )
        raise

    finally:
        if conn:
            conn.close()
