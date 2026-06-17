import logging

from core.integrations.whatsapp.tools.conta import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.block")


def bloquear_usuario_meta(wa_id_cliente, phone_id_unidade):
    cliente_wa = conta_wa(phone_id_unidade)

    resultado = cliente_wa.block_users(
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


def desbloquear_usuario_meta(wa_id_cliente, phone_id_unidade):
    cliente_wa = conta_wa(phone_id_unidade)

    resultado = cliente_wa.unblock_users(
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
