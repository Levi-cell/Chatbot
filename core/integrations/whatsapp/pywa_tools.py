import logging

from pywa import WhatsApp
from pywa.types.templates import TemplateLanguage

from core.logging_config import short_value


logger = logging.getLogger("whatsapp.pywa")

# URL dev webhook: https://gladys-tetrarchic-dovie.ngrok-free.dev/webhook/
TOKEN = "EAATYGW2lhwgBQ4NNpLFVOzkhBCfH7SeWuus3RkF47cq9ldlK7QnU9UHhYZAH9xfWlOnf6p3sbbZAZC179mGXxiS6ZBLRt0EU5bWPrkjLOsjP1mAWVrPR8xadDOnEOWDuyhD0SFhojrOpqcKoo68NzqNdtJMGNqdoKEAZCGP1xdD1EMVn6J2CY86XZCWe30HQZDZD"
PHONE_NUMBER_ID = "954435134428733"


wa = WhatsApp(
    token=TOKEN,
    phone_id=PHONE_NUMBER_ID,
)


def enviar_mensagem_texto(to, text, client=None):
    cliente = client or wa

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


def enviar_template(to, name, language="en_US", client=None):
    cliente = client or wa

    sent_message = cliente.send_template(
        to=to,
        name=name,
        language=TemplateLanguage(language),
    )

    id_hash_msg = _extrair_id_mensagem_enviada(sent_message)

    logger.info(
        "whatsapp_template_enviado | acao=enviar_template template=%s language=%s to=%s id_hash_msg=%s",
        name,
        language,
        short_value(to),
        id_hash_msg,
    )

    return id_hash_msg


def bloquear_usuario_meta(wa_id_cliente, phone_id_unidade, client=None):
    cliente = client or wa

    resultado = cliente.block_users(
        users=[str(wa_id_cliente)],
        phone_id=str(phone_id_unidade),
    )

    erros = getattr(resultado, "errors", None)
    if erros:
        raise RuntimeError(f"PyWa retornou erro ao bloquear usuario: {erros}")

    logger.warning(
        "whatsapp_usuario_bloqueado | acao=bloquear wa_id_cliente=%s phone_id_unidade=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
    )

    return resultado


def desbloquear_usuario_meta(wa_id_cliente, phone_id_unidade, client=None):
    cliente = client or wa

    resultado = cliente.unblock_users(
        users=[str(wa_id_cliente)],
        phone_id=str(phone_id_unidade),
    )

    erros = getattr(resultado, "errors", None)
    if erros:
        raise RuntimeError(f"PyWa retornou erro ao desbloquear usuario: {erros}")

    logger.warning(
        "whatsapp_usuario_desbloqueado | acao=desbloquear wa_id_cliente=%s phone_id_unidade=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
    )

    return resultado


def _extrair_id_mensagem_enviada(sent_message):
    id_hash_msg = getattr(sent_message, "id", None)

    if not id_hash_msg:
        raise ValueError("PyWa nao retornou id da mensagem enviada")

    return id_hash_msg
