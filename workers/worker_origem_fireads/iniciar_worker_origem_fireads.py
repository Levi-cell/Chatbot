"""Supervisor com encerramento gracioso e intervalo de duas horas."""

import logging
import signal
from threading import Event

from core.logging_config import setup_logging
from .config import INTERVALO_SEGUNDOS, configuracao
from .origem_worker import executar_ciclo


def iniciar_worker_origem_fireads():
    setup_logging()
    logger = logging.getLogger('worker.origem_fireads.supervisor')
    desde = configuracao()
    if desde is None:
        logger.info('origem_desativado | configuracao=FIREADS_ORIGEM_ATIVO')
        return
    parar = Event()
    for sinal in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sinal, lambda *_: parar.set())
    logger.info('origem_iniciado | desde=%s intervalo=%s', desde.isoformat(), INTERVALO_SEGUNDOS)
    while not parar.is_set():
        try:
            executar_ciclo(desde, parar=parar)
        except Exception as erro:
            logger.error('origem_ciclo_falhou | tipo=%s', type(erro).__name__)
        parar.wait(INTERVALO_SEGUNDOS)
    logger.info('origem_encerrado')


if __name__ == '__main__':
    iniciar_worker_origem_fireads()
