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
    args = parser.parse_args()
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario()
    from utilitarios.fireAds.config_teste import URL_DASHBOARD
    from core.integrations.fireads.cliente import ClienteFireAds
    from core.integrations.fireads.contrato import localizar
    from workers.worker_flow.fireads import interpretar, PRAZO_ABERTURA_SEGUNDOS

    cliente = ClienteFireAds(
        URL_DASHBOARD, segundos=PRAZO_ABERTURA_SEGUNDOS, timeout_leitura=None,
    )
    fontes = {}
    try:
        for origem, aba in (
            ("google", "Leads Google Ads (NÃO EDITAR)"),
            ("meta", "[FIRE] Leads Ads Geral - 7.2"),
        ):
            inicio = time.monotonic()
            print(f"Consultando {origem}; prazo total compartilhado: {PRAZO_ABERTURA_SEGUNDOS}s...", flush=True)
            fontes[origem] = cliente.consultar(aba)
            telefone = "WhatsApp" if origem == "google" else "phone_number"
            encontrados = localizar(fontes[origem]["rows"], args.numero, telefone)
            campos = ("Nome", "Email", "Perfil/Faixa", "Data/Hora") if origem == "google" else (
                "full_name", "email", "para_quem", "created_time",
            )
            equivalentes = len({tuple(str(r.get(c) or "") for c in campos) for r in encontrados}) <= 1
            print(json.dumps({"aba": aba, "segundos": round(time.monotonic() - inicio, 2),
                              "registros": len(fontes[origem]["rows"]),
                              "correspondencias": len(encontrados),
                              "dados_e_data_iguais": equivalentes}, ensure_ascii=False), flush=True)
        decisao = interpretar(fontes["google"]["rows"], fontes["meta"]["rows"], args.numero, args.fuso)
        print(json.dumps({"simulacao_sem_gravacao": {
            k: decisao.get(k) for k in ("resultado", "origem", "motivo", "status_dependente")
        }}, ensure_ascii=False), flush=True)
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
