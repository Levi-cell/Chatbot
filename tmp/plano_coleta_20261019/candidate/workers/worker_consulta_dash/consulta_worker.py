"""Orquestra reservas duráveis e sinaliza a espera; não envia respostas nem muda etapas."""

import logging
import time

from core.database.connection_aws import get_conn
from core.integrations.whatsapp.pywa_functions.digitacao import indicar_digitacao
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
        inicio_reserva = time.monotonic()
        conn.commit()
        if reserva is None:
            return False
        logger.info("consulta_dash_iniciada | consulta=%s conversa=%s tentativa=%s",
                    reserva["id_consulta"], reserva["id_conversa"], reserva["versao"])
        mensagem = pendencias.buscar_mensagem_aguardando(reserva, cursor)
        conn.commit()
        if mensagem is not None:
            indicar_digitacao(
                mensagem["id_phone_unidade"], mensagem["id_hash"],
                id_mensagem=mensagem["id_mensagem"], id_conversa=reserva["id_conversa"],
            )
        # O indicador também consome o orçamento existente, sem reiniciar os 300s.
        reserva["restante"] = max(
            0.0, float(reserva["restante"]) - (time.monotonic() - inicio_reserva),
        )
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
