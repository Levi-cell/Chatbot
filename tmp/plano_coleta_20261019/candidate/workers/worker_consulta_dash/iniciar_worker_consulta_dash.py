"""Ponto de entrada do serviço periódico de consulta FireAds."""

import logging
import time

from core.logging_config import setup_logging
from workers.worker_consulta_dash.consulta_worker import consulta_worker

logger = logging.getLogger("worker.consulta_dash.supervisor")


def iniciar_worker_consulta_dash():
    setup_logging()
    while True:
        try:
            logger.info("consulta_dash_worker_iniciado")
            consulta_worker()
        except KeyboardInterrupt:
            raise
        except Exception as erro:
            # Mensagens SQL/HTTP podem expor entradas; o tipo basta para este log.
            logger.error("consulta_dash_worker_falhou | tipo=%s reiniciar_em=5s",
                         type(erro).__name__)
            time.sleep(5)


if __name__ == "__main__":
    iniciar_worker_consulta_dash()
