import logging

from core.database.deploy.transacao_deploy import transacao_deploy
from core.repositories.cache_control import CACHE_UNIDADES_NOME


logger = logging.getLogger("db.cache_control_setup")


def criar_cache_controle():
    with transacao_deploy("criar_cache_controle", logger) as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS chatbot.cache_controle (
                nome VARCHAR(100) PRIMARY KEY,
                versao BIGINT NOT NULL DEFAULT 1,
                atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)

        cursor.execute(
            """
            INSERT INTO chatbot.cache_controle (
                nome,
                versao,
                atualizado_em
            )
            VALUES (%s, 1, NOW())
            ON CONFLICT (nome) DO NOTHING;
            """,
            (CACHE_UNIDADES_NOME,),
        )

    logger.info("banco_setup_ok | acao=criar_cache_controle")
