import logging
import signal
from threading import Event

from core.logging_config import setup_logging
from workers.worker_followup.config import carregar_config


def main():
    setup_logging()
    config = carregar_config()
    logger = logging.getLogger("worker.followup.main")
    parar = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: parar.set())
    if not config.habilitado:
        logger.info("followup_desabilitado | nenhum_envio=true")
        return
    from workers.worker_followup.followup_worker import executar_worker

    logger.info(
        "followup_iniciado | lote=%s intervalo=%s lembretes_por_ciclo=1",
        config.lote,
        config.intervalo,
    )
    executar_worker(config, parar)
    logger.info("followup_encerrado")


if __name__ == "__main__":
    main()
