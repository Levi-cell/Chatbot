"""Entrypoint seguro do worker periódico de Funil."""

import logging

from core.logging_config import setup_logging
from workers.worker_funil.config import (
    FUNIL_WORKER_ENABLED,
    validar_configuracao_funil,
)
from workers.worker_funil.funil_worker import worker_funil


setup_logging()
logger = logging.getLogger("worker.funil.main")


def inicia_worker_funil():
    if not FUNIL_WORKER_ENABLED:
        logger.warning(
            "funil_worker_desativado | acao=nao_iniciar "
            "configuracao=FUNIL_WORKER_ENABLED"
        )
        return

    validar_configuracao_funil()
    logger.info("funil_worker_iniciando")
    worker_funil()


if __name__ == "__main__":
    inicia_worker_funil()
