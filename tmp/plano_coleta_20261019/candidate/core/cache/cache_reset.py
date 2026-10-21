import logging

from core.cache.runtime.cache_flood_redis import RATE_PREFIX
from core.cache.runtime.cache_webhook_erro_inesperado import (
    REDIS_PREFIX as ERRO_INESPERADO_PREFIX,
)
from core.cache.runtime.cache_cliente import REDIS_PREFIX as CLIENTE_PREFIX
from core.cache.runtime.cache_conversas_bloqueadas import REDIS_PREFIX as CONVERSA_BLOQUEADA_PREFIX
from core.cache.cache_unidade import (
    CACHE_DB_VERSION_KEY,
    CACHE_TEMP_KEY,
    CACHE_VERSION_KEY,
    REDIS_KEY,
    recarregar_cache_unidades,
)
from core.cache.redis_client import get_redis_safe


logger = logging.getLogger("cache.reset")

CHAVES_EXATAS_RESET = (
    REDIS_KEY,
    CACHE_VERSION_KEY,
    CACHE_DB_VERSION_KEY,
    CACHE_TEMP_KEY,
)

PADROES_RESET = (
    f"{CLIENTE_PREFIX}*",
    f"{CONVERSA_BLOQUEADA_PREFIX}:*",
    f"{RATE_PREFIX}:*",
    f"{ERRO_INESPERADO_PREFIX}:*",
)

def resetar_cache_redis_dev():
    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)

        chaves_exatas_removidas = _remover_chaves_exatas(r, CHAVES_EXATAS_RESET)
        chaves_por_prefixo_removidas = 0

        for padrao in PADROES_RESET:
            chaves_por_prefixo_removidas += _remover_por_padrao(r, padrao)

        unidades_recriadas = recarregar_cache_unidades()

        logger.warning(
            "cache_redis_dev_resetado | acao=limpar_e_recriar chaves_exatas=%s chaves_prefixo=%s unidades_recriadas=%s",
            chaves_exatas_removidas,
            chaves_por_prefixo_removidas,
            unidades_recriadas,
        )
        return {
            "chaves_exatas_removidas": chaves_exatas_removidas,
            "chaves_por_prefixo_removidas": chaves_por_prefixo_removidas,
            "unidades_recriadas": unidades_recriadas,
        }

    except Exception as exc:
        logger.warning(
            "cache_redis_dev_reset_falhou | acao=seguir_sem_cache_recriado erro=%s",
            exc,
        )
        return {
            "chaves_exatas_removidas": 0,
            "chaves_por_prefixo_removidas": 0,
            "unidades_recriadas": None,
            "erro": str(exc),
        }


def _remover_chaves_exatas(redis_client, chaves):
    if not chaves:
        return 0

    return int(redis_client.delete(*chaves))


def _remover_por_padrao(redis_client, padrao):
    total_removido = 0
    lote = []

    for key in redis_client.scan_iter(match=padrao, count=500):
        lote.append(key)

        if len(lote) >= 500:
            total_removido += int(redis_client.delete(*lote))
            lote = []

    if lote:
        total_removido += int(redis_client.delete(*lote))

    return total_removido
