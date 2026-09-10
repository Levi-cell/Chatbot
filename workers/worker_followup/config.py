from dataclasses import dataclass

from core.config_env import env_bool, env_int


@dataclass(frozen=True)
class ConfigFollowup:
    habilitado: bool
    intervalo: int
    lote: int


def carregar_config():
    intervalo = env_int("FOLLOWUP_POLL_SECONDS", 60)
    lote = env_int("FOLLOWUP_BATCH_SIZE", 20)
    if not 5 <= intervalo <= 3600 or not 1 <= lote <= 100:
        raise ValueError("FOLLOWUP_POLL_SECONDS: 5..3600; FOLLOWUP_BATCH_SIZE: 1..100")
    return ConfigFollowup(env_bool("FOLLOWUP_WORKER_ENABLED", False), intervalo, lote)
