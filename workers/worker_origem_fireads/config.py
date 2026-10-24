"""Ativação explícita e marco fixo: reinícios não movem a janela de descoberta."""

from datetime import datetime
from core.config_env import env_bool, env_optional

INTERVALO_SEGUNDOS = 7200
TAMANHO_LOTE = 100


def configuracao():
    if not env_bool('FIREADS_ORIGEM_ATIVO', False):
        return None
    try:
        desde = datetime.fromisoformat(env_optional('FIREADS_ORIGEM_DESDE'))
        if desde.tzinfo is None or desde.utcoffset() is None:
            raise ValueError
    except ValueError:
        raise ValueError('FIREADS_ORIGEM_DESDE exige data ISO 8601 com fuso e marco fixo') from None
    return desde
