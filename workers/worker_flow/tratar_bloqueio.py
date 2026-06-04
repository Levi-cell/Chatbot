import logging

from core.cache.cache_conversas_bloqueadas import registrar_bloqueio_conversa_cache
from core.logging_config import short_value
from core.repositories.deletes import deletar_mensagem_por_id
from core.repositories.querys import buscar_finalizou_em_conversa


logger = logging.getLogger("worker.bloqueio")


def tratar_conversa_bloqueada(
    id_mensagem,
    cliente_telefone,
    id_phone_unidade,
    id_conversa,
    cursor,
):
    finalizou_em = buscar_finalizou_em_conversa(id_conversa, cursor)

    registrar_bloqueio_conversa_cache(
        cliente_telefone,
        id_phone_unidade,
        finalizou_em,
    )

    deletadas = deletar_mensagem_por_id(id_mensagem, cursor)

    logger.info(
        "mensagem_ignorada | motivo=conversa_bloqueada acao=registrar_cache_remover_fila id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s finalizou_em=%s removida=%s",
        id_mensagem,
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
        id_conversa,
        finalizou_em,
        deletadas,
    )
