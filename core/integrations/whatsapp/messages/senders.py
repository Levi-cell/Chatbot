import logging

from core.integrations.whatsapp.tools.conta import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.pywa")

# URL dev webhook: https://gladys-tetrarchic-dovie.ngrok-free.dev/webhook


def enviar_mensagem_texto(to, text, phone_id_unidade, client_mock=None):
    cliente = _obter_cliente_whatsapp(phone_id_unidade, client_mock)

    sent_message = cliente.send_message(
        to=to,
        text=text,
    )

    id_hash_msg = _extrair_id_mensagem_enviada(sent_message)

    logger.info(
        "whatsapp_mensagem_enviada | acao=enviar tipo=text to=%s id_hash_msg=%s",
        short_value(to),
        id_hash_msg,
    )

    return id_hash_msg


def _obter_cliente_whatsapp(phone_id_unidade, client_mock=None):
    # client_mock existe apenas para testes; em producao sempre monta o WhatsApp da unidade.
    if client_mock:
        return client_mock

    return conta_wa(phone_id_unidade)


def _extrair_id_mensagem_enviada(sent_message):
    id_hash_msg = getattr(sent_message, "id", None)

    if not id_hash_msg:
        raise ValueError("PyWa nao retornou id da mensagem enviada")

    return id_hash_msg
