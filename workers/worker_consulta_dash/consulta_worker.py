"""Orquestra reservas duráveis. Não cria conversas, não muda etapas e não envia WhatsApp."""

import logging
import time

from core.database.connection_aws import get_conn
from core.repositories.fireads import pendencias
from workers.worker_consulta_dash.consulta import consultar

logger = logging.getLogger("worker.consulta_dash")
INTERVALO_OCIOSO_SEGUNDOS = 2


def executar_ciclo():
    """Uma consulta por ciclo, com conexão sem transação aberta durante o HTTP."""
    conn = None
    reserva = None
    try:
        conn = get_conn(application_name="worker_consulta_dash", connect_timeout=5)
        cursor = conn.cursor()
        pendencias.expirar(cursor)
        conn.commit()
        reserva = pendencias.reservar(cursor)
        conn.commit()
        if reserva is None:
            return False
        logger.info("consulta_dash_iniciada | consulta=%s conversa=%s tentativa=%s",
                    reserva["id_consulta"], reserva["id_conversa"], reserva["versao"])
        resultado = consultar(reserva)
        gravado = pendencias.concluir(reserva, resultado, cursor)
        # Se o orçamento terminou durante a chamada, persistir o timeout também
        # sem depender de um novo ciclo do worker de atendimento.
        pendencias.expirar(cursor)
        conn.commit()
        logger.info("consulta_dash_finalizada | consulta=%s resultado=%s confirmado=%s",
                    reserva["id_consulta"], resultado["decisao"]["resultado"], gravado)
        return True
    except Exception:
        if conn is not None and not conn.closed:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            try:
                if reserva is not None and not conn.closed:
                    pendencias.liberar_reserva(reserva["id_consulta"], conn.cursor())
                    conn.commit()
            finally:
                # Mesmo falha no unlock não deixa uma sessão reutilizável com lock.
                conn.close()


def consulta_worker():
    while True:
        if not executar_ciclo():
            time.sleep(INTERVALO_OCIOSO_SEGUNDOS)
