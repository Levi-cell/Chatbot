import logging

import requests

from core.integrations.whatsapp.tools.config import (
    construir_url_graph_api,
    get_meta_http_timeout,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.registro")


def desregistrar_numero_whatsapp(phone_number_id):
    url = construir_url_graph_api(f"{phone_number_id}/deregister")

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        url,
        headers=headers,
        timeout=get_meta_http_timeout(),
    )
    logger.info(
        "whatsapp_numero_desregistro_resposta | acao=desregistrar_numero phone_number_id=%s status=%s",
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
