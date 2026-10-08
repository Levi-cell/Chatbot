import hashlib
import logging
from datetime import datetime, timedelta, timezone

from core.database.connection_aws import get_conn
from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value
from core.repositories.fluxo.politicas import (
    buscar_bloqueio_ativo_por_cliente_unidade,
)


logger = logging.getLogger("cache.bloqueia_conversa")

REDIS_PREFIX = "conversa_bloqueada"


class ValidacaoBloqueioConversaIndisponivel(Exception):
    pass


def conversa_esta_bloqueada_cache(cliente_telefone, id_phone_unidade):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        return bool(r.exists(key))

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_indisponivel | acao=fallback_banco cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )

    return _conversa_esta_bloqueada_banco_e_repara_cache(
        cliente_telefone,
        id_phone_unidade,
    )


def registrar_bloqueio_conversa_cache(
    cliente_telefone,
    id_phone_unidade,
    finalizou_em,
    bloqueio_dias,
    redis_retries=1,
    redis_delay=0,
):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    ttl = _calcular_ttl(finalizou_em, bloqueio_dias)

    if ttl <= 0:
        logger.info(
            "cache_bloqueio_ignorado | motivo=ttl_expirado acao=nao_registrar cliente=%s phone_number_id=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
        )
        return False

    payload = {
        "cliente_telefone": str(cliente_telefone),
        "id_phone_unidade": str(id_phone_unidade),
        "finalizou_em": str(finalizou_em) if finalizou_em else "",
        "bloqueio_dias": str(bloqueio_dias),
    }

    try:
        r = get_redis_safe(retries=redis_retries, delay=redis_delay, validate=False)
        r.hset(key, mapping=payload)
        r.expire(key, ttl)

        logger.info(
            "cache_bloqueio_registrado | acao=registrar cliente=%s phone_number_id=%s ttl=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            ttl,
        )
        return True

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_registrar_falhou | acao=ignorar cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        return False


def remover_bloqueio_conversa_cache(
    cliente_telefone,
    id_phone_unidade,
    redis_retries=1,
    redis_delay=0,
):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    try:
        r = get_redis_safe(retries=redis_retries, delay=redis_delay, validate=False)
        return bool(r.delete(key))

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_remover_falhou | acao=ignorar cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        return False


def _conversa_esta_bloqueada_banco_e_repara_cache(
    cliente_telefone,
    id_phone_unidade,
):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        bloqueio = buscar_bloqueio_ativo_por_cliente_unidade(
            cliente_telefone,
            id_phone_unidade,
            cursor,
        )

        if bloqueio is None:
            remover_bloqueio_conversa_cache(
                cliente_telefone,
                id_phone_unidade,
                redis_retries=1,
                redis_delay=0,
            )
            return False

        registrar_bloqueio_conversa_cache(
            cliente_telefone,
            id_phone_unidade,
            bloqueio.finalizou_em,
            bloqueio.bloqueio_dias,
            redis_retries=1,
            redis_delay=0,
        )

        return True

    except Exception as exc:
        logger.exception(
            "fallback_banco_bloqueio_falhou | acao=levantar_indisponibilidade cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        raise ValidacaoBloqueioConversaIndisponivel(
            "Nao foi possivel validar o bloqueio da conversa no Redis nem no banco"
        ) from exc

    finally:
        if conn:
            conn.close()


def _cache_key(cliente_telefone, id_phone_unidade):
    cliente = _normalizar(cliente_telefone)
    unidade = _normalizar(id_phone_unidade)

    if not cliente or not unidade:
        return None

    raw = f"{unidade}:{cliente}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return f"{REDIS_PREFIX}:{digest}"


def _normalizar(valor):
    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None


def _calcular_ttl(finalizou_em, bloqueio_dias):
    if bloqueio_dias <= 0:
        return 0

    if finalizou_em is None:
        return bloqueio_dias * 24 * 60 * 60

    if isinstance(finalizou_em, str):
        finalizou_em = datetime.fromisoformat(finalizou_em)

    if finalizou_em.tzinfo is None:
        finalizou_em = finalizou_em.replace(tzinfo=timezone.utc)

    bloqueado_ate = finalizou_em + timedelta(days=bloqueio_dias)
    agora = datetime.now(timezone.utc)

    return int((bloqueado_ate - agora).total_seconds())
