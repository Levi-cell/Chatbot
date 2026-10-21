"""Coleta sequencial: um erro de conta/período não impede as demais unidades."""

import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from core.consumo_meta.periodos import (
    INICIO_ACOMPANHAMENTO, fronteiras_mes, meses_ate, primeiro_dia, proxima_coleta_diaria,
)
from core.integrations.whatsapp.consumo import consultar_conta_consumo, consultar_metricas_conta
from core.repositories.consumo_meta import coletas
from core.repositories.unidades.consultas import unidade_habilitada
from .config import (
    CONSUMO_META_HORA_CONFERENCIA, CONSUMO_META_INTERVALO_SEGUNDOS,
    CONSUMO_META_LIMITE_POR_CICLO,
)
from .processamento import atualizar_agenda_encerrados, registrar_falha, salvar_coleta

logger = logging.getLogger("worker.consumo_meta")
LOCK_CONSUMO_META = 73492601


def agora_utc():
    return datetime.now(timezone.utc)


def erro_publicavel(erro):
    # As mensagens da integração são sanitizadas. Erros inesperados podem conter
    # dados de conexão/payload; nesses casos, registrar somente o tipo da falha.
    if isinstance(erro, (ValueError, RuntimeError)):
        return str(erro)[:400]
    return f"Falha interna na coleta ({type(erro).__name__})."


