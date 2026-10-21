"""Mede a consulta inicial por telefone, sem alterar banco, cache ou dashboard."""

import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("numero")
    parser.add_argument("--fuso", default=None)
    parser.add_argument("--segundos", type=float, default=300)
    args = parser.parse_args()
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario()
    from utilitarios.fireAds.config_teste import URL_DASHBOARD
    from core.integrations.fireads.cliente import ClienteFireAds
    from core.integrations.fireads.contrato import ABA_DESTINO, localizar
    from workers.worker_consulta_dash.resultado import interpretar

    cliente = ClienteFireAds(
        URL_DASHBOARD, segundos=args.segundos, timeout_leitura=None,
    )
    try:
        inicio = time.monotonic()
        print(f"Consultando aba geral; prazo: {args.segundos}s...", flush=True)
        fonte = cliente.consultar(ABA_DESTINO)
        encontrados = localizar(fonte["rows"], args.numero, "WhatsApp", incluir_equivalentes=True)
        print(json.dumps({"aba": ABA_DESTINO, "segundos": round(time.monotonic() - inicio, 2),
                          "registros": len(fonte["rows"]), "correspondencias": len(encontrados)},
                         ensure_ascii=False), flush=True)
        decisao = interpretar(fonte["rows"], args.numero, args.fuso, aba=ABA_DESTINO)
        print(json.dumps({"simulacao_sem_gravacao": {
            k: decisao.get(k) for k in ("resultado", "origem", "motivo", "status_dependente")
        }}, ensure_ascii=False), flush=True)
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
