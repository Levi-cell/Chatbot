import hashlib
import logging
import time

from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value


logger = logging.getLogger("cache.bloqueio_meta")

RATE_PREFIX = "webhook_flood_rate"
DEDUPLICACAO_TTL_SEGUNDOS = 2 * 60 * 60

_AVALIAR_FLOOD_LUA = """
local dedupe_key = KEYS[1]
local dedupe_ttl = tonumber(ARGV[1])
local evento_novo = redis.call(
    "SET",
    dedupe_key,
    "1",
    "NX",
    "EX",
    dedupe_ttl
)
local resposta = {}

if evento_novo then
    table.insert(resposta, 1)
else
    table.insert(resposta, 0)
end

for indice = 2, #KEYS do
    local total

    if evento_novo then
        total = redis.call("INCR", KEYS[indice])

        if total == 1 then
            redis.call(
                "EXPIRE",
                KEYS[indice],
                tonumber(ARGV[indice])
            )
        end
    else
        total = tonumber(
            redis.call("GET", KEYS[indice]) or "0"
        )
    end

    table.insert(resposta, total)
end

return resposta
"""


def avaliar_flood_redis(
    wa_id_cliente,
    phone_id_unidade,
    id_hash_msg,
    regras,
):
    if (
        not wa_id_cliente
        or not phone_id_unidade
        or not id_hash_msg
        or not regras
    ):
        return {
            "redis_ok": True,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "dados_invalidos",
            "regra": None,
            "evento_novo": False,
        }

    try:
        redis = get_redis_safe(
            retries=1,
            delay=0,
            validate=False,
        )
        agora = time.time()
        digest_par = _digest_par(
            wa_id_cliente,
            phone_id_unidade,
        )
        digest_wamid = _digest_wamid(id_hash_msg)
        chaves = [
            _dedupe_key(digest_par, digest_wamid),
        ]
        argumentos = [
            DEDUPLICACAO_TTL_SEGUNDOS,
        ]

        for regra in regras:
            janela_segundos = regra["janela_segundos"]
            janela = int(agora // janela_segundos)
            chaves.append(
                _rate_key(
                    digest_par,
                    janela_segundos,
                    janela,
                )
            )
            argumentos.append(
                janela_segundos + 10,
            )

        # A deduplicação e todos os incrementos são uma única operação
        # atômica. Duas entregas concorrentes do mesmo WAMID não conseguem
        # vencer o SET NX ao mesmo tempo.
        resultados = redis.eval(
            _AVALIAR_FLOOD_LUA,
            len(chaves),
            *chaves,
            *argumentos,
        )
        maior_total = 0
        evento_novo = bool(resultados[0])

        for indice, regra in enumerate(
            regras,
            start=1,
        ):
            total = int(resultados[indice])
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
                    "evento_novo": evento_novo,
                }

        return {
            "redis_ok": True,
            "bloqueado": False,
            "flood": False,
            "total": maior_total,
            "motivo": "redis",
            "regra": None,
            "evento_novo": evento_novo,
        }

    except Exception as exc:
        logger.warning(
            "rate_limit_redis_falhou | "
            "acao=fallback_banco wa_id_cliente=%s "
            "phone_id_unidade=%s id_hash_msg=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            short_value(id_hash_msg),
            exc,
        )
        return {
            "redis_ok": False,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "redis_indisponivel",
            "regra": None,
            "evento_novo": False,
        }


def _dedupe_key(digest_par, digest_wamid):
    return (
        f"{RATE_PREFIX}:{{{digest_par}}}:"
        f"wamid:{digest_wamid}"
    )


def _rate_key(digest_par, janela_segundos, janela):
    return (
        f"{RATE_PREFIX}:{{{digest_par}}}:"
        f"contador:{janela_segundos}:{janela}"
    )


def _digest_par(wa_id_cliente, phone_id_unidade):
    wa_id_cliente = _normalizar(wa_id_cliente)
    phone_id_unidade = _normalizar(phone_id_unidade)

    if not wa_id_cliente or not phone_id_unidade:
        return None

    raw = f"{phone_id_unidade}:{wa_id_cliente}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _digest_wamid(id_hash_msg):
    id_hash_msg = _normalizar(id_hash_msg)

    if not id_hash_msg:
        return None

    return hashlib.sha256(
        id_hash_msg.encode("utf-8")
    ).hexdigest()


def _normalizar(valor):
    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None
