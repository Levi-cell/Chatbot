"""DDL único compartilhado com a migração manual do deploy."""

import logging
from pathlib import Path

from core.database.deploy_database.transacao_deploy import transacao_deploy


def criar_estrutura_fireads():
    caminho = (
        Path(__file__).resolve().parents[3]
        / "deploy/migrations/20261007_fireads_chat_customizacao.sql"
    )
    script = caminho.read_text(encoding="utf-8")
    ddl = script.split("-- INICIO DDL FIREADS\n", 1)[1].split("-- FIM DDL FIREADS", 1)[
        0
    ]
    with transacao_deploy(
        "estrutura_fireads", logging.getLogger("db.fireads")
    ) as cursor:
        cursor.execute(ddl)
