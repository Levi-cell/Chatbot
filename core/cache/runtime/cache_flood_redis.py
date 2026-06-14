import hashlib
import logging
import time

from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value


logger = logging.getLogger("cache.bloqueio_meta")

RATE_PREFIX = "webhook_flood_rate"


def avaliar_flood_redis(
    wa_id_cliente,
    phone_id_unidade,
    regras,
):
    if not wa_id_cliente or not phone_id_unidade:
        return {
            "redis_ok": True,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "dados_invalidos",
            "regra": None,
        }

    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        agora = time.time()
        pipe = r.pipeline()

        for regra in regras:
            janela_segundos = regra["janela_segundos"]
            janela = int(agora // janela_segundos)
            key = _rate_key(
                wa_id_cliente,
                phone_id_unidade,
                janela_segundos,
                janela,
            )
            pipe.incr(key)
            pipe.expire(key, janela_segundos + 10)

        resultados = pipe.execute()

        maior_total = 0
        indice = 0

        for regra in regras:
            total = int(resultados[indice])
            indice += 2
            maior_total = max(maior_total, total)

            if total >= regra["limite"]:
                return {
                    "redis_ok": True,
                    "bloqueado": False,
                    "flood": True,
                    "total": total,
                    "limite": regra["limite"],
                    "janela_segundos": regra["janela_segundos"],
                    "motivo": "redis",
                    "regra": regra["nome"],
                }

        return {
            "redis_ok": True,
            "bloqueado": False,
            "flood": False,
            "total": maior_total,
            "motivo": "redis",
            "regra": None,
        }

    except Exception as exc:
        logger.warning(
            "rate_limit_redis_falhou | acao=fallback_banco wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            "redis_ok": False,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "redis_indisponivel",
            "regra": None,
        }


def _rate_key(wa_id_cliente, phone_id_unidade, janela_segundos, janela):
    digest = _digest(wa_id_cliente, phone_id_unidade)
    return f"{RATE_PREFIX}:{janela_segundos}:{janela}:{digest}"


def _digest(wa_id_cliente, phone_id_unidade):
    wa_id_cliente = _normalizar(wa_id_cliente)
    phone_id_unidade = _normalizar(phone_id_unidade)

    if not wa_id_cliente or not phone_id_unidade:
        return None

    raw = f"{phone_id_unidade}:{wa_id_cliente}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalizar(valor):
    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None
