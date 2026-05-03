import redis
import threading
import time
import logging

logger = logging.getLogger(__name__)

_redis_client = None
_lock = threading.Lock()


def get_redis():
    """
    Singleton thread-safe com inicialização única do client Redis.
    """

    global _redis_client

    if _redis_client is None:
        with _lock:
            if _redis_client is None:
                _redis_client = _create_client()

    return _redis_client


def _create_client():
    """
    Cria conexão Redis com validação inicial.
    """

    try:
        client = redis.Redis(
            host='redis-14738.crce216.sa-east-1-2.ec2.cloud.redislabs.com',
            port=14738,
            decode_responses=True,
            username="default",
            password="CE3qT6jtGcErfsdkl4vQT9tnxz5QcHce",
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )

        # 🔥 valida conexão real
        client.ping()

        logger.info("Redis conectado com sucesso")
        return client

    except Exception as e:
        logger.error(f"Falha ao conectar no Redis: {e}")
        raise


def get_redis_safe(retries=3, delay=2):
    """
    Versão resiliente para worker.
    - tenta reutilizar client
    - valida conexão com ping
    - recria se necessário
    """

    global _redis_client

    for attempt in range(1, retries + 1):
        try:
            client = get_redis()

            # valida conexão viva
            client.ping()

            return client

        except Exception as e:
            logger.warning(
                f"Redis indisponível (tentativa {attempt}/{retries}): {e}"
            )

            # força recriação do client
            _redis_client = None

            time.sleep(delay)

    raise ConnectionError("Redis indisponível após múltiplas tentativas")


def confirmar_conexao_redis():
    """
    Healthcheck simples para uso externo.
    """

    try:
        client = get_redis_safe()
        return print(client.ping())

    except Exception as e:
        logger.error(f"Erro ao conectar no Redis: {e}")
        return False

