"""Fronteiras de calendário e agenda da conferência no fuso da WABA."""

import re
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

INICIO_ACOMPANHAMENTO = date(2026, 10, 1)


def validar_mes(valor):
    if not isinstance(valor, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", valor):
        raise ValueError("Informe o mês no formato AAAA-MM.")
    try:
        return date.fromisoformat(valor + "-01")
    except ValueError:
        raise ValueError("Mês inválido.") from None


def proximo_mes(mes):
    return date(mes.year + (mes.month == 12), mes.month % 12 + 1, 1)


def primeiro_dia(instante, nome_fuso):
    local = instante.astimezone(ZoneInfo(nome_fuso))
    return local.date().replace(day=1)


def fronteiras_mes(mes, nome_fuso):
    fuso = ZoneInfo(nome_fuso)
    return (
        datetime.combine(mes, time.min, fuso),
        datetime.combine(proximo_mes(mes), time.min, fuso),
    )


def dia_consolidacao_seguinte(data_local):
    return proximo_mes(data_local.replace(day=1)).replace(day=25)


def proxima_coleta_diaria(agora, nome_fuso, hora=9):
    """Um horário local estável evita deslocar o ciclo diário a cada execução."""
    local = agora.astimezone(ZoneInfo(nome_fuso))
    destino = datetime.combine(local.date() + timedelta(days=1), time(hora), local.tzinfo)
    return destino.astimezone(timezone.utc)


def meses_ate(inicio, fim):
    while inicio <= fim:
        yield inicio
        inicio = proximo_mes(inicio)
