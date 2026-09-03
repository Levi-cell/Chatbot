"""Janelas de consulta aceitas pelo painel; valores do navegador nunca viram SQL."""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


@dataclass(frozen=True)
class PeriodoMonitoramento:
    chave: str
    rotulo: str
    inicio: datetime | None
    fim: datetime
    inicio_anterior: datetime | None = None
    fim_anterior: datetime | None = None


PERIODOS = {
    '24h': ('Últimas 24 horas', timedelta(hours=24)),
    '7d': ('Últimos 7 dias', timedelta(days=7)),
    '30d': ('Últimos 30 dias', timedelta(days=30)),
    '2m': ('Últimos 2 meses', timedelta(days=60)),
    '3m': ('Últimos 3 meses', timedelta(days=90)),
    '6m': ('Últimos 6 meses', timedelta(days=180)),
    '1a': ('Último ano', timedelta(days=365)),
}


def resolver_periodo(chave, *, agora=None):
    agora = agora or datetime.now(timezone.utc)
    if agora.tzinfo is None:
        agora = agora.replace(tzinfo=timezone.utc)
    agora = agora.astimezone(timezone.utc)
    if chave == 'total':
        return PeriodoMonitoramento('total', 'Todo o histórico', None, agora)
    if chave not in PERIODOS:
        raise ValueError('Período inválido.')
    rotulo, duracao = PERIODOS[chave]
    inicio = agora - duracao
    return PeriodoMonitoramento(
        chave, rotulo, inicio, agora,
        inicio_anterior=inicio - duracao,
        fim_anterior=inicio,
    )

