import logging

from core.cache.runtime.cache_conversas_bloqueadas import registrar_bloqueio_conversa_cache
from core.logging_config import short_value
from core.repositories.atendimento.fila import deletar_mensagem_por_id
from core.repositories.fluxo.politicas import (
    buscar_bloqueio_conversa_por_id,
)


logger = logging.getLogger("worker.bloqueio")


def tratar_conversa_bloqueada(
    id_mensagem,
    cliente_telefone,
    id_phone_unidade,
    id_conversa,
    cursor,
):
    bloqueio = buscar_bloqueio_conversa_por_id(id_conversa, cursor)

    if bloqueio is None:
        raise ValueError(
            "Conversa classificada como bloqueada sem política de bloqueio "
            f"(id_conversa={id_conversa})"
        )

    registrar_bloqueio_conversa_cache(
        cliente_telefone,
        id_phone_unidade,
        bloqueio.finalizou_em,
        bloqueio.bloqueio_dias,
    )

    deletadas = deletar_mensagem_por_id(id_mensagem, cursor)

    logger.info(
        "mensagem_ignorada | motivo=conversa_bloqueada acao=registrar_cache_remover_fila id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s finalizou_em=%s bloqueio_dias=%s removida=%s",
        id_mensagem,
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
        id_conversa,
        bloqueio.finalizou_em,
        bloqueio.bloqueio_dias,
        deletadas,
    )
