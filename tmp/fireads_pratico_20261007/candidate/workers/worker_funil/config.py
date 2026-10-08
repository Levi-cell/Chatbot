"""Configuração operacional do worker de Funil."""

from core.config_env import env_bool, env_int


FUNIL_WORKER_ENABLED = env_bool("FUNIL_WORKER_ENABLED", False)
FUNIL_INTERVALO_SEGUNDOS = env_int("FUNIL_INTERVALO_SEGUNDOS", 1800)
FUNIL_LIMITE_POR_CICLO = env_int("FUNIL_LIMITE_POR_CICLO", 100)
FUNIL_LEASE_SEGUNDOS = env_int("FUNIL_LEASE_SEGUNDOS", 900)
FUNIL_RETRY_LEAD_SEGUNDOS = env_int("FUNIL_RETRY_LEAD_SEGUNDOS", 3600)
FUNIL_HTTP_TIMEOUT = (
    env_int("FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS", 10),
    env_int("FUNIL_HTTP_READ_TIMEOUT_SECONDS", 30),
)


def validar_configuracao_funil():
    valores_positivos = {
        "FUNIL_INTERVALO_SEGUNDOS": FUNIL_INTERVALO_SEGUNDOS,
        "FUNIL_LIMITE_POR_CICLO": FUNIL_LIMITE_POR_CICLO,
        "FUNIL_LEASE_SEGUNDOS": FUNIL_LEASE_SEGUNDOS,
        "FUNIL_RETRY_LEAD_SEGUNDOS": FUNIL_RETRY_LEAD_SEGUNDOS,
        "FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS": FUNIL_HTTP_TIMEOUT[0],
        "FUNIL_HTTP_READ_TIMEOUT_SECONDS": FUNIL_HTTP_TIMEOUT[1],
    }

    invalidos = [nome for nome, valor in valores_positivos.items() if valor <= 0]
    if invalidos:
        raise RuntimeError(
            "Configurações do Funil devem ser positivas: "
            + ", ".join(invalidos)
        )

