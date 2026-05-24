import logging
import time

from core.logging_config import setup_logging


setup_logging()

from workers.worker_flow.worker_flow import worker_flow


logger = logging.getLogger("worker.main")


def inicia_flow_main():
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


if __name__ == "__main__":
    inicia_flow_main()
