import logging

from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value


logger = logging.getLogger("cache.cliente")

REDIS_PREFIX = "cliente_cache:"
CLIENTE_CACHE_TTL_SEGUNDOS = 60 * 60 * 24 * 180


def buscar_cliente_cache(waid_telefone):
    key = _montar_key_cliente(waid_telefone)

    if key is None:
        return None

    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        id_cliente = r.get(key)

        if id_cliente is None:
            logger.debug(
                "cliente_cache_miss | acao=fallback_banco cliente=%s",
                short_value(waid_telefone),
            )
            return None

        id_cliente = int(id_cliente)

        if id_cliente <= 0:
            logger.warning(
                "cliente_cache_valor_invalido | acao=fallback_banco cliente=%s valor=%s",
                short_value(waid_telefone),
                id_cliente,
            )
            remover_cliente_cache(waid_telefone)
            return None

        logger.debug(
            "cliente_cache_hit | acao=usar_cache cliente=%s id_cliente=%s",
            short_value(waid_telefone),
            id_cliente,
        )
        return id_cliente

    except (TypeError, ValueError) as exc:
        logger.warning(
            "cliente_cache_parse_falhou | acao=fallback_banco cliente=%s erro=%s",
            short_value(waid_telefone),
            exc,
        )
        remover_cliente_cache(waid_telefone)
        return None

    except Exception as exc:
        logger.warning(
            "cliente_cache_indisponivel | acao=fallback_banco cliente=%s erro=%s",
            short_value(waid_telefone),
            exc,
        )
        return None


def salvar_cliente_cache(waid_telefone, id_cliente):
    key = _montar_key_cliente(waid_telefone)

    if key is None or not _id_cliente_valido(id_cliente):
        logger.warning(
            "cliente_cache_salvar_ignorado | motivo=dados_invalidos acao=seguir_sem_cache cliente=%s id_cliente=%s",
            short_value(waid_telefone),
            id_cliente,
        )
        return False

    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        r.setex(key, CLIENTE_CACHE_TTL_SEGUNDOS, int(id_cliente))

        logger.debug(
            "cliente_cache_salvo | acao=salvar_redis cliente=%s id_cliente=%s ttl=%s",
            short_value(waid_telefone),
            id_cliente,
            CLIENTE_CACHE_TTL_SEGUNDOS,
        )
        return True

    except Exception as exc:
        logger.warning(
            "cliente_cache_salvar_falhou | acao=seguir_sem_cache cliente=%s id_cliente=%s erro=%s",
            short_value(waid_telefone),
            id_cliente,
            exc,
        )
        return False


def remover_cliente_cache(waid_telefone):
    key = _montar_key_cliente(waid_telefone)

    if key is None:
        return False

    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        r.delete(key)

        logger.debug(
            "cliente_cache_removido | acao=remover_redis cliente=%s",
            short_value(waid_telefone),
        )
        return True

    except Exception as exc:
        logger.warning(
            "cliente_cache_remover_falhou | acao=ignorar cliente=%s erro=%s",
            short_value(waid_telefone),
            exc,
        )
        return False


def _montar_key_cliente(waid_telefone):
    if waid_telefone is None:
        return None

    telefone = str(waid_telefone).strip()

    if not telefone:
        return None

    return f"{REDIS_PREFIX}{telefone}"


def _id_cliente_valido(id_cliente):
    try:
        return int(id_cliente) > 0
    except (TypeError, ValueError):
        return False
