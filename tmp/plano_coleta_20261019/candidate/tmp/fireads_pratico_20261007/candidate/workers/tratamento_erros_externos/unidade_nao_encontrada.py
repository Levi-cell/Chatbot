import logging
import time

from workers.tratamento_erros_externos.expection_process import tratar_unidade_nao_encontrada


logger = logging.getLogger("worker.erro")


def handle_unidade_nao_encontrada(cursor, id_mensagem, erro):
    try:
        if cursor:
            tratar_unidade_nao_encontrada(id_mensagem, erro, cursor)

    except Exception:
        logger.exception(
            "handler_unidade_falhou | acao=ignorar_handler id_mensagem=%s erro=%s",
            id_mensagem,
            erro,
        )

    time.sleep(2)
