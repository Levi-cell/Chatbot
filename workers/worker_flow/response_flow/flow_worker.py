import logging
from workers.worker_flow.fireads import preparar_abertura
from workers.worker_flow.suporte.consultas_fireads import ConsultaFireAdsPendente

import psycopg
from core.cache.cache_unidade import UnidadeNaoEncontrada
from core.repositories.unidades.consultas import (
    UnidadeDesativada,
    exigir_unidade_habilitada_por_phone_id,
)
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.logging_config import short_value
from core.repositories.atendimento.conversas import tentar_lock_conversa
from core.repositories.atendimento.followup import (
    LockConversaPerdido,
    proteger_conversa,
    reler_conversa,
)
from workers.worker_flow.response_flow.retomada_followup import (
    enviar_retorno_followup,
)
from workers.worker_flow.transacoes.retorno_followup import (
    preparar_retorno_followup,
    persistir_retorno_followup,
)
from core.repositories.atendimento.fila import (
    pegar_mensagens_da_fila,
    reagendar_mensagem_sem_erro,
    vincular_mensagem_fila_a_conversa,
)
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.tratamento_erros_externos.erro_generico import handle_erro_generico
from workers.tratamento_erros_externos.exceptions import BancoFalhouAposEnvioMeta
from workers.tratamento_erros_externos.unidade_nao_encontrada import (
    handle_unidade_nao_encontrada,
)
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.suporte.cache_repair import (
    confirmar_cache_cliente_se_pendente,
    reparar_cache_cliente_stale_se_fk_invalida,
    reparar_cache_unidade_stale_se_fk_invalida,
)
from workers.worker_flow.suporte.estado_ciclo import (
    aguardar_fila_vazia,
    atualizar_estado_com_contexto,
    atualizar_estado_com_mensagem,
    atualizar_estado_lock,
    criar_estado_ciclo,
    montar_mensagem_fila,
)
from workers.worker_flow.transacoes.finalizacao_fila import (
    finalizar_mensagem_processada,
    registrar_cache_bloqueio_apos_commit,
)
from workers.worker_flow.transacoes.lock_conversa import (
    liberar_lock_conversa_se_necessario,
)
from workers.worker_flow.transacoes.ordem_turno import (
    logar_lock_recusado,
    reagendar_se_houver_mensagem_anterior,
)
from workers.worker_flow.transacoes.persistencia_resposta import (
    atualizar_banco_com_contexto_final,
)
from workers.worker_flow.tratar_bloqueio import tratar_conversa_bloqueada
from workers.worker_flow.valida_banco import validar_banco_mensagem
from workers.worker_flow.valida_historico import valida_historico

logger = logging.getLogger("worker.response_flow")


