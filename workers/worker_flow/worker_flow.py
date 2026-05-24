import logging
import time

import psycopg2

from core.cache.cache_unidade import (
    UnidadeNaoEncontrada,
    # garantir_cache_unidades_se_necessario, # redundante
    obter_id_unidade_redis_ou_plsql,
)
from core.database.connection_aws import get_conn
from core.repositories.querys import (
    pegar_mensagens_da_fila,
    tentar_lock_conversa,
)
from core.repositories.updates import marcar_mensagem_como_enviada
from workers.tratamento_erro.erro_conexao import handle_erro_conexao
from workers.tratamento_erro.erro_generico import handle_erro_generico
from workers.tratamento_erro.unidade_nao_encontrada import handle_unidade_nao_encontrada
from workers.worker_flow.bloquear_conversa import tratar_conversa_bloqueada
from workers.worker_flow.suport_functions import (
    valida_cliente,
    valida_conversa,
)

logger = logging.getLogger("worker.flow")


def worker_flow():
    logger.info("worker_iniciado")

    max_retry = 3
    retry_delay = 5

    while True:
        conn_ciclo = None
        cursor_ciclo = None
        id_mensagem = None
        id_conversa = None
        estado = None

        try:
            conn_ciclo = get_conn()
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5

            # garantir_cache_unidades_se_necessario(cursor_ciclo) # redundante

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                logger.info("fila_vazia | aguardar=30s")
                time.sleep(30)
                continue

            (
                id_mensagem,
                cliente_telefone,
                conteudo_texto,
                tipo_mensagem,
                id_phone_unidade,
                unidade_telefone,
                data_recebimento,
                id_hash,
                retry_count,
            ) = registro

            logger.info(
                "mensagem_processando | id=%s cliente=%s unidade=%s tipo=%s retry=%s",
                id_mensagem,
                cliente_telefone,
                id_phone_unidade,
                tipo_mensagem,
                retry_count,
            )

            id_unidade = obter_id_unidade_redis_ou_plsql(id_phone_unidade, cursor_ciclo)

            ################## FLUXO DE CONVERSA

            id_cliente, inserido = valida_cliente(cliente_telefone, cursor_ciclo)

            id_conversa, estado = valida_conversa(id_cliente, id_unidade, inserido, cursor_ciclo)

            if estado == "bloqueada":
                tratar_conversa_bloqueada(
                    id_mensagem,
                    cliente_telefone,
                    id_phone_unidade,
                    id_conversa,
                    cursor_ciclo,
                )
                logger.info(f"Conversa está bloqueada: {id_conversa}")
                conn_ciclo.commit()
                continue

            lock_ok = tentar_lock_conversa(id_conversa, cursor_ciclo)
            conn_ciclo.commit()

            if not lock_ok:
                logger.info(f"Conversa em processamento: {id_conversa}")
                continue

            ################# FLUXO DE CONVERSA

            marcar_mensagem_como_enviada(id_mensagem, cursor_ciclo)
            conn_ciclo.commit()

            logger.info(
                "mensagem_processada | id=%s id_unidade=%s id_conversa=%s estado=%s",
                id_mensagem,
                id_unidade,
                id_conversa,
                estado,
            )

        except psycopg2.OperationalError as erro:
            logger.warning("banco_operacional_erro | erro=%s", erro)
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            logger.warning("unidade_nao_encontrada | id_mensagem=%s erro=%s", id_mensagem, erro)
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(cursor_ciclo, id_mensagem, erro)

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            logger.exception("mensagem_erro | id_mensagem=%s", id_mensagem)
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(cursor_ciclo, id_mensagem, erro, max_retry)

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    conn_ciclo.close()
                except Exception as erro:
                    logger.warning("conexao_fechar_falhou | erro=%s", erro)
