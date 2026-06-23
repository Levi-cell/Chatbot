import logging
import threading
import time

from core.database.connection_aws import get_conn
from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value
from core.repositories.cache_control import buscar_versao_cache_unidades
from core.repositories.querys import buscar_id_unidade_por_phone_id, pegar_unidades


logger = logging.getLogger("cache.unidades")

REDIS_KEY = "unidades_cache"
CACHE_VERSION_KEY = "unidades_cache_version"
CACHE_DB_VERSION_KEY = "unidades_cache_db_version"
CACHE_TEMP_KEY = f"{REDIS_KEY}:tmp"
VERSAO_CHECK_INTERVAL_SEGUNDOS = 300

_redis_unidades_falhou = False
_ultima_checagem_versao = 0
_versao_lock = threading.Lock()


class UnidadeNaoEncontrada(Exception):
    pass


class CacheUnidadesIndisponivel(Exception):
    pass


class ValidacaoUnidadeIndisponivel(Exception):
    pass


def carregar_unidades_redis_primeira_vez():
    conn = None

    try:
        conn = get_conn(application_name="cache_chatbot")
        cursor = conn.cursor()
        return carregar_cache_redis(cursor)

    finally:
        if conn:
            conn.close()


def recarregar_cache_unidades():
    conn = None

    try:
        conn = get_conn(application_name="cache_chatbot")
        cursor = conn.cursor()
        return carregar_cache_redis(cursor)

    except Exception as exc:
        logger.exception("cache_recarregar_falhou | origem=admin acao=manter_cache_atual erro=%s", exc)
        return None

    finally:
        if conn:
            conn.close()


def validar_cache_unidades_disponivel_ou_erro():
    try:
        r = get_redis_safe(retries=1, delay=0, validate=True)
        key = f"{REDIS_KEY}:admin_preflight"
        r.set(key, "ok", ex=10)
        r.delete(key)

        logger.debug("cache_unidades_preflight_ok | acao=permitir_admin")
        return True

    except Exception as exc:
        _marcar_redis_falhou()
        logger.exception(
            "cache_unidades_preflight_falhou | acao=bloquear_admin erro=%s",
            exc,
        )
        raise CacheUnidadesIndisponivel(
            "Redis indisponivel para atualizar cache de unidades"
        ) from exc


def recarregar_cache_unidades_ou_erro(cursor=None):
    conn = None

    try:
        cursor_uso = cursor

        if cursor_uso is None:
            conn = get_conn(application_name="cache_chatbot")
            cursor_uso = conn.cursor()

        return carregar_cache_redis(
            cursor_uso,
            redis_retries=1,
            redis_delay=0,
        )

    except Exception as exc:
        _marcar_redis_falhou()
        logger.exception(
            "cache_recarregar_falhou | origem=admin acao=bloquear_alteracao erro=%s",
            exc,
        )
        raise CacheUnidadesIndisponivel(
            "Redis falhou ao recriar cache de unidades"
        ) from exc

    finally:
        if conn:
            conn.close()


def carregar_cache_redis(cursor, redis_retries=3, redis_delay=2):
    r = get_redis_safe(retries=redis_retries, delay=redis_delay)
    unidades = _normalizar_unidades(pegar_unidades(cursor))
    versao_banco = buscar_versao_cache_unidades(cursor)
    total = _salvar_cache(r, unidades, versao_banco)

    _marcar_versao_conferida()
    logger.info("cache_atualizado | acao=salvar_redis unidades=%s versao=%s", total, versao_banco)
    return total


def carregar_unidades_cache_webhook(cursor):
    return carregar_cache_redis(cursor)


def obter_id_unidade_redis_ou_plsql(id_phone_unidade, cursor):
    phone_key = _normalizar_phone_number_id(id_phone_unidade)

    if phone_key is None:
        raise UnidadeNaoEncontrada("phone_number_id invalido")

    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        _sincronizar_cache_unidades_por_versao(r, origem="worker", cursor=cursor)

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
        _marcar_redis_falhou()
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


def garantir_cache_unidades_se_necessario(cursor):
    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        _sincronizar_cache_unidades_por_versao(r, origem="manual", cursor=cursor)

        if not _cache_valido(r):
            logger.info("cache_invalido | acao=recarregar origem=manual")
            return carregar_cache_redis(cursor, redis_retries=1, redis_delay=0)

        return None

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning("cache_validacao_falhou | origem=manual acao=manter_cache_atual erro=%s", exc)
        return None


