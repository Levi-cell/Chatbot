import ipaddress
import logging
import socket
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
    Cria conexao exclusivamente com um Redis remoto e valida o acesso inicial.
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

        destino = validar_redis_remoto(client)
        client.ping()

        logger.info("redis_conectado | status=ok destino=%s", destino)
        return client

    except Exception as e:
        logger.error("redis_conectar_falhou | erro=%s", e)
        raise


def validar_redis_remoto(redis_client):
    """
    Confirma que o cliente aponta para outra maquina, nunca para Redis local.

    Enderecos privados remotos continuam validos; somente loopback, endereco
    indefinido ou um IP pertencente a esta propria maquina sao recusados.
    """

    pool = getattr(redis_client, "connection_pool", None)
    configuracao = getattr(pool, "connection_kwargs", {})
    host = str(configuracao.get("host", "")).strip()

    if not host:
        raise RuntimeError(
            "nao foi possivel confirmar o destino do Redis; operacao abortada"
        )

    try:
        destinos = {
            _normalizar_ip(resultado[4][0])
            for resultado in socket.getaddrinfo(
                host,
                None,
                type=socket.SOCK_STREAM,
            )
        }
    except (OSError, ValueError) as exc:
        raise RuntimeError(
            f"nao foi possivel validar o destino Redis {host}; operacao abortada"
        ) from exc

    locais = {
        ipaddress.ip_address("127.0.0.1"),
        ipaddress.ip_address("::1"),
    }
    for nome_local in {socket.gethostname(), socket.getfqdn()}:
        if not nome_local:
            continue
        try:
            locais.update(
                _normalizar_ip(resultado[4][0])
                for resultado in socket.getaddrinfo(
                    nome_local,
                    None,
                    type=socket.SOCK_STREAM,
                )
            )
        except (OSError, ValueError):
            continue

    for destino in destinos:
        if destino.is_loopback or destino.is_unspecified:
            raise RuntimeError(
                f"Redis local recusado ({host}); operacao abortada"
            )

        try:
            familia = (
                socket.AF_INET6
                if isinstance(destino, ipaddress.IPv6Address)
                else socket.AF_INET
            )
            alvo = (
                (str(destino), 9, 0, 0)
                if familia == socket.AF_INET6
                else (str(destino), 9)
            )
            with socket.socket(familia, socket.SOCK_DGRAM) as sock:
                sock.connect(alvo)
                locais.add(_normalizar_ip(sock.getsockname()[0]))
        except OSError:
            pass

        if destino in locais:
            raise RuntimeError(
                f"Redis da propria maquina recusado ({host}); operacao abortada"
            )

    return host


def _normalizar_ip(valor):
    endereco = ipaddress.ip_address(
        str(valor).strip().strip("[]").split("%", 1)[0]
    )
    return getattr(endereco, "ipv4_mapped", None) or endereco


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
