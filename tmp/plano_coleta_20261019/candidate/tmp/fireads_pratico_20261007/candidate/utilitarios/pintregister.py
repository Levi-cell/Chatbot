"""Altera conscientemente o PIN de registro de um número na Meta."""

import argparse
import sys
from pathlib import Path

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def alterar_pin(phone_number_id, *, session=requests):
    """Envia à Meta o PIN configurado no ambiente, sem expor seu valor."""
    phone_number_id = _validar_phone_number_id(phone_number_id)

    from core.integrations.whatsapp.tools.config import (
        construir_url_graph_api,
        get_meta_http_timeout,
        get_phone_registration_pin,
        get_token_usuario_meta,
    )

    try:
        response = session.post(
            construir_url_graph_api(phone_number_id),
            headers={
                "Authorization": f"Bearer {get_token_usuario_meta()}",
                "Content-Type": "application/json",
            },
            json={"pin": get_phone_registration_pin()},
            timeout=get_meta_http_timeout(),
        )
    except requests.RequestException as exc:
        raise RuntimeError("Falha HTTP ao alterar o PIN na Meta") from exc

    if not response.ok:
        try:
            dados_erro = response.json()
            erro = dados_erro.get("error", {})

            detalhes = (
                f"message={erro.get('message')!r}, "
                f"type={erro.get('type')!r}, "
                f"code={erro.get('code')!r}, "
                f"error_subcode={erro.get('error_subcode')!r}, "
                f"fbtrace_id={erro.get('fbtrace_id')!r}"
            )
        except ValueError:
            detalhes = "resposta da Meta não contém JSON válido"

        raise RuntimeError(
            f"A Meta recusou a alteração do PIN "
            f"(HTTP {response.status_code}): {detalhes}"
        )


    try:
        dados = response.json()
    except ValueError as exc:
        raise RuntimeError("A Meta não retornou um JSON válido") from exc
    if not isinstance(dados, dict) or dados.get("success") is not True:
        raise RuntimeError("A Meta não confirmou a alteração do PIN")
    return response.status_code, True


def _validar_phone_number_id(valor):
    phone_number_id = str(valor or "").strip()
    if not phone_number_id:
        raise ValueError("phone_number_id não informado")
    if not phone_number_id.isascii() or not phone_number_id.isdecimal():
        raise ValueError("phone_number_id deve conter somente dígitos ASCII")
    return phone_number_id


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Altera o PIN de registro configurado na Meta.",
    )
    parser.add_argument("--phone-number-id", required=True)
    parser.add_argument(
        "--confirm-phone-number-id",
        required=True,
        help="repita exatamente o alvo para confirmar a operação",
    )
    parser.add_argument(
        "--confirm-real-change",
        action="store_true",
        help="confirma o POST real e mutante para a Meta",
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
    parser = criar_parser()
    args = parser.parse_args(argv)
    try:
        alvo = _validar_phone_number_id(args.phone_number_id)
    except ValueError as exc:
        parser.error(str(exc))

    if args.confirm_phone_number_id.strip() != alvo:
        parser.error("a confirmação do phone number ID não coincide")
    if not args.confirm_real_change:
        parser.error("a alteração exige --confirm-real-change")

    try:
        from utilitarios.bootstrap import configurar_ambiente_utilitario

        configurar_ambiente_utilitario(args.env_file)
        status, sucesso = alterar_pin(alvo)
        print(f"ALTERAR_PIN_META_OK status={status} sucesso={sucesso}")
        return 0
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(
            f"ALTERAR_PIN_META_FALHOU: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

if __name__ == "__main__":
    raise SystemExit(
        main([
            "--phone-number-id",
            "1238343616032627",
            "--confirm-phone-number-id",
            "1238343616032627",
            "--confirm-real-change",
        ])
    )