def unidade_esta_ativa(phone_number_id):
    phone_key = _normalizar_phone_number_id(phone_number_id)

    if phone_key is None:
        return False

    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        _sincronizar_cache_unidades_por_versao(r, origem="webhook")

        if _cache_valido(r):
            return bool(r.hexists(REDIS_KEY, phone_key))

        logger.warning(
            "cache_invalido | acao=fallback_banco origem=webhook phone_number_id=%s",
            short_value(phone_key),
        )

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning(
            "cache_indisponivel | acao=fallback_banco origem=webhook phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )

    return _unidade_esta_ativa_banco_e_repara_cache(phone_key)


def _unidade_esta_ativa_banco_e_repara_cache(phone_key):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        id_unidade = buscar_id_unidade_por_phone_id(phone_key, cursor)

        _tentar_recarregar_cache(cursor, origem="webhook")

        return _id_unidade_valido(id_unidade)

    except Exception as exc:
        logger.exception(
            "fallback_banco_unidade_falhou | origem=webhook acao=levantar_indisponibilidade phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )
        raise ValidacaoUnidadeIndisponivel(
            "Nao foi possivel validar a unidade no Redis nem no banco"
        ) from exc

    finally:
        if conn:
            conn.close()


def _sincronizar_cache_unidades_por_versao(r, origem, cursor=None):
    if not _deve_conferir_versao():
        return None

    with _versao_lock:
        if not _deve_conferir_versao():
            return None

        conn = None

        try:
            cursor_uso = cursor

            if cursor_uso is None:
                conn = get_conn(application_name=_application_name_por_origem(origem))
                cursor_uso = conn.cursor()

            versao_banco = buscar_versao_cache_unidades(cursor_uso)
            versao_redis = _int_ou_none(r.get(CACHE_DB_VERSION_KEY))

            if versao_redis != versao_banco or not _cache_valido(r):
                logger.info(
                    "cache_versao_divergente | origem=%s redis=%s banco=%s acao=recarregar",
                    origem,
                    versao_redis,
                    versao_banco,
                )
                return carregar_cache_redis(cursor_uso, redis_retries=1, redis_delay=0)

            _marcar_versao_conferida()
            return None

        except Exception as exc:
            _marcar_checagem_tentada()
            logger.warning(
                "cache_versao_checar_falhou | origem=%s acao=manter_cache_atual erro=%s",
                origem,
                exc,
            )
            return None

        finally:
            if conn:
                conn.close()


def _tentar_recarregar_cache(cursor, origem):
    try:
        return carregar_cache_redis(cursor, redis_retries=1, redis_delay=0)

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning(
            "cache_reparo_falhou | origem=%s acao=manter_cache_atual erro=%s",
            origem,
            exc,
        )
        return None


def _salvar_cache(r, unidades, versao_banco):
    total = len(unidades)

    pipe = r.pipeline()
    pipe.delete(CACHE_TEMP_KEY)

    if total > 0:
        pipe.hset(CACHE_TEMP_KEY, mapping=unidades)
        pipe.rename(CACHE_TEMP_KEY, REDIS_KEY)
    else:
        pipe.delete(REDIS_KEY)

    pipe.set(CACHE_VERSION_KEY, total)
    pipe.set(CACHE_DB_VERSION_KEY, versao_banco)
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

    except Exception as exc:
        logger.warning(
            "cache_validacao_erro | acao=considerar_invalido_e_usar_fallback erro=%s",
            exc,
        )
        return False


def _deve_conferir_versao():
    agora = time.monotonic()

    if _redis_unidades_falhou:
        return True

    if _ultima_checagem_versao == 0:
        return True

    return (agora - _ultima_checagem_versao) >= VERSAO_CHECK_INTERVAL_SEGUNDOS


def _marcar_redis_falhou():
    global _redis_unidades_falhou
    _redis_unidades_falhou = True


def _marcar_versao_conferida():
    global _redis_unidades_falhou, _ultima_checagem_versao
    _redis_unidades_falhou = False
    _ultima_checagem_versao = time.monotonic()


def _marcar_checagem_tentada():
    global _ultima_checagem_versao
    _ultima_checagem_versao = time.monotonic()


def _int_ou_none(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _application_name_por_origem(origem):
    if origem == "worker":
        return "worker_chatbot"

    if origem == "webhook":
        return "webhook_chatbot"

    return "cache_chatbot"


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
