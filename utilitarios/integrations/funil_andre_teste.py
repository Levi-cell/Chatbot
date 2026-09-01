"""Sonda manual para enviar um lead ao Funil de Santo André."""

import argparse
import json
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parents[2]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from core.integrations.funil.cliente import enviar_oportunidade
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from utilitarios.montar_lead_teste import (
    montar_dados_lead_teste_santo_andre,
)


# ============================================================
# CONFIGURAÇÃO DO FUNIL - SANTO ANDRÉ / JARDIM BELA VISTA
# ============================================================

NOME_WIDGET_SANTO_ANDRE = "SANTO ANDRÉ - JARDIM BELA VISTA"
WIDGET_SANTO_ANDRE = "Q74XP20240925181741"

LINK_API_SANTO_ANDRE = (
    "https://leads.funildevendas.com.br/apicarrossel/api/"
    "?W=Q74XP20240925181741"
)

CANAL_META_ADS = "113340"
HTTP_TIMEOUT = (10, 30)


# ============================================================
# PAYLOAD
# ============================================================

def montar_payload_oportunidade_teste():
    """Monta o payload fictício de Santo André sem executar o POST."""
    dados_lead = montar_dados_lead_teste_santo_andre()
    return montar_payload_oportunidade(dados_lead)


# ============================================================
# ENVIO
# ============================================================

def criar_oportunidade_teste(*, confirmar_envio_real=False):
    """Envia o lead de teste somente mediante confirmação explícita."""
    if confirmar_envio_real is not True:
        raise ValueError(
            "Passe confirmar_envio_real=True para inserir "
            "o lead de teste no CRM."
        )

    return enviar_oportunidade(
        link_api_carrossel=LINK_API_SANTO_ANDRE,
        codigo_canal_venda=CANAL_META_ADS,
        payload=montar_payload_oportunidade_teste(),
        timeout=HTTP_TIMEOUT,
    )


# ============================================================
# AUXILIAR
# ============================================================

def _imprimir_resultado(resultado):
    print(
        json.dumps(
            resultado,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )


# ============================================================
# CLI
# ============================================================

def criar_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Envia um lead de teste para o Funil da unidade "
            "Santo André - Jardim Bela Vista."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="comando",
        required=True,
    )

    subparsers.add_parser(
        "payload",
        help="Mostra o payload sem enviar o lead.",
    )

    envio = subparsers.add_parser(
        "send-test",
        help="Envia o lead de teste para Santo André.",
    )

    envio.add_argument(
        "--confirm-real-send",
        action="store_true",
        help="Confirma o envio real para o CRM.",
    )

    return parser


# ============================================================
# MAIN
# ============================================================

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        argv = ["send-test", "--confirm-real-send"]

    parser = criar_parser()
    args = parser.parse_args(argv)

    try:
        if args.comando == "payload":
            _imprimir_resultado(montar_payload_oportunidade_teste())
            return 0

        if not args.confirm_real_send:
            parser.error("send-test exige --confirm-real-send")

        resultado = criar_oportunidade_teste(
            confirmar_envio_real=True
        )
        _imprimir_resultado(resultado)
        return 0
    except (
        requests.RequestException,
        RuntimeError,
        ValueError,
    ) as exc:
        print(
            f"FUNIL_ANDRE_FALHOU: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
