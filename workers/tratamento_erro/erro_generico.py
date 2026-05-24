import logging
import time

from workers.tratamento_erro.expection_process import tratar_erro_processamento


logger = logging.getLogger("worker.erro")


def handle_erro_generico(cursor, id_mensagem, erro, max_retry):
    try:
        if cursor:
            tratar_erro_processamento(id_mensagem, erro, max_retry, cursor)

    except Exception:
        logger.exception("handler_generico_falhou | id_mensagem=%s", id_mensagem)

    time.sleep(2)
