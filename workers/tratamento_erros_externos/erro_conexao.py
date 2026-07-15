import logging
import time


logger = logging.getLogger("worker.erro")


def handle_erro_conexao(
    erro,
    retry_delay,
    *,
    incremento_retry=None,
    limite_retry=60,
):
    """Aguarda uma reconexao e calcula o proximo intervalo.

    O worker de atendimento preserva o backoff exponencial historico. O
    worker do Funil informa ``incremento_retry=5`` para usar 5, 10, 15...
    sem duplicar o tratamento compartilhado de indisponibilidade do banco.
    """
    logger.warning(
        "banco_indisponivel | acao=aguardar_retry retry_em=%ss erro=%s",
        retry_delay,
        erro,
    )
    time.sleep(retry_delay)

    if incremento_retry is not None:
        return min(retry_delay + incremento_retry, limite_retry)

    return min(retry_delay * 2, limite_retry)
