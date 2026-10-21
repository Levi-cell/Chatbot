"""Limites de trabalho e cadência; a agenda efetiva fica persistida no banco."""

from core.config_env import env_bool, env_int

CONSUMO_META_ENABLED = env_bool("CONSUMO_META_ENABLED", False)
CONSUMO_META_CICLO_SEGUNDOS = env_int("CONSUMO_META_CICLO_SEGUNDOS", 60)
CONSUMO_META_INTERVALO_SEGUNDOS = env_int("CONSUMO_META_INTERVALO_SEGUNDOS", 3600)
CONSUMO_META_LIMITE_POR_CICLO = env_int("CONSUMO_META_LIMITE_POR_CICLO", 100)
CONSUMO_META_HORA_CONFERENCIA = env_int("CONSUMO_META_HORA_CONFERENCIA", 9)


def validar_configuracao():
    if min(CONSUMO_META_CICLO_SEGUNDOS, CONSUMO_META_INTERVALO_SEGUNDOS, CONSUMO_META_LIMITE_POR_CICLO) <= 0:
        raise ValueError("Intervalos e limite do consumo Meta devem ser positivos.")
    if not 0 <= CONSUMO_META_HORA_CONFERENCIA <= 23:
        raise ValueError("Hora de conferência deve estar entre 0 e 23.")
