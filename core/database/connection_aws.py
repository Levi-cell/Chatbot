import logging

import psycopg2


logger = logging.getLogger("db.connection")

setup = {
    "host": "chatbotdb.chi8soygomha.sa-east-1.rds.amazonaws.com",
    "database": "db_chatbot",
    "user": "fushi",
    "password": "fushi998874_",
    "port": "5432"
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

## conn.close automaticamente fecha qualquer cursor associado a ela,
# se fizer conn.close n precisa fazer cursor.close
