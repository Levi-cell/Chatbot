import logging

import psycopg2

from core.config_env import env_int, env_required


logger = logging.getLogger("db.connection")

setup = {
    "host": env_required("DB_HOST"),
    "database": env_required("DB_NAME"),
    "user": env_required("DB_USER"),
    "password": env_required("DB_PASSWORD"),
    "port": env_int("DB_PORT", 5432),
}


def get_conn(application_name=None):
    connect_kwargs = dict(setup)

    if application_name:
        connect_kwargs["application_name"] = application_name

    conn = psycopg2.connect(**connect_kwargs)
    logger.debug(
        "banco_conexao_aberta | acao=connect host=%s database=%s user=%s application_name=%s",
        setup["host"],
        setup["database"],
        setup["user"],
        application_name,
    )
    return conn

# conn.close automaticamente fecha qualquer cursor associado a ela.
# Se fizer conn.close, nao precisa fazer cursor.close.
