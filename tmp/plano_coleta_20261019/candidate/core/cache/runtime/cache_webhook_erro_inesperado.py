import hashlib
import logging

from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value


logger = logging.getLogger(
    "cache.webhook_erro_inesperado"
)

REDIS_PREFIX = "webhook_erro_inesperado"
MAX_RESPOSTAS_503_POR_WAMID = 3
TTL_TENTATIVAS_SEGUNDOS = 7 * 24 * 60 * 60


def registrar_tentativa_erro_inesperado(id_hash_msg):
    id_hash_msg = _normalizar(id_hash_msg)

    if not id_hash_msg:
        return {
            "cache_ok": False,
            "identificavel": False,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "wamid_ausente",
        }

    try:
        redis = get_redis_safe(
            retries=1,
            delay=0,
            validate=False,
        )
        key = _cache_key(id_hash_msg)
        pipe = redis.pipeline(transaction=True)
        pipe.incr(key)
        pipe.expire(
            key,
            TTL_TENTATIVAS_SEGUNDOS,
        )
        resultados = pipe.execute()
        tentativa = int(resultados[0])
        retornar_503 = (
            tentativa
            <= MAX_RESPOSTAS_503_POR_WAMID
        )

        logger.warning(
            "webhook_erro_inesperado_contabilizado | "
            "acao=%s id_hash_msg=%s tentativa=%s "
            "limite_503=%s ttl=%s",
            (
                "retornar_503"
                if retornar_503
                else "retornar_200_e_ignorar"
            ),
            short_value(id_hash_msg),
            tentativa,
            MAX_RESPOSTAS_503_POR_WAMID,
            TTL_TENTATIVAS_SEGUNDOS,
        )
        return {
            "cache_ok": True,
            "identificavel": True,
            "tentativa": tentativa,
            "retornar_503": retornar_503,
            "motivo": (
                "dentro_limite_503"
                if retornar_503
                else "limite_503_esgotado"
            ),
        }

    except Exception as exc:
        logger.exception(
            "webhook_erro_inesperado_contador_falhou | "
            "acao=retornar_200_e_ignorar "
            "id_hash_msg=%s erro=%s",
            short_value(id_hash_msg),
            exc,
        )
        return {
            "cache_ok": False,
            "identificavel": True,
            "tentativa": None,
            "retornar_503": False,
            "motivo": "redis_indisponivel",
        }


def _cache_key(id_hash_msg):
    digest = hashlib.sha256(
        id_hash_msg.encode("utf-8")
    ).hexdigest()
    return f"{REDIS_PREFIX}:{digest}"


def _normalizar(valor):
    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None