def executar_ciclo_consumo(*, conectar=None, session=None, relogio=agora_utc, parar=None):
    if conectar is None:
        from core.database.connection_aws import get_conn
        conectar = lambda: get_conn(application_name="worker_consumo_meta", connect_timeout=10)
    resumo = {"coletados": 0, "falhas": 0, "ocupado": False}
    sessao_propria = session is None
    session = session or requests.Session()
    conn = None
    try:
        conn = conectar()
        conn.autocommit = True
        with conn.cursor() as cursor:
            cursor.execute("SELECT pg_try_advisory_lock(%s)", (LOCK_CONSUMO_META,))
            if not cursor.fetchone()[0]:
                resumo["ocupado"] = True
                return resumo
            unidades = coletas.listar_unidades(cursor)
        trabalhos = []
        for unidade in unidades:
            if parar and parar.is_set():
                break
            agora = relogio()
            with conn.cursor() as cursor:
                if not unidade_habilitada(unidade["id_unidade"], cursor):
                    continue
                agenda = coletas.listar_agenda(cursor, unidade["id_unidade"])
                registros = coletas.listar_registros(cursor, unidade["id_unidade"])
            atualizar_agenda_encerrados(conn, registros, agora)
            conta_agenda = agenda.get("conta")
            # Falha de conta espera a próxima coleta horária; sucesso ainda permite
            # processar pendências diárias que venceram antes dessa próxima hora.
            if conta_agenda and conta_agenda["ultimo_erro"] and conta_agenda["proxima_consulta_em"] > agora:
                continue
            por_mes = {registro["mes_referencia"]: registro for registro in registros}
            if unidade["nome_fuso"]:
                atual = primeiro_dia(agora, unidade["nome_fuso"])
                meses = list(meses_ate(INICIO_ACOMPANHAMENTO, atual))
                devidos = [mes for mes in meses if
                    (mes not in por_mes or por_mes[mes]["status_apuracao"] != "consolidado") and
                    (mes.strftime("%Y-%m") not in agenda or agenda[mes.strftime("%Y-%m")]["proxima_consulta_em"] <= agora)]
                if not devidos and conta_agenda and conta_agenda["proxima_consulta_em"] > agora:
                    continue
            try:
                conta = consultar_conta_consumo(unidade["waba_id"], session=session)
                observado = relogio()
                with conn.transaction(), conn.cursor() as cursor:
                    coletas.sincronizar_fuso(cursor, unidade["id_unidade"], conta, observado)
                    coletas.agendar(cursor, unidade["id_unidade"], "conta", observado,
                                   observado + timedelta(seconds=CONSUMO_META_INTERVALO_SEGUNDOS))
            except Exception as erro:
                if conn.closed:
                    raise
                resumo["falhas"] += 1
                registrar_falha(conn, unidade["id_unidade"], "conta", agora,
                                agora + timedelta(seconds=CONSUMO_META_INTERVALO_SEGUNDOS), erro_publicavel(erro))
                for registro in registros:
                    if registro["status_apuracao"] == "consolidado":
                        continue
                    fuso = registro["fuso_horario"]
                    if agora.astimezone(ZoneInfo(fuso)).date() == registro["data_proxima_consolidacao"]:
                        registrar_falha(conn, unidade["id_unidade"], registro["mes_referencia"].strftime("%Y-%m"),
                                        agora, proxima_coleta_diaria(agora, fuso, CONSUMO_META_HORA_CONFERENCIA),
                                        "Não foi possível validar a conta na data de conferência.")
                logger.warning("consumo_conta_falhou | unidade=%s tipo=%s", unidade["id_unidade"], type(erro).__name__)
                continue
            atual = primeiro_dia(agora, conta["fuso_horario"])
            for mes in reversed(list(meses_ate(INICIO_ACOMPANHAMENTO, atual))):
                registro = por_mes.get(mes)
                periodo = mes.strftime("%Y-%m")
                if registro and registro["status_apuracao"] == "consolidado":
                    continue
                if periodo in agenda and agenda[periodo]["proxima_consulta_em"] > agora:
                    continue
                # Prioridade global para o mês atual; depois, pendências mais antigas.
                trabalhos.append((mes != atual, mes, unidade, conta, registro))

        trabalhos.sort(key=lambda item: (item[0], item[1], item[2]["id_unidade"]))
        for _, mes, unidade, conta, registro in trabalhos[:CONSUMO_META_LIMITE_POR_CICLO]:
            if parar and parar.is_set():
                break
            # O lote pode ter sido montado antes da desativação no Admin.
            with conn.cursor() as cursor:
                if not unidade_habilitada(unidade["id_unidade"], cursor):
                    continue
            referencia = relogio()
            inicio, fim = fronteiras_mes(mes, conta["fuso_horario"])
            fuso_agenda = registro["fuso_horario"] if registro else conta["fuso_horario"]
            proxima = (referencia + timedelta(seconds=CONSUMO_META_INTERVALO_SEGUNDOS) if referencia < fim
                       else proxima_coleta_diaria(referencia, fuso_agenda, CONSUMO_META_HORA_CONFERENCIA))
            periodo = mes.strftime("%Y-%m")
            try:
                # Janela histórica da API: não converter indisponibilidade em zero.
                if inicio < referencia - timedelta(days=365):
                    raise ValueError("Período fora da janela histórica de consulta; revisão necessária.")
                if referencia.replace(microsecond=0) <= inicio:
                    with conn.transaction(), conn.cursor() as cursor:
                        coletas.agendar(cursor, unidade["id_unidade"], periodo, referencia, inicio + timedelta(minutes=1))
                    continue
                resultado = consultar_metricas_conta(conta, phone_number_id=unidade["phone_number_id"],
                                                     mes=periodo, session=session, agora=referencia)
                if salvar_coleta(conn, unidade["id_unidade"], resultado, relogio(), proxima):
                    resumo["coletados"] += 1
            except Exception as erro:
                if conn.closed:
                    raise
                resumo["falhas"] += 1
                registrar_falha(conn, unidade["id_unidade"], periodo, relogio(), proxima, erro_publicavel(erro))
                logger.warning("consumo_mes_falhou | unidade=%s mes=%s tipo=%s", unidade["id_unidade"], periodo, type(erro).__name__)
        return resumo
    finally:
        # O lock é de sessão: fechamento/queda da conexão libera o ciclo. Nenhum
        # lock de conversa, fila de mensagens ou transação HTTP é compartilhado.
        if conn is not None:
            conn.close()
        if sessao_propria:
            session.close()
