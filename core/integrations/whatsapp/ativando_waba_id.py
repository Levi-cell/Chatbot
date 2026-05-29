import logging

import requests

from core.logging_config import setup_logging, short_value


setup_logging()
logger = logging.getLogger("whatsapp.waba")

ACCESS_TOKEN = "EAATYGW2lhwgBQ4NNpLFVOzkhBCfH7SeWuus3RkF47cq9ldlK7QnU9UHhYZAH9xfWlOnf6p3sbbZAZC179mGXxiS6ZBLRt0EU5bWPrkjLOsjP1mAWVrPR8xadDOnEOWDuyhD0SFhojrOpqcKoo68NzqNdtJMGNqdoKEAZCGP1xdD1EMVn6J2CY86XZCWe30HQZDZD"
WABA_ID = "1898271867454270"

url = f"https://graph.facebook.com/v25.0/{WABA_ID}/subscribed_apps"

headers = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Content-Type": "application/json",
}

response = requests.post(url, headers=headers)

logger.info(
    "whatsapp_waba_subscribe_resposta | acao=subscribe_apps waba_id=%s status=%s resposta=%s",
    short_value(WABA_ID),
    response.status_code,
    response.json(),
)
