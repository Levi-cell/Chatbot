"""Executa continuamente os ciclos de publicacao de leads no Funil."""

import logging
from workers.worker_funil.fireads import processar_lote
import time

import psycopg

from core.database.connection_aws import get_conn
from core.repositories.funil.envios import (
    reivindicar_proximo_envio,
    sincronizar_envios_elegiveis,
)
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.worker_funil.config import (
    FUNIL_INTERVALO_SEGUNDOS,
    FUNIL_LEASE_SEGUNDOS,
    FUNIL_LIMITE_POR_CICLO,
)
from workers.worker_funil.processamento import processar_envio_funil


logger = logging.getLogger("worker.funil")


def funil_worker():
    """Mantem o Funil ativo e recupera falhas operacionais esperadas."""
    logger.info(
        "funil_worker_iniciado | intervalo_segundos=%s limite_por_ciclo=%s",
        FUNIL_INTERVALO_SEGUNDOS,
        FUNIL_LIMITE_POR_CICLO,
    )
    retry_conexao = 5

    while True:
        try:
            logger.info("funil_ciclo_iniciando")
            resumo = executar_ciclo_funil()
            retry_conexao = 5

            logger.info(
                "funil_ciclo_concluido | acao=aguardar_proximo "
                "materializados=%s processados=%s enviados=%s falhas=%s "
                "limite_por_ciclo=%s aguardar=%ss",
                resumo["materializados"],
                resumo["processados"],
                resumo["enviados"],
                resumo["falhas"],
                FUNIL_LIMITE_POR_CICLO,
                FUNIL_INTERVALO_SEGUNDOS,
            )
            print("PROXIMO CICLO EM 30 MINUTOS")
            time.sleep(FUNIL_INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            logger.info("funil_worker_interrompido | acao=encerrar")
            raise

        except psycopg.OperationalError as erro:
            # Falha esperada: o proprio worker aguarda e abre uma nova conexao.
            retry_conexao = handle_erro_conexao(
                erro,
                retry_conexao,
                incremento_retry=5,
            )


def executar_ciclo_funil():
    """Materializa e processa um lote; cada reserva é commitada isoladamente."""
    conn = None
    cursor = None
    resumo = {
        "materializados": 0,
        "processados": 0,
        "enviados": 0,
        "falhas": 0,
    }

    try:
        conn = get_conn(application_name="worker_funil")
        cursor = conn.cursor()

        resumo["materializados"] = sincronizar_envios_elegiveis(
            cursor,
            limite=FUNIL_LIMITE_POR_CICLO,
        )
        conn.commit()

        for _ in range(FUNIL_LIMITE_POR_CICLO):
            envio = reivindicar_proximo_envio(
                cursor,
                lease_segundos=FUNIL_LEASE_SEGUNDOS,
            )
            conn.commit()

            if envio is None:
                break

            resumo["processados"] += 1
            if processar_envio_funil(envio, conn, cursor):
                resumo["enviados"] += 1
            else:
                resumo["falhas"] += 1
            print("---------------PROXIMO ENVIO------------------")

        # Fila independente: tentativas de dashboard não dependem de haver
        # novos leads elegíveis ao Funil neste ciclo.
        resumo['dash'] = processar_lote(conn, cursor, FUNIL_LIMITE_POR_CICLO)
        logger.info('dash_ciclo | %s', resumo['dash'])
        return resumo

    except Exception:
        if conn:
            conn.rollback()
        raise

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()
