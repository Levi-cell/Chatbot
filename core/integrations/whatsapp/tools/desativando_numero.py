import logging

import requests

from core.integrations.whatsapp.tools.config import (
    get_meta_http_timeout,
    get_phone_number_id_dev,
    get_token_usuario_meta,
)
from core.logging_config import setup_logging, short_value


logger = logging.getLogger("whatsapp.registro")


def desregistrar_numero_whatsapp(phone_number_id):
    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/deregister"

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
#     status_http, resposta_meta = desregistrar_numero_whatsapp(
#         get_phone_number_id_dev()
#     )
#     _imprimir_resultado(status_http, resposta_meta)
