import logging

import requests

from core.integrations.whatsapp.tools.config import get_token_usuario_meta


logger = logging.getLogger("whatsapp.registro")


def desregistrar_numero_whatsapp(phone_number_id):
    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/deregister"

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers)
    logger.info(
        "whatsapp_numero_desregistro_resposta | acao=desregistrar_numero phone_number_id=%s status=%s",
        phone_number_id,
        response.status_code,
    )

    try:
        resposta = response.json()
    except ValueError:
        resposta = {"success": response.ok, "text": response.text}

    return response.status_code, resposta
