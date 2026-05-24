import hashlib
import logging
from datetime import datetime, timedelta, timezone

from core.database.redis_client import get_redis_safe
from core.logging_config import short_value


logger = logging.getLogger("cache.bloqueia_conversa")

REDIS_PREFIX = "conversa_bloqueada"
BLOQUEIO_DIAS = 30
TTL_PADRAO_SEGUNDOS = BLOQUEIO_DIAS * 24 * 60 * 60


def conversa_esta_bloqueada_cache(cliente_telefone, id_phone_unidade):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    try:
        r = get_redis_safe()
        return bool(r.exists(key))

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_indisponivel | cliente=%s unidade=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        return False


def registrar_bloqueio_conversa_cache(
    cliente_telefone,
    id_phone_unidade,
    finalizou_em=None,
):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    ttl = _calcular_ttl(finalizou_em)

    if ttl <= 0:
        logger.info(
            "cache_bloqueio_ignorado | motivo=ttl_expirado cliente=%s unidade=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
        )
        return False

    payload = {
        "cliente_telefone": str(cliente_telefone),
        "id_phone_unidade": str(id_phone_unidade),
        "finalizou_em": str(finalizou_em) if finalizou_em else "",
    }

    try:
        r = get_redis_safe()
        r.hset(key, mapping=payload)
        r.expire(key, ttl)

        logger.info(
            "cache_bloqueio_registrado | cliente=%s unidade=%s ttl=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            ttl,
        )
        return True

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_registrar_falhou | cliente=%s unidade=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        return False


def remover_bloqueio_conversa_cache(cliente_telefone, id_phone_unidade):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    try:
        r = get_redis_safe()
        return bool(r.delete(key))

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_remover_falhou | cliente=%s unidade=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        return False

 ### EXCLUSIVO PARA DEV
def limpar_cache_conversas_bloqueadas_dev():
    # Exclusivo para DEV: use ao recriar o banco para remover bloqueios antigos do Redis.
    try:
        r = get_redis_safe()
        total_removido = 0
        lote = []

        for key in r.scan_iter(match=f"{REDIS_PREFIX}:*", count=500):
            lote.append(key)

            if len(lote) >= 500:
                total_removido += r.delete(*lote)
                lote = []

        if lote:
            total_removido += r.delete(*lote)

        logger.warning(
            "cache_bloqueio_dev_limpo | chaves_removidas=%s",
            total_removido,
        )
        return total_removido

    except Exception as exc:
        logger.warning("cache_bloqueio_dev_limpeza_falhou | erro=%s", exc)
        return 0


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


def _calcular_ttl(finalizou_em):
    if finalizou_em is None:
        return TTL_PADRAO_SEGUNDOS

    if isinstance(finalizou_em, str):
        finalizou_em = datetime.fromisoformat(finalizou_em)

    if finalizou_em.tzinfo is None:
        finalizou_em = finalizou_em.replace(tzinfo=timezone.utc)

    bloqueado_ate = finalizou_em + timedelta(days=BLOQUEIO_DIAS)
    agora = datetime.now(timezone.utc)

    return int((bloqueado_ate - agora).total_seconds())