def worker_flow():
    logger.info("worker_iniciado")

    max_retry = 3
    retry_delay = 5

    while True:
        print("\n\n\n---------------------NOVO CICLO---------------------\n\n\n")
        logger.info("---------- ciclo_worker_inicio ----------")

        conn_ciclo = None
        cursor_ciclo = None
        estado_ciclo = criar_estado_ciclo()
        contexto_envio = {}

        try:
            conn_ciclo = get_conn(application_name="worker_chatbot")
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5
            logger.debug("ciclo_conexao_banco_ok | acao=dequeue")

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                conn_ciclo.close()
                conn_ciclo = None
                cursor_ciclo = None
                aguardar_fila_vazia()
                continue

            mensagem = montar_mensagem_fila(registro)
            atualizar_estado_com_mensagem(estado_ciclo, mensagem)

            logger.info(
                "mensagem_processando | acao=iniciar id_mensagem=%s cliente=%s phone_number_id=%s tipo=%s retry=%s",
                mensagem["id_mensagem"],
                short_value(mensagem["cliente_telefone"]),
                short_value(mensagem["id_phone_unidade"]),
                mensagem["tipo_mensagem"],
                mensagem["retry_count"],
            )

            if reagendar_se_houver_mensagem_anterior(
                mensagem,
                cursor_ciclo,
            ):
                conn_ciclo.commit()
                continue

            exigir_unidade_habilitada_por_phone_id(mensagem["id_phone_unidade"], cursor_ciclo)
            contexto_banco = validar_banco_mensagem(
                mensagem,
                cursor_ciclo,
            )
            atualizar_estado_com_contexto(estado_ciclo, contexto_banco)

            contexto_conversa = contexto_banco["conversa"]
            id_conversa = contexto_conversa["id_conversa"]

            conn_ciclo.commit()
            logger.debug(
                "contexto_banco_confirmado | acao=commit id_mensagem=%s id_conversa_calculada=%s estado=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_conversa["estado"],
            )

            confirmar_cache_cliente_se_pendente(contexto_banco)

            if contexto_conversa["estado"] == "bloqueada":
                tratar_conversa_bloqueada(
                    mensagem["id_mensagem"],
                    mensagem["cliente_telefone"],
                    mensagem["id_phone_unidade"],
                    id_conversa,
                    cursor_ciclo,
                )
                conn_ciclo.commit()
                continue

            lock_ok, lock_version = tentar_lock_conversa(id_conversa, cursor_ciclo)
            conn_ciclo.commit()
            atualizar_estado_lock(estado_ciclo, lock_ok, lock_version)

            if not lock_ok:
                logar_lock_recusado(mensagem, contexto_banco)
                reagendar_mensagem_sem_erro(
                    mensagem["id_mensagem"],
                    cursor_ciclo,
                    delay_seconds=5,
                )
                conn_ciclo.commit()
                continue

            linhas_vinculadas = vincular_mensagem_fila_a_conversa(
                mensagem["id_mensagem"],
                id_conversa,
                cursor_ciclo,
            )

            if linhas_vinculadas == 0:
                logger.critical(
                    "mensagem_conversa_vinculo_inconsistente | "
                    "motivo=historico_conflitante_ou_fila_ausente "
                    "acao=reagendar_sem_consumir_retry id_mensagem=%s "
                    "cliente=%s phone_number_id=%s "
                    "id_conversa_calculada=%s",
                    mensagem["id_mensagem"],
                    short_value(mensagem["cliente_telefone"]),
                    short_value(mensagem["id_phone_unidade"]),
                    id_conversa,
                )
                reagendar_mensagem_sem_erro(
                    mensagem["id_mensagem"],
                    cursor_ciclo,
                    delay_seconds=300,
                )
                conn_ciclo.commit()
                continue

            contexto_banco = reler_conversa(contexto_banco, lock_version, cursor_ciclo)
            exigir_unidade_habilitada_por_phone_id(mensagem["id_phone_unidade"], cursor_ciclo)
            contexto_banco = preparar_abertura(
                contexto_banco, mensagem, lock_version, cursor_ciclo
            )
            contexto_conversa = contexto_banco["conversa"]
            contexto_historico = preparar_retorno_followup(
                mensagem,
                contexto_banco,
                cursor_ciclo,
            )
            if contexto_historico is None:
                contexto_historico = valida_historico(
                    mensagem, contexto_banco, cursor_ciclo
                )
            conn_ciclo.commit()
            logger.debug(
                "historico_contexto_ok | acao=commit id_mensagem=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s inserido=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_historico["id_etapa_cliente"],
                contexto_historico["id_etapa_resposta"],
                contexto_historico["mensagem_cliente_inserida"],
            )

            proteger_conversa(id_conversa, lock_version, cursor_ciclo, renovar=True)
            exigir_unidade_habilitada_por_phone_id(mensagem["id_phone_unidade"], cursor_ciclo)
            conn_ciclo.commit()
            if contexto_historico.get("retorno_followup"):
                contexto_envio = enviar_retorno_followup(contexto_historico)
            else:
                contexto_envio = flow_sender(contexto_historico)

            try:
                proteger_conversa(id_conversa, lock_version, cursor_ciclo)
                persistir = (
                    persistir_retorno_followup
                    if contexto_historico.get("retorno_followup")
                    else atualizar_banco_com_contexto_final
                )
                contexto_final = persistir(
                    contexto_historico, contexto_envio, cursor_ciclo
                )
                if contexto_historico.get("retorno_followup"):
                    # O retorno agora pode encerrar por idade ou finalizar o fluxo.
                    # Histórico, efeitos, stage=0, encerramento e fila são atômicos:
                    # um retry não pode encontrar um checkpoint concluído sem
                    # que o encerramento correspondente também esteja confirmado.
                    resultado_encerramento = finalizar_mensagem_processada(
                        mensagem,
                        contexto_banco,
                        lock_version,
                        cursor_ciclo,
                        contexto_final,
                    )
                conn_ciclo.commit()

            except Exception as erro:
                if contexto_envio.get("enviou"):
                    raise BancoFalhouAposEnvioMeta(
                        "Banco falhou depois da Meta confirmar envio",
                        id_mensagem=mensagem["id_mensagem"],
                        id_conversa=id_conversa,
                        id_hash_msg_bot=contexto_envio.get("id_hash_msg_bot"),
                        id_etapa=contexto_envio.get("id_etapa_resultante"),
                    ) from erro

                raise

            logger.debug(
                "resposta_bot_contexto_final_ok | acao=commit id_mensagem=%s id_conversa=%s etapa=%s resposta_ja_existia=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_final["id_etapa_resultante"],
                contexto_final["resposta_ja_existia"],
                contexto_final["id_hash_msg_bot"],
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
            )

            if not contexto_historico.get("retorno_followup"):
                proteger_conversa(id_conversa, lock_version, cursor_ciclo)
                resultado_encerramento = finalizar_mensagem_processada(
                    mensagem,
                    contexto_banco,
                    lock_version,
                    cursor_ciclo,
                    contexto_final,
                )
                conn_ciclo.commit()

            registrar_cache_bloqueio_apos_commit(
                mensagem,
                resultado_encerramento,
            )

        except ConsultaFireAdsPendente as espera:
            # A espera é uma decisão válida, não uma falha SQL. Solicitação,
            # vínculo da fila e reagendamento serão confirmados juntos abaixo.
            # Libera o ciclo para outras conversas. Esperar uma leitura não é erro
            # e não pode esgotar as três tentativas da mensagem original.
            reagendar_mensagem_sem_erro(
                mensagem["id_mensagem"], cursor_ciclo, delay_seconds=5,
                retry_esperado=mensagem["retry_count"],
            )
            conn_ciclo.commit()
            logger.debug(
                "fireads_consulta_pendente | conversa=%s motivo=%s acao=aguardar_sem_responder",
                estado_ciclo["id_conversa"], espera,
            )

        except UnidadeDesativada:
            conn_ciclo.rollback()
            # Preserva pendência/histórico; a função dequeue não reserva inativas.
            reagendar_mensagem_sem_erro(
                mensagem["id_mensagem"], cursor_ciclo, delay_seconds=300,
                retry_esperado=mensagem["retry_count"],
            )
            conn_ciclo.commit()
            logger.info("unidade_desativada | acao=preservar_pendente id_mensagem=%s", mensagem["id_mensagem"])

        except LockConversaPerdido:
            if conn_ciclo:
                conn_ciclo.rollback()
            # Não reescreve uma fila que pode estar sendo processada pelo novo dono.
            logger.warning(
                "lock_perdido | acao=aguardar_recuperacao_fila id_conversa=%s",
                estado_ciclo["id_conversa"],
            )

        except ErroEnvioMeta as erro:
            logger.warning(
                "meta_envio_erro | acao=reagendar_sem_sent id_mensagem=%s cliente=%s phone_number_id=%s etapa=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro.id_etapa,
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except BancoFalhouAposEnvioMeta as erro:
            if isinstance(erro.__cause__, LockConversaPerdido):
                conn_ciclo.rollback()
                logger.critical(
                    "meta_confirmou_com_lock_perdido | conversa=%s hash=%s risco=duplicidade",
                    erro.id_conversa,
                    erro.id_hash_msg_bot,
                )
                continue
            logger.critical(
                "banco_falhou_apos_envio_meta | risco=resposta_duplicada acao=reagendar_sem_sent id_mensagem=%s id_conversa=%s etapa=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s erro=%s",
                erro.id_mensagem,
                erro.id_conversa,
                erro.id_etapa,
                erro.id_hash_msg_bot,
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except psycopg.OperationalError as erro:
            logger.warning(
                "banco_operacional_erro | acao=retry_conexao id_mensagem=%s erro=%s",
                estado_ciclo["id_mensagem"],
                erro,
            )
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            logger.warning(
                "unidade_nao_encontrada | acao=tratar_unidade_invalida id_mensagem=%s cliente=%s phone_number_id=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            logger.exception(
                "mensagem_erro | acao=tratar_erro_generico id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s estado=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                estado_ciclo["id_conversa"],
                estado_ciclo["estado"],
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo)
            reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo)

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    unlock_realizado = liberar_lock_conversa_se_necessario(
                        cursor_ciclo,
                        estado_ciclo,
                    )

                    if unlock_realizado is not None:
                        conn_ciclo.commit()

                except Exception as erro:
                    logger.exception(
                        "finalizacao_ciclo_falhou | acao=continuar_para_close erro=%s",
                        erro,
                    )

                finally:
                    try:
                        conn_ciclo.close()

                    except Exception as erro:
                        logger.exception(
                            "conexao_ciclo_close_falhou | acao=registrar_e_continuar erro=%s",
                            erro,
                        )
