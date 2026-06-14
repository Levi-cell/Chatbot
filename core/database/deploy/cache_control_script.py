import logging

from core.database.connection_aws import get_conn
from core.repositories.cache_control import (
    criar_tabela_cache_controle_sql,
    garantir_linha_cache_unidades,
)


logger = logging.getLogger("db.cache_control_setup")


def criar_cache_controle():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        criar_tabela_cache_controle_sql(cursor)
        garantir_linha_cache_unidades(cursor)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_cache_controle")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=criar_cache_controle erro=%s", erro)

    finally:
        if conn:
            conn.close()
