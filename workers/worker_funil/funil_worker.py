"""Loop periódico, reservas e supervisão do envio de leads ao Funil."""

import logging
import time

from core.database.connection_aws import get_conn
from core.repositories.funil.envios import (
    reivindicar_proximo_envio,
    sincronizar_envios_elegiveis,
)
from workers.worker_funil.config import (
    FUNIL_INTERVALO_SEGUNDOS,
    FUNIL_LEASE_SEGUNDOS,
    FUNIL_LIMITE_POR_CICLO,
)
from workers.worker_funil.processamento import processar_envio_funil


logger = logging.getLogger("worker.funil")


def worker_funil():
    """Executa imediatamente e repete a varredura a cada intervalo configurado."""
    retry_conexao = 5

    while True:
        try:
            resumo = executar_ciclo_funil()
            retry_conexao = 5
            logger.info(
                "funil_ciclo_concluido | acao=aguardar_proximo "
                "materializados=%s processados=%s enviados=%s falhas=%s "
                "aguardar=%ss",
                resumo["materializados"],
                resumo["processados"],
                resumo["enviados"],
                resumo["falhas"],
                FUNIL_INTERVALO_SEGUNDOS,
            )
            time.sleep(FUNIL_INTERVALO_SEGUNDOS)

        except KeyboardInterrupt:
            logger.info("funil_worker_interrompido | acao=encerrar")
            raise

        except Exception as exc:
            logger.exception(
                "funil_ciclo_falhou | acao=reiniciar "
                "reiniciar_em=%ss erro=%s",
                retry_conexao,
                exc,
            )
            time.sleep(retry_conexao)
            retry_conexao = min(retry_conexao + 5, 60)


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

