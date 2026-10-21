"""Supervisor com espera interrompível e encerramento gracioso pelo systemd."""

import logging
import signal
from threading import Event

from core.logging_config import setup_logging
from .config import CONSUMO_META_ENABLED, CONSUMO_META_CICLO_SEGUNDOS, validar_configuracao
from .consumo_worker import executar_ciclo_consumo


def iniciar_worker_consumo_meta():
    setup_logging()
    logger = logging.getLogger("worker.consumo_meta.supervisor")
    validar_configuracao()
    if not CONSUMO_META_ENABLED:
        logger.warning("consumo_meta_desativado | configuracao=CONSUMO_META_ENABLED")
        return
    parar = Event()
    for sinal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sinal, lambda *_: parar.set())
    while not parar.is_set():
        try:
            resumo = executar_ciclo_consumo(parar=parar)
            logger.info("consumo_meta_ciclo | coletados=%s falhas=%s ocupado=%s",
                        resumo["coletados"], resumo["falhas"], resumo["ocupado"])
        except Exception as erro:
            logger.error("consumo_meta_ciclo_falhou | tipo=%s", type(erro).__name__)
        parar.wait(CONSUMO_META_CICLO_SEGUNDOS)
    logger.info("consumo_meta_encerrado")


if __name__ == "__main__":
    iniciar_worker_consumo_meta()
