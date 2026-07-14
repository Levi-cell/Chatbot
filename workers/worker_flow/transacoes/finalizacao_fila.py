import logging

from core.cache.runtime.cache_conversas_bloqueadas import (
    registrar_bloqueio_conversa_cache,
)
from core.logging_config import short_value
from core.repositories.atendimento.fila import marcar_mensagem_como_enviada
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

    resultado_encerramento = aplicar_encerramento_se_necessario(
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
        resultado_encerramento["atendimento_encerrado"],
    )

    return resultado_encerramento


def registrar_cache_bloqueio_apos_commit(
    mensagem,
    resultado_encerramento,
):
    """Materializa no Redis somente bloqueios já confirmados no banco."""
    if not resultado_encerramento.get("atendimento_encerrado"):
        return False

    bloqueio_dias = int(
        resultado_encerramento.get("bloqueio_dias") or 0
    )

    if bloqueio_dias <= 0:
        return False

    registrado = registrar_bloqueio_conversa_cache(
        mensagem["cliente_telefone"],
        mensagem["id_phone_unidade"],
        resultado_encerramento["finalizou_em"],
        bloqueio_dias,
    )

    logger.info(
        "cache_bloqueio_pos_commit | acao=registrar cliente=%s "
        "phone_number_id=%s bloqueio_dias=%s registrado=%s",
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        bloqueio_dias,
        registrado,
    )
    return registrado
