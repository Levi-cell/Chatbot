import logging

from pywa.types import Button

from core.integrations.whatsapp.tools.conta import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.pywa")

# URL dev webhook: https://gladys-tetrarchic-dovie.ngrok-free.dev/webhook


def enviar_mensagem_texto(to, text, phone_id_unidade):
    cliente_wa = conta_wa(phone_id_unidade)

    sent_message = cliente_wa.send_message(
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


def enviar_mensagem_texto_com_botao(
    to,
    text,
    titulo_botao,
    phone_id_unidade,
    callback_data=None,
):
    cliente_wa = conta_wa(phone_id_unidade)
    dados_callback = callback_data or titulo_botao

    sent_message = cliente_wa.send_message(
        to=to,
        text=text,
        buttons=[
            Button(
                title=titulo_botao,
                callback_data=dados_callback,
            )
        ],
    )

    id_hash_msg = _extrair_id_mensagem_enviada(sent_message)

    logger.info(
        "whatsapp_mensagem_enviada | acao=enviar tipo=interactive_button to=%s id_hash_msg=%s botao=%s",
        short_value(to),
        id_hash_msg,
        titulo_botao,
    )

    return id_hash_msg


def _extrair_id_mensagem_enviada(sent_message):
    id_hash_msg = getattr(sent_message, "id", None)

    if not id_hash_msg:
        raise ValueError("PyWa nao retornou id da mensagem enviada")

    return id_hash_msg
