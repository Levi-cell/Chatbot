"""Carrega a configuração local e privada usada apenas por ``operations``."""

import os


def configure_local_operations():
    """Injeta a configuração local antes de importar conectores de ``core``."""
    try:
        from operations.local_settings import LOCAL_ENV
    except ImportError as exc:
        raise RuntimeError(
            "Arquivo operations/local_settings.py não encontrado"
        ) from exc

    for nome, valor in LOCAL_ENV.items():
        os.environ[nome] = str(valor)

