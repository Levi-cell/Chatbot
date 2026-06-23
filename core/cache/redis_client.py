import logging
import threading
import time

import redis

from core.config_env import env_bool, env_int, env_optional, env_required


logger = logging.getLogger(__name__)

_redis_client = None
_lock = threading.Lock()

REDIS_HOST = env_required("REDIS_HOST")
REDIS_PORT = env_int("REDIS_PORT", 6379)
REDIS_USERNAME = env_optional("REDIS_USERNAME") or None
REDIS_PASSWORD = env_optional("REDIS_PASSWORD") or None
REDIS_SSL = env_bool("REDIS_SSL", False)


def get_redis():
    """
    Singleton thread-safe com inicializacao unica do client Redis.
    """

    global _redis_client

    if _redis_client is None:
        with _lock:
            if _redis_client is None:
                _redis_client = _create_client()

    return _redis_client


def _create_client():
    """
    Cria conexao Redis com validacao inicial.
    """

    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            username=REDIS_USERNAME,
            password=REDIS_PASSWORD,
            ssl=REDIS_SSL,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )

        client.ping()

        logger.info("redis_conectado | status=ok")
        return client

    except Exception as e:
        logger.error("redis_conectar_falhou | erro=%s", e)
        raise


def get_redis_safe(retries=3, delay=2, validate=True):
    """
    Versao resiliente para worker.
    - tenta reutilizar client
    - valida conexao com ping quando validate=True
    - recria se necessario
    """

    global _redis_client

    for attempt in range(1, retries + 1):
        try:
            client = get_redis()

            if validate:
                client.ping()

            return client

        except Exception as e:
            logger.warning(
                "redis_indisponivel | tentativa=%s total=%s erro=%s",
                attempt,
                retries,
                e,
            )

            _redis_client = None

            time.sleep(delay)

    raise ConnectionError("Redis indisponivel apos multiplas tentativas")


def confirmar_conexao_redis():
    """
    Healthcheck simples para uso externo.
    """

    try:
        client = get_redis_safe()
        resultado = client.ping()
        logger.info("redis_healthcheck_ok | ping=%s", resultado)
        return resultado

    except Exception as e:
        logger.error("redis_healthcheck_falhou | erro=%s", e)
        return False
