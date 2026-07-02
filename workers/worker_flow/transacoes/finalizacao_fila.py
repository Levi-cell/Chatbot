import logging

from core.logging_config import short_value
from core.repositories.updates import marcar_mensagem_como_enviada
from workers.worker_flow.transacoes.encerramento_atendimento import (
    aplicar_encerramento_se_necessario,
)


logger = logging.getLogger("worker.support")


def finalizar_mensagem_processada(
    mensagem,
    contexto_banco,
    lock_version,
    cursor,
    contexto_final=None,
):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]
    contexto_final = contexto_final or {}

    atendimento_encerrado = aplicar_encerramento_se_necessario(
        id_conversa,
        contexto_final.get("intencao_encerramento"),
        cursor,
    )

    marcar_mensagem_como_enviada(mensagem["id_mensagem"], cursor)

    logger.info(
        "mensagem_processada | acao=marcar_sent id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s estado=%s lock_version=%s atendimento_encerrado=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        id_conversa,
        contexto_conversa["estado"],
        lock_version,
        atendimento_encerrado,
    )
