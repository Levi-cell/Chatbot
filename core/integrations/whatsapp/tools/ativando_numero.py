
import logging

import requests

from core.integrations.whatsapp.tools.config import (
    construir_url_graph_api,
    get_meta_http_timeout,
    get_phone_registration_pin,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.registro")


def registrar_numero_whatsapp(phone_number_id, pin=None):
    url = construir_url_graph_api(f"{phone_number_id}/register")

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "pin": pin or get_phone_registration_pin(),
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=get_meta_http_timeout(),
    )
    logger.info(
        "whatsapp_numero_registro_resposta | acao=registrar_numero phone_number_id=%s status=%s",
        short_value(phone_number_id),
        response.status_code,
    )

    return response.status_code, _normalizar_resposta(response)


def _normalizar_resposta(response):
    try:
        return response.json()

    except ValueError:
        return {
            "success": response.ok,
            "text": response.text,
        }
