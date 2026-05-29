
import logging

import requests


logger = logging.getLogger("whatsapp.registro")


def registrar_numero_whatsapp(phone_number_id, pin="123456"):
    TOKEN_USUARIO_META = "EAATYGW2lhwgBQ4NNpLFVOzkhBCfH7SeWuus3RkF47cq9ldlK7QnU9UHhYZAH9xfWlOnf6p3sbbZAZC179mGXxiS6ZBLRt0EU5bWPrkjLOsjP1mAWVrPR8xadDOnEOWDuyhD0SFhojrOpqcKoo68NzqNdtJMGNqdoKEAZCGP1xdD1EMVn6J2CY86XZCWe30HQZDZD"
    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/register"

    headers = {
        "Authorization": f"Bearer {TOKEN_USUARIO_META}",
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
