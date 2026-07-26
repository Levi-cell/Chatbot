import logging

import requests

from core.integrations.whatsapp.tools.config import (
    get_meta_http_timeout,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.waba")


def desativar_waba_id(waba_id):
    """Remove a assinatura do App atual da WABA recebida."""
    waba_id = str(waba_id or "").strip()

    if not waba_id:
        raise ValueError("waba_id nao informado para desativacao")

    url = f"https://graph.facebook.com/v25.0/{waba_id}/subscribed_apps"

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    response = requests.delete(
        url,
        headers=headers,
        timeout=get_meta_http_timeout(),
    )

    logger.info(
        "whatsapp_waba_unsubscribe_resposta | "
        "acao=unsubscribe_apps waba_id=%s status=%s",
        short_value(waba_id),
        response.status_code,
    )

    return response.status_code, _normalizar_resposta(response)


def _normalizar_resposta(response):
    try:
        dados = response.json()

        if isinstance(dados, dict):
            return dados

        return {
            "success": response.ok,
            "data": dados,
        }

    except ValueError:
        return {
            "success": response.ok,
            "text": response.text,
        }


def _imprimir_resultado(status, resposta):
    sucesso = (
        200 <= status < 300
        and resposta.get("success") is True
    )
    resultado = "SUCESSO" if sucesso else "FALHA"
    print(
        f"[{resultado}] status={status} resposta={resposta}"
    )
