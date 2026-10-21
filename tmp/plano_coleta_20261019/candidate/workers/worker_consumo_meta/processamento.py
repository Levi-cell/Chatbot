"""Transações curtas de sucesso/falha; nunca manter transação aberta durante HTTP."""

from datetime import datetime
from zoneinfo import ZoneInfo

from core.consumo_meta.apuracao import decidir_apuracao, quantidades, validar_identidade
from core.consumo_meta.periodos import dia_consolidacao_seguinte, validar_mes
from core.repositories.consumo_meta import coletas


def salvar_coleta(conn, id_unidade, resultado, agora, proxima):
    mes = validar_mes(resultado["mes"])
    with conn.transaction(), conn.cursor() as cursor:
        coletas.conferir_cadastro_coletado(cursor, id_unidade, resultado)
        anterior = coletas.buscar_para_atualizar(cursor, id_unidade, mes)
        if anterior and anterior["ultimo_sucesso_em"] >= agora:
            return False
        validar_identidade(anterior, resultado)
        valores = {
            "id_unidade": id_unidade, "mes_referencia": mes,
            "waba_id": resultado["waba_id"],
            "phone_number_id": resultado["numeros"][0]["phone_number_id"],
            "timezone_id": int(resultado["timezone_id"]), "fuso_horario": resultado["fuso_horario"],
            "data_hora_inicio": datetime.fromisoformat(resultado["data_hora_inicio"]),
            "data_hora_fim": datetime.fromisoformat(resultado["data_hora_fim"]),
            "consultado_ate": datetime.fromisoformat(resultado["fim_exclusivo"]),
            "ultimo_sucesso_em": agora,
            **quantidades(resultado), **decidir_apuracao(anterior, resultado, agora),
        }
        gravou = coletas.salvar_registro(cursor, valores)
        if gravou:
            coletas.agendar(cursor, id_unidade, resultado["mes"], agora, proxima)
        return gravou


def registrar_falha(conn, id_unidade, periodo, agora, proxima, erro):
    """Falha no dia da decisão também prorroga; não deixa consolidar no dia 26."""
    with conn.transaction(), conn.cursor() as cursor:
        coletas.agendar(cursor, id_unidade, periodo, agora, proxima, erro)
        if periodo == "conta":
            return
        registro = coletas.buscar_para_atualizar(cursor, id_unidade, validar_mes(periodo))
        if not registro or registro["status_apuracao"] == "consolidado":
            return
        hoje = agora.astimezone(ZoneInfo(registro["fuso_horario"])).date()
        prazo = registro["data_proxima_consolidacao"]
        if hoje >= prazo:
            prazo = dia_consolidacao_seguinte(hoje)
        estado = "em_conferencia" if agora >= registro["data_hora_fim"] else "em_andamento"
        decisao = agora if hoje >= registro["data_proxima_consolidacao"] else registro["ultima_decisao_consolidacao_em"]
        coletas.atualizar_pendencia(cursor, registro, estado, prazo, decisao)


def atualizar_agenda_encerrados(conn, registros, agora):
    """Recupera viradas e dias 25 perdidos, mesmo antes de a Meta responder."""
    with conn.transaction(), conn.cursor() as cursor:
        for registro in registros:
            if registro["status_apuracao"] == "consolidado":
                continue
            hoje = agora.astimezone(ZoneInfo(registro["fuso_horario"])).date()
            prazo = registro["data_proxima_consolidacao"]
            estado = "em_conferencia" if agora >= registro["data_hora_fim"] else "em_andamento"
            decisao = registro["ultima_decisao_consolidacao_em"]
            if hoje > prazo:
                prazo = dia_consolidacao_seguinte(hoje)
                # Se reiniciou antes do dia 25 do mês seguinte, esse é o próximo prazo.
                if hoje.day < 25:
                    prazo = hoje.replace(day=25)
                decisao = agora
            if estado != registro["status_apuracao"] or prazo != registro["data_proxima_consolidacao"]:
                coletas.atualizar_pendencia(cursor, registro, estado, prazo, decisao)
