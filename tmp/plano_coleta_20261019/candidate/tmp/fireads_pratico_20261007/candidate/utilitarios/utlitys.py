"""Consulta manual dos metadados de um número na Graph API da Meta."""

import argparse
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


CAMPOS_PHONE_META = (
    "id",
    "display_phone_number",
    "verified_name",
    "status",
    "code_verification_status",
    "quality_rating",
)


def consultar_phone_meta(phone_number_id, *, session=requests):
    """Consulta somente os campos operacionais esperados para o phone ID."""
    phone_number_id = _validar_phone_number_id(phone_number_id)

    from core.integrations.whatsapp.tools.config import (
        construir_url_graph_api,
        get_meta_http_timeout,
        get_token_usuario_meta,
    )

    try:
        response = session.get(
            construir_url_graph_api(phone_number_id),
            headers={
                "Authorization": f"Bearer {get_token_usuario_meta()}",
            },
            params={"fields": ",".join(CAMPOS_PHONE_META)},
            timeout=get_meta_http_timeout(),
        )
    except requests.RequestException as exc:
        raise RuntimeError("Falha HTTP ao consultar a Meta") from exc

    if not response.ok:
        raise RuntimeError(
            f"A Meta recusou a consulta (HTTP {response.status_code})"
        )

    try:
        dados = response.json()
    except ValueError as exc:
        raise RuntimeError("A Meta não retornou um JSON válido") from exc
    if not isinstance(dados, dict):
        raise RuntimeError("A Meta retornou uma estrutura inesperada")
    return {
        campo: dados.get(campo)
        for campo in CAMPOS_PHONE_META
    }


def _validar_phone_number_id(valor):
    phone_number_id = str(valor or "").strip()
    if not phone_number_id:
        raise ValueError("phone_number_id não informado")
    if not phone_number_id.isascii() or not phone_number_id.isdecimal():
        raise ValueError("phone_number_id deve conter somente dígitos ASCII")
    return phone_number_id


def _mascarar(valor):
    texto = str(valor or "")
    if len(texto) <= 7:
        return "*" * len(texto)
    return f"{texto[:4]}...{texto[-3:]}"


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Consulta um phone number ID na Graph API da Meta.",
    )
    parser.add_argument("--phone-number-id", required=True)
    parser.add_argument(
        "--mostrar-identificadores",
        action="store_true",
        help="exibe ID e telefone completos",
    )
    parser.add_argument(
        "--env-file",
        help=(
            "usa explicitamente este arquivo de ambiente; sem a opção, "
            "usa utilitarios/local_settings.py"
        ),
    )
    return parser


def main(argv=None):
    args = criar_parser().parse_args(argv)
    try:
        from utilitarios.bootstrap import configurar_ambiente_utilitario

        configurar_ambiente_utilitario(args.env_file)
        dados = consultar_phone_meta(args.phone_number_id)
        for campo, valor in dados.items():
            if (
                not args.mostrar_identificadores
                and campo in {"id", "display_phone_number"}
            ):
                valor = _mascarar(valor)
            print(f"{campo}: {valor}")
        return 0
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(
            f"CONSULTA_PHONE_META_FALHOU: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
