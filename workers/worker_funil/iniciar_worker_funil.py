"""Reinicia o processo do Funil quando uma falha critica escapa do worker."""

import logging
import time

from core.logging_config import setup_logging
from workers.worker_funil.config import (
    FUNIL_WORKER_ENABLED,
    validar_configuracao_funil,
)
from workers.worker_funil.funil_worker import funil_worker


setup_logging()
logger = logging.getLogger("worker.funil.supervisor")


def iniciar_worker_funil():
    if not FUNIL_WORKER_ENABLED:
        logger.warning(
            "funil_worker_desativado | acao=nao_iniciar "
            "configuracao=FUNIL_WORKER_ENABLED"
        )
        return

    validar_configuracao_funil()

    while True:
        try:
            logger.info("funil_worker_iniciando")
            funil_worker()

        except KeyboardInterrupt:
            logger.info("funil_supervisor_interrompido | acao=encerrar")
            raise

        except Exception as exc:
            logger.exception(
                "funil_worker_morreu | acao=reiniciar_processo "
                "reiniciar_em=5s erro=%s",
                exc,
            )
            time.sleep(5)



