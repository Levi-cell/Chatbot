import logging
import time

import psycopg2

from core.cache.cache_cliente import salvar_cliente_cache
from core.cache.cache_unidade import (
    UnidadeNaoEncontrada,
    # garantir_cache_unidades_se_necessario, # redundante
    obter_id_unidade_redis_ou_plsql,
)
from core.database.connection_aws import get_conn
from core.logging_config import short_value
from core.repositories.querys import (
    existe_mensagem_anterior_aberta_conversa,
    pegar_mensagens_da_fila,
    tentar_lock_conversa,
    unlock_conversa,
)
from core.repositories.updates import (
    marcar_mensagem_como_enviada,
    reagendar_mensagem_sem_erro,
    vincular_mensagem_a_conversa,
)
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
    i = 0

    while True:
        i = i + 1
        logger.info("---------- ciclo_worker_inicio | numero=%s ----------", i)

        conn_ciclo = None
        cursor_ciclo = None
        id_mensagem = None
        id_cliente = None
        id_conversa = None
        estado = None
        lock_ok = False
        lock_version = None
        cliente_telefone = None
        id_phone_unidade = None
        tipo_mensagem = None
        cliente_cache_pendente = False

        try:
            conn_ciclo = get_conn()
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5
            logger.debug("ciclo_conexao_banco_ok | ciclo=%s acao=dequeue", i)

            # garantir_cache_unidades_se_necessario(cursor_ciclo) # redundante

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                logger.debug("fila_vazia | ciclo=%s acao=aguardar segundos=30", i)
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
                "mensagem_processando | ciclo=%s acao=iniciar id_mensagem=%s cliente=%s phone_number_id=%s tipo=%s retry=%s",
                i,
                id_mensagem,
                short_value(cliente_telefone),
                short_value(id_phone_unidade),
                tipo_mensagem,
                retry_count,
            )

            id_unidade = obter_id_unidade_redis_ou_plsql(id_phone_unidade, cursor_ciclo)
            logger.debug(
                "unidade_resolvida | ciclo=%s acao=continuar phone_number_id=%s id_unidade=%s",
                i,
                short_value(id_phone_unidade),
                id_unidade,
            )

            ################## FLUXO DE CONVERSA

            id_cliente, inserido, cliente_cache_pendente = valida_cliente(
                cliente_telefone,
                cursor_ciclo,
            )

            id_conversa, estado, etapa = valida_conversa(
                id_cliente,
                id_unidade,
                inserido,
                cursor_ciclo,
            )

            vincular_mensagem_a_conversa(id_mensagem, id_conversa, cursor_ciclo)
            conn_ciclo.commit()
            logger.debug(
                "mensagem_conversa_vinculada | ciclo=%s acao=commit id_mensagem=%s id_conversa=%s estado=%s",
                i,
                id_mensagem,
                id_conversa,
                estado,
            )

            if cliente_cache_pendente:
                salvar_cliente_cache(cliente_telefone, id_cliente)
                cliente_cache_pendente = False
                logger.debug(
                    "cliente_cache_confirmado | ciclo=%s acao=salvar cliente=%s id_cliente=%s",
                    i,
                    short_value(cliente_telefone),
                    id_cliente,
                )

            if estado == "bloqueada":
                tratar_conversa_bloqueada(
                    id_mensagem,
                    cliente_telefone,
                    id_phone_unidade,
                    id_conversa,
                    cursor_ciclo,
                )
                conn_ciclo.commit()
                continue

            lock_ok, lock_version = tentar_lock_conversa(id_conversa, cursor_ciclo)
            conn_ciclo.commit()

            if not lock_ok:
                logger.info(
                    "conversa_lock_recusado | ciclo=%s motivo=conversa_em_processamento acao=continuar id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s",
                    i,
                    id_mensagem,
                    short_value(cliente_telefone),
                    short_value(id_phone_unidade),
                    id_unidade,
                    id_conversa,
                )
                continue

            if existe_mensagem_anterior_aberta_conversa(
                id_conversa,
                id_mensagem,
                data_recebimento,
                cursor_ciclo,
            ):
                reagendar_mensagem_sem_erro(id_mensagem, cursor_ciclo, delay_seconds=30)
                conn_ciclo.commit()

                logger.info(
                    "mensagem_reagendada | ciclo=%s motivo=mensagem_anterior_aberta acao=aguardar_ordem id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s lock_version=%s",
                    i,
                    id_mensagem,
                    short_value(cliente_telefone),
                    short_value(id_phone_unidade),
                    id_conversa,
                    lock_version,
                )
                continue

            # valida historico

            ################# FLUXO DE CONVERSA

            marcar_mensagem_como_enviada(id_mensagem, cursor_ciclo)
            conn_ciclo.commit()

            logger.info(
                "mensagem_processada | ciclo=%s acao=marcar_sent id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s estado=%s lock_version=%s",
                i,
                id_mensagem,
                short_value(cliente_telefone),
                short_value(id_phone_unidade),
                id_unidade,
                id_conversa,
                estado,
                lock_version,
            )

        except psycopg2.OperationalError as erro:
            logger.warning(
                "banco_operacional_erro | ciclo=%s acao=retry_conexao id_mensagem=%s erro=%s",
                i,
                id_mensagem,
                erro,
            )
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            logger.warning(
                "unidade_nao_encontrada | ciclo=%s acao=tratar_unidade_invalida id_mensagem=%s cliente=%s phone_number_id=%s erro=%s",
                i,
                id_mensagem,
                short_value(cliente_telefone),
                short_value(id_phone_unidade),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(cursor_ciclo, id_mensagem, erro)

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            logger.exception(
                "mensagem_erro | ciclo=%s acao=tratar_erro_generico id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s estado=%s erro=%s",
                i,
                id_mensagem,
                short_value(cliente_telefone),
                short_value(id_phone_unidade),
                id_conversa,
                estado,
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(cursor_ciclo, id_mensagem, erro, max_retry)

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    if lock_ok and id_conversa and lock_version is not None:
                        unlock_realizado = unlock_conversa(
                            id_conversa,
                            lock_version,
                            cursor_ciclo,
                        )
                        conn_ciclo.commit()

                        logger.debug(
                            "conversa_unlock | ciclo=%s acao=liberar id_conversa=%s lock_version=%s liberada=%s",
                            i,
                            id_conversa,
                            lock_version,
                            unlock_realizado,
                        )

                    conn_ciclo.close()
                except Exception as erro:
                    logger.warning("finalizacao_ciclo_falhou | ciclo=%s erro=%s", i, erro)
