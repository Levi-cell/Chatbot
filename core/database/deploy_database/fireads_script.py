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
        novo = caminho.with_name("20261009_worker_consulta_dash.sql").read_text(
            encoding="utf-8"
        )
        cursor.execute(
            novo.split("-- INICIO DDL CONSULTA DASH\n", 1)[1].split(
                "-- FIM DDL CONSULTA DASH", 1
            )[0]
        )
        geral = caminho.with_name("20261014_fireads_aba_geral.sql").read_text(encoding="utf-8")
        cursor.execute(geral.split("-- INICIO DDL FIREADS ABA GERAL\n", 1)[1].split(
            "-- FIM DDL FIREADS ABA GERAL", 1
        )[0])
        coleta = caminho.with_name('20261019_coleta_abertura.sql').read_text(encoding='utf-8')
        cursor.execute(coleta.split('-- INICIO DDL COLETA ABERTURA\n', 1)[1].split(
            '-- FIM DDL COLETA ABERTURA', 1)[0])
        turno = caminho.with_name('20261021_chat_fire_turno_coleta.sql').read_text(encoding='utf-8')
        cursor.execute(turno.split('-- INICIO DDL CHAT FIRE TURNO\n', 1)[1].split(
            '-- FIM DDL CHAT FIRE TURNO', 1)[0])
