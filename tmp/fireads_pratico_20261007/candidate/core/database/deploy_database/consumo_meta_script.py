"""Reutiliza o DDL versionado tanto no setup vazio quanto na migração manual."""

from pathlib import Path


def criar_tabelas_consumo_meta(cursor):
    caminho = Path(__file__).resolve().parents[3] / "deploy/migrations/20260929_consumo_mensal_meta.sql"
    script = caminho.read_text(encoding="utf-8")
    # O chamador já controla a transação. Executar somente o DDL entre marcadores
    # evita um BEGIN/COMMIT interno confirmar outras operações do setup.
    ddl = script.split("-- INICIO DDL CONSUMO META\n", 1)[1].split("-- FIM DDL CONSUMO META", 1)[0]
    cursor.execute(ddl)
