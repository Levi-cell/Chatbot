import logging

from core.logging_config import short_value
from core.repositories.updates import marcar_mensagem_como_enviada


logger = logging.getLogger("worker.support")


def finalizar_mensagem_processada(
    mensagem,
    contexto_banco,
    lock_version,
    cursor,
):
    contexto_conversa = contexto_banco["conversa"]

    marcar_mensagem_como_enviada(mensagem["id_mensagem"], cursor)

    logger.info(
        "mensagem_processada | acao=marcar_sent id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s estado=%s lock_version=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        contexto_conversa["id_conversa"],
        contexto_conversa["estado"],
        lock_version,
    )
