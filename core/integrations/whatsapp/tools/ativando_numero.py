
import logging

import requests

from core.integrations.whatsapp.tools.config import get_token_usuario_meta


logger = logging.getLogger("whatsapp.registro")


def registrar_numero_whatsapp(phone_number_id, pin="123456"):
    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/register"

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json"
    }

    payload = {
        "messaging_product": "whatsapp",
        "pin": pin
    }

    response = requests.post(url, headers=headers, json=payload)
    logger.info(
        "whatsapp_numero_registro_resposta | acao=registrar_numero phone_number_id=%s status=%s",
        phone_number_id,
        response.status_code,
    )

    return response.status_code, response.json()
