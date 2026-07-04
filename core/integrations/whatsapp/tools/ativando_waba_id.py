import logging

import requests

from core.integrations.whatsapp.tools.config import (
    get_token_usuario_meta,
    get_waba_id,
)
from core.logging_config import setup_logging, short_value


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


def _imprimir_resultado(status, resposta):
    sucesso = (
        200 <= status < 300
        and resposta.get("success") is True
    )
    resultado = "SUCESSO" if sucesso else "FALHA"
    print(
        f"[{resultado}] status={status} resposta={resposta}"
    )



# if __name__ == "__main__":
#     setup_logging()
#     status_http, resposta_meta = ativar_waba_id(get_waba_id())
#     _imprimir_resultado(status_http, resposta_meta)

