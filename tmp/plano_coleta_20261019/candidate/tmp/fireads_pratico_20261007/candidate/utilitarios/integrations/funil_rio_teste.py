"""Sonda manual para enviar um lead de teste ao Funil do Rio Vermelho."""

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
    montar_dados_lead_teste_rio_vermelho,
)


# ============================================================
# CONFIGURAÇÃO DO FUNIL - SALVADOR / RIO VERMELHO
# ============================================================

WIDGET_RIO_VERMELHO = "CHXJ020240923185012"

LINK_API_RIO_VERMELHO = (
    "https://leads.funildevendas.com.br/apicarrossel/api/"
    "?W=CHXJ020240923185012"
)

# Mantendo o canal que você já estava utilizando.
CANAL_META_ADS = "113340"

HTTP_TIMEOUT = (10, 30)


# ============================================================
# PAYLOAD
# ============================================================

def montar_payload_oportunidade_teste():
    """
    Monta o payload utilizando o lead fictício
    definido em utilitarios.montar_lead_teste.
    """

    dados_lead = montar_dados_lead_teste_rio_vermelho()

    return montar_payload_oportunidade(dados_lead)


# ============================================================
# ENVIO
# ============================================================

def criar_oportunidade_teste(*, confirmar_envio_real=False):
    """
    Envia o lead de teste para o Funil do Rio Vermelho.

    O envio só acontece se confirmar_envio_real=True.
    """

    if confirmar_envio_real is not True:
        raise ValueError(
            "Passe confirmar_envio_real=True para inserir "
            "o lead de teste no CRM."
        )

    payload = montar_payload_oportunidade_teste()

    return enviar_oportunidade(
        link_api_carrossel=LINK_API_RIO_VERMELHO,
        codigo_canal_venda=CANAL_META_ADS,
        payload=payload,
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
            "Envia um lead de teste para o Funil "
            "da unidade Salvador - Rio Vermelho."
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
        help="Envia o lead de teste para o Rio Vermelho.",
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
    parser = criar_parser()

    args = parser.parse_args(argv)

    try:

        if args.comando == "payload":
            payload = montar_payload_oportunidade_teste()

            _imprimir_resultado(payload)

            return 0

        if args.comando == "send-test":

            if not args.confirm_real_send:
                parser.error(
                    "send-test exige --confirm-real-send"
                )

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
            f"FUNIL_RIO_FALHOU: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(main())
