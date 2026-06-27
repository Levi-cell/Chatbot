import logging

from core.repositories.querys import unlock_conversa


logger = logging.getLogger("worker.support")


def liberar_lock_conversa_se_necessario(cursor, estado_ciclo):
    if not (
        estado_ciclo["lock_ok"]
        and estado_ciclo["id_conversa"]
        and estado_ciclo["lock_version"] is not None
    ):
        return None

    unlock_realizado = unlock_conversa(
        estado_ciclo["id_conversa"],
        estado_ciclo["lock_version"],
        cursor,
    )

    logger.debug(
        "conversa_unlock | acao=liberar id_conversa=%s lock_version=%s liberada=%s",
        estado_ciclo["id_conversa"],
        estado_ciclo["lock_version"],
        unlock_realizado,
    )
    return unlock_realizado
