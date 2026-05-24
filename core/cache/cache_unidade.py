import logging

from core.database.connection_aws import get_conn
from core.database.redis_client import get_redis_safe
from core.logging_config import short_value
from core.repositories.querys import buscar_id_unidade_por_phone_id, pegar_unidades


logger = logging.getLogger("cache.unidades")

REDIS_KEY = "unidades_cache"
CACHE_VERSION_KEY = "unidades_cache_version"
CACHE_TEMP_KEY = f"{REDIS_KEY}:tmp"


class UnidadeNaoEncontrada(Exception):
    pass


def carregar_unidades_redis_primeira_vez():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()
        return carregar_cache_redis(cursor)

    finally:
        if conn:
            conn.close()


def recarregar_cache_unidades():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()
        return carregar_cache_redis(cursor)

    except Exception as exc:
        logger.exception("cache_recarregar_falhou | origem=admin erro=%s", exc)
        return None

    finally:
        if conn:
            conn.close()


def carregar_cache_redis(cursor, redis_retries=3, redis_delay=2):
    r = get_redis_safe(retries=redis_retries, delay=redis_delay)
    unidades = _normalizar_unidades(pegar_unidades(cursor))
    total = _salvar_cache(r, unidades)

    logger.info("cache_atualizado | unidades=%s", total)
    return total


def carregar_unidades_cache_webhook(cursor):
    return carregar_cache_redis(cursor)


def obter_id_unidade_redis_ou_plsql(id_phone_unidade, cursor):
    phone_key = _normalizar_phone_number_id(id_phone_unidade)

    if phone_key is None:
        raise UnidadeNaoEncontrada("phone_number_id invalido")

    try:
        r = get_redis_safe(retries=1, delay=0)

        if _cache_valido(r):
            id_unidade = r.hget(REDIS_KEY, phone_key)

            if _id_unidade_valido(id_unidade):
                return int(id_unidade)

            raise UnidadeNaoEncontrada(f"Unidade nao encontrada no cache ativo: {phone_key}")

        logger.warning(
            "cache_invalido | acao=fallback_banco origem=worker phone_number_id=%s",
            short_value(phone_key),
        )

    except UnidadeNaoEncontrada:
        raise

    except Exception as exc:
        logger.warning(
            "cache_indisponivel | acao=fallback_banco origem=worker phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )

    id_unidade = buscar_id_unidade_por_phone_id(phone_key, cursor)

    _tentar_recarregar_cache(cursor, origem="worker")

    if not _id_unidade_valido(id_unidade):
        raise UnidadeNaoEncontrada(f"Unidade nao encontrada: {phone_key}")

    return int(id_unidade)

## REDUNDANTE

# def garantir_cache_unidades_se_necessario(cursor):
#     try:
#         r = get_redis_safe(retries=1, delay=0)
#
#         if not _cache_valido(r):
#             logger.info("cache_invalido | acao=recarregar origem=worker")
#             return carregar_cache_redis(cursor, redis_retries=1, redis_delay=0)
#
#         return None
#
#     except Exception as exc:
#         logger.warning("cache_validacao_falhou | origem=worker erro=%s", exc)
#         return None


def unidade_esta_ativa(phone_number_id):
    phone_key = _normalizar_phone_number_id(phone_number_id)

    if phone_key is None:
        return False

    try:
        r = get_redis_safe(retries=1, delay=0)

        if _cache_valido(r):
            return bool(r.hexists(REDIS_KEY, phone_key))

        logger.warning(
            "cache_invalido | acao=fallback_banco origem=webhook phone_number_id=%s",
            short_value(phone_key),
        )

    except Exception as exc:
        logger.warning(
            "cache_indisponivel | acao=fallback_banco origem=webhook phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )

    return _unidade_esta_ativa_banco_e_repara_cache(phone_key)


def _unidade_esta_ativa_banco_e_repara_cache(phone_key):
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        id_unidade = buscar_id_unidade_por_phone_id(phone_key, cursor)

        _tentar_recarregar_cache(cursor, origem="webhook")

        return _id_unidade_valido(id_unidade)

    except Exception as exc:
        logger.exception(
            "fallback_banco_unidade_falhou | origem=webhook phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )
        return False

    finally:
        if conn:
            conn.close()


def _tentar_recarregar_cache(cursor, origem):
    try:
        return carregar_cache_redis(cursor, redis_retries=1, redis_delay=0)

    except Exception as exc:
        logger.warning(
            "cache_reparo_falhou | origem=%s erro=%s",
            origem,
            exc,
        )
        return None


def _salvar_cache(r, unidades):
    total = len(unidades)

    if total == 0:
        pipe = r.pipeline()
        pipe.delete(REDIS_KEY)
        pipe.delete(CACHE_TEMP_KEY)
        pipe.set(CACHE_VERSION_KEY, 0)
        pipe.execute()
        return 0

    pipe = r.pipeline()
    pipe.delete(CACHE_TEMP_KEY)
    pipe.hset(CACHE_TEMP_KEY, mapping=unidades)
    pipe.rename(CACHE_TEMP_KEY, REDIS_KEY)
    pipe.set(CACHE_VERSION_KEY, total)
    pipe.execute()

    return total


def _cache_valido(r):
    try:
        versao = r.get(CACHE_VERSION_KEY)

        if versao is None:
            return False

        total_esperado = int(versao)

        if total_esperado == 0:
            return True

        return r.hlen(REDIS_KEY) == total_esperado

    except Exception:
        return False


def _normalizar_unidades(unidades_raw):
    if isinstance(unidades_raw, dict):
        return {
            str(phone_number_id).strip(): int(id_unidade)
            for phone_number_id, id_unidade in unidades_raw.items()
            if phone_number_id and _id_unidade_valido(id_unidade)
        }

    if isinstance(unidades_raw, list):
        unidades = {}

        for unidade in unidades_raw:
            if isinstance(unidade, dict):
                phone_number_id = unidade.get("phone_number_id")
                id_unidade = unidade.get("id_unidade")
            else:
                try:
                    phone_number_id, id_unidade = unidade[0], unidade[1]
                except (TypeError, IndexError):
                    continue

            if phone_number_id and _id_unidade_valido(id_unidade):
                unidades[str(phone_number_id).strip()] = int(id_unidade)

        return unidades

    return {}


def _id_unidade_valido(id_unidade):
    try:
        return int(id_unidade) > 0
    except (TypeError, ValueError):
        return False


def _normalizar_phone_number_id(id_phone_unidade):
    if id_phone_unidade is None:
        return None

    phone_key = str(id_phone_unidade).strip()
    return phone_key or None