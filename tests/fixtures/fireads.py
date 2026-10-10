"""Migração real nas bases PostgreSQL descartáveis da suíte."""

from pathlib import Path

MIGRACAO_FIREADS = (
    Path(__file__).resolve().parents[2]
    / "deploy/migrations/20261007_fireads_chat_customizacao.sql"
)


def aplicar_fireads(cursor):
    """Usa o DDL do deploy, preservando a transação controlada pelo teste."""
    texto = MIGRACAO_FIREADS.read_text(encoding="utf-8")
    ddl = texto.split("-- INICIO DDL FIREADS\n", 1)[1].split("-- FIM DDL FIREADS", 1)[0]
    cursor.execute(ddl)

    novo = MIGRACAO_FIREADS.with_name("20261009_worker_consulta_dash.sql").read_text(
        encoding="utf-8"
    )
    cursor.execute(
        novo.split("-- INICIO DDL CONSULTA DASH\n", 1)[1].split(
            "-- FIM DDL CONSULTA DASH", 1
        )[0]
    )
