import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)


def env_required(name):
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")

    return value.strip()


def env_optional(name, default=""):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def env_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "sim"}:
        return True

    if normalized in {"0", "false", "no", "nao"}:
        return False

    raise RuntimeError(f"Valor booleano invalido em {name}: {value}")


def env_int(name, default=None):
    value = os.getenv(name)

    if value is None:
        if default is None:
            raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
        return default

    try:
        return int(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"Valor inteiro invalido em {name}: {value}") from exc


def env_csv(name, default=None):
    value = os.getenv(name)

    if value is None:
        return list(default or [])

    return [item.strip() for item in value.split(",") if item.strip()]
