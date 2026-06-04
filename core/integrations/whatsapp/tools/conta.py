from pywa import WhatsApp

from core.integrations.whatsapp.tools.config import TOKEN_USUARIO_META


def conta_wa(phone_id, token=TOKEN_USUARIO_META):
    phone_id = _normalizar_phone_id(phone_id)

    return WhatsApp(
        token=token,
        phone_id=phone_id,
    )


def _normalizar_phone_id(phone_id):
    if phone_id is None:
        raise ValueError("phone_id da unidade nao informado")

    phone_id = str(phone_id).strip()

    if not phone_id:
        raise ValueError("phone_id da unidade vazio")

    return phone_id
