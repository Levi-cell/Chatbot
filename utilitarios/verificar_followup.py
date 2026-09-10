"""Diagnóstico somente leitura. Não adquire lock de conversa nem envia mensagens."""

import json

from core.database.connection_aws import get_conn
from core.repositories.atendimento.followup import consultar_diagnostico


def main():
    with get_conn(application_name="verificar_followup", connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            diagnostico = consultar_diagnostico(cursor)
    print(json.dumps(diagnostico, ensure_ascii=False))
    if diagnostico["stages_negativos"] or diagnostico["horarios_futuros"]:
        raise SystemExit("REVISAR_ANOMALIAS_ANTES_DE_ATIVAR")
    print("FOLLOWUP_CONSULTA_OK_SEM_ENVIO")


if __name__ == "__main__":
    main()
