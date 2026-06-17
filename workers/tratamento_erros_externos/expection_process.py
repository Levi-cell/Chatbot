import logging

from core.repositories.deletes import deletar_mensagem_por_id, deletar_mensagem_se_max_retry
from core.repositories.updates import reagendar_mensagem


logger = logging.getLogger("worker.erro")


def tratar_erro_processamento(id_mensagem, erro, max_retry, cursor):
    logger.error(
        "mensagem_processamento_erro | acao=avaliar_retry id_mensagem=%s erro=%s",
        id_mensagem,
        erro,
    )

    if id_mensagem is None:
        logger.warning("mensagem_sem_id | acao=ignorar")
        return "no_action"

    linhas_deletadas = deletar_mensagem_se_max_retry(id_mensagem, max_retry, cursor)

    if linhas_deletadas > 0:
        logger.warning(
            "mensagem_removida | motivo=max_retry acao=delete id_mensagem=%s",
            id_mensagem,
        )
        return "delete"

    linhas_reagendadas = reagendar_mensagem(id_mensagem, erro, max_retry, cursor)

    if linhas_reagendadas > 0:
        logger.info(
            "mensagem_reagendada | motivo=erro_processamento acao=retry id_mensagem=%s",
            id_mensagem,
        )
        return "retry"

    logger.info("mensagem_sem_alteracao | motivo=retry_indisponivel acao=ignorar id_mensagem=%s", id_mensagem)
    return "no_action"


def tratar_unidade_nao_encontrada(id_mensagem, erro, cursor):
    logger.warning(
        "unidade_invalida | acao=remover_fila id_mensagem=%s erro=%s",
        id_mensagem,
        erro,
    )

    if id_mensagem is None:
        return "no_action"

    deletadas = deletar_mensagem_por_id(id_mensagem, cursor)

    if deletadas:
        logger.warning(
            "mensagem_removida | motivo=unidade_invalida acao=delete id_mensagem=%s",
            id_mensagem,
        )
        return "delete"

    logger.info("mensagem_ja_removida | motivo=unidade_invalida acao=ignorar id_mensagem=%s", id_mensagem)
    return "no_action"
