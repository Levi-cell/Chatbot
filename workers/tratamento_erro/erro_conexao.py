import logging
import time


logger = logging.getLogger("worker.erro")


def handle_erro_conexao(erro, retry_delay):
    logger.warning(
        "banco_indisponivel | acao=aguardar_retry retry_em=%ss erro=%s",
        retry_delay,
        erro,
    )
    time.sleep(retry_delay)

    return min(retry_delay * 2, 60)
