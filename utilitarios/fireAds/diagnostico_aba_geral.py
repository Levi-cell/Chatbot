"""Inspeciona o contrato da aba geral por GET, sem mostrar dados dos contatos."""

import json
from collections import Counter

from core.integrations.fireads.cliente import ClienteFireAds
from core.integrations.fireads.contrato import ABA_DESTINO
from utilitarios.fireAds.config_teste import URL_DASHBOARD


def main():
    cliente = ClienteFireAds(URL_DASHBOARD, segundos=120, timeout_leitura=None)
    try:
        dados = cliente.consultar(ABA_DESTINO)
        rows = dados["rows"]
        canais = Counter(str(row.get("Canal") or "").strip() for row in rows)
        por_canal = {}
        for canal in ("Google Ads", "Meta Ads", "Organico Site"):
            selecionados = [
                row for row in rows if str(row.get("Canal") or "").strip() == canal
            ]
            por_canal[canal] = {
                "registros": len(selecionados),
                "para_quem_preenchido": sum(
                    bool(str(row.get("Para quem é") or "").strip())
                    for row in selecionados
                ),
            }
        print(json.dumps({
            "aba": dados["aba"],
            "cabecalhos": dados["headers"],
            "registros": len(rows),
            "canais": dict(canais),
            "cobertura_destinatario": por_canal,
        }, ensure_ascii=False, indent=2))
    except Exception as erro:
        # Nunca despejar o corpo recebido, que pode conter dados pessoais.
        print(json.dumps({"erro": type(erro).__name__}, ensure_ascii=False))
    finally:
        cliente.close()


if __name__ == "__main__":
    main()
