import logging

import requests

from core.integrations.whatsapp.tools.config import get_token_usuario_meta
from core.logging_config import setup_logging, short_value


setup_logging()
logger = logging.getLogger("whatsapp.waba")


def ativar_waba_id(waba_id):
    url = f"https://graph.facebook.com/v25.0/{waba_id}/subscribed_apps"

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers)

    logger.info(
        "whatsapp_waba_subscribe_resposta | acao=subscribe_apps waba_id=%s status=%s resposta=%s",
        short_value(waba_id),
        response.status_code,
        response.json(),
    )

    return response.status_code, response.json()
