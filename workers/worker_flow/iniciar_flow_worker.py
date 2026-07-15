import logging
import time

from core.logging_config import setup_logging


setup_logging()

from workers.worker_flow.response_flow.flow_worker import worker_flow


logger = logging.getLogger("worker.main")


def inicia_worker_flow():
    while True:
        try:
            logger.info("worker_flow_iniciando")
            worker_flow()
        except Exception as exc:
            logger.exception(
                "worker_flow_morreu | reiniciar_em=5s erro=%s",
                exc,
            )
            time.sleep(5)



inicia_worker_flow()