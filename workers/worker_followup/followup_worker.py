"""Propriedade transacional do ciclo proativo; não consome fila nem etapas."""

import logging
from datetime import timedelta
from time import monotonic

from core.integrations.whatsapp.messages.followup_messages import (
    MENSAGEM_FOLLOWUP,
    montar_mensagem_encerramento_followup,
)
from core.database.connection_aws import get_conn
from core.repositories.atendimento.conversas import (
    tentar_lock_conversa,
    unlock_conversa,
)
from core.repositories.atendimento.followup import (
    configurar_consulta_followup,
    listar_elegiveis,
    persistir_followup,
    proteger_conversa,
    reler_elegivel,
    validar_schema_followup,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.followup import (
    enviar_followup,
)

logger = logging.getLogger("worker.followup")


def obter_lote(limite, depois=None):
    with get_conn(application_name="worker_followup_scan", connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            configurar_consulta_followup(cursor)
            validar_schema_followup(cursor)
            return listar_elegiveis(cursor, limite, depois)


def processar_candidato(candidato, parar):
    inicio = monotonic()
    conn = get_conn(application_name="worker_followup", connect_timeout=10)
    versao = None
    envio = None
    id_conversa = candidato["id_conversa"]
    try:
        with conn.cursor() as cursor:
            configurar_consulta_followup(cursor, sessao=True)
            lock_ok, versao_obtida = tentar_lock_conversa(id_conversa, cursor)
            conn.commit()
            if not lock_ok:
                logger.debug(
                    "followup_descartado | conversa=%s motivo=lock_ocupado", id_conversa
                )
                return False
            versao = versao_obtida
            proteger_conversa(id_conversa, versao, cursor, renovar=True)
            dados = reler_elegivel(id_conversa, cursor)
            conn.commit()
            if dados is None or parar.is_set():
                logger.debug(
                    "followup_descartado | conversa=%s motivo=%s versao=%s",
                    id_conversa,
                    "parada_solicitada" if parar.is_set() else "guard_revalidacao",
                    versao,
                )
                return False
            stage_anterior = dados["followup_stage"]
            stage = stage_anterior + 1
            mensagem = MENSAGEM_FOLLOWUP
            if stage == 2:
                mensagem = montar_mensagem_encerramento_followup(
                    id_etapa=dados["id_etapa"],
                    nome_titular=dados["nome_titular"],
                    nome_agente=dados["nome_agente"],
                    status_dependente=dados["status_dependente"],
                    nome_dependente=dados["nome_dependente"],
                )
            logger.info(
                "followup_despacho | conversa=%s cliente_id=%s unidade=%s etapa=%s "
                "stage_anterior=%s stage_proposto=%s ancora_id=%s ancora_em=%s vence_em=%s versao=%s",
                id_conversa,
                dados["id_cliente"],
                dados["id_unidade"],
                dados["id_etapa"],
                stage_anterior,
                stage,
                dados["id_ancora"],
                dados["ancora_em"],
                dados["ancora_em"] + timedelta(hours=7),
                versao,
            )
            # Releitura já inclui histórico, fila, bloqueios, unidade e janela Meta.
            envio = enviar_followup(
                dados["cliente_telefone"], dados["id_phone_unidade"], mensagem=mensagem
            )
            id_bot, _ = persistir_followup(dados, envio, versao, cursor)
            conn.commit()
            logger.info(
                "followup_confirmado | conversa=%s unidade=%s etapa=%s stage=%s versao=%s historico=%s",
                id_conversa,
                dados["id_unidade"],
                dados["id_etapa"],
                stage,
                versao,
                id_bot,
            )
            return True
    except Exception:
        conn.rollback()
        if envio and envio.get("enviou"):
            logger.critical(
                "followup_commit_falhou | conversa=%s versao=%s id_hash_msg=%s risco=duplicidade",
                id_conversa,
                versao,
                envio.get("id_hash_msg_bot"),
                exc_info=True,
            )
        else:
            logger.exception(
                "followup_falhou | conversa=%s versao=%s stage_preservado=true",
                id_conversa,
                versao,
            )
        return False
    finally:
        try:
            if versao is not None:
                with conn.cursor() as cursor:
                    unlock_conversa(id_conversa, versao, cursor)
                conn.commit()
        except Exception:
            conn.rollback()
            logger.exception(
                "followup_unlock_falhou | conversa=%s versao=%s", id_conversa, versao
            )
        finally:
            conn.close()
            logger.debug(
                "followup_ciclo_final | conversa=%s duracao_ms=%.0f",
                id_conversa,
                (monotonic() - inicio) * 1000,
            )


def executar_worker(config, parar):
    depois = None
    falhas_scan = 0
    while not parar.is_set():
        try:
            candidatos = obter_lote(config.lote, depois)
            falhas_scan = 0
            for candidato in candidatos:
                if parar.is_set():
                    break
                try:
                    processar_candidato(candidato, parar)
                except Exception:
                    # Inclui falhas de conexão/limpeza fora do try do processamento.
                    logger.exception(
                        "followup_candidata_falhou | conversa=%s acao=seguir_lote",
                        candidato["id_conversa"],
                    )
                depois = (candidato["ancora_em"], candidato["id_conversa"])
            if len(candidatos) < config.lote:
                depois = None
            # Limite por rodada também evita tempestade de retry sem resposta confirmada.
            parar.wait(config.intervalo)
        except Exception:
            falhas_scan += 1
            espera = min(300, 5 * (2 ** min(falhas_scan - 1, 6)))
            logger.exception("followup_scan_falhou | retry_em=%s", espera)
            parar.wait(espera)
