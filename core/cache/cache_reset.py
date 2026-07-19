import argparse
import logging
import sys

from core.cache.runtime.cache_flood_redis import RATE_PREFIX
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

PADROES_OPERACIONAIS_RESET = (
    f"{CLIENTE_PREFIX}*",
    f"{CONVERSA_BLOQUEADA_PREFIX}:*",
    f"{RATE_PREFIX}:*",
)

# Compatibilidade com o reset completo de desenvolvimento.
PADROES_RESET = PADROES_OPERACIONAIS_RESET


def resetar_cache_operacional(redis_client=None):
    """
    Remove apenas estado operacional ligado a clientes e conversas.

    O cache de unidades e suas chaves de versao permanecem intactos. A funcao
    aceita um client apenas para facilitar testes; em producao usa a conexao
    configurada no ambiente da aplicacao.
    """

    r = (
        redis_client
        if redis_client is not None
        else get_redis_safe(retries=1, delay=0)
    )
    removidas_por_padrao = {}

    for padrao in PADROES_OPERACIONAIS_RESET:
        removidas_por_padrao[padrao] = _remover_por_padrao(r, padrao)

    total_removido = sum(removidas_por_padrao.values())
    logger.warning(
        "cache_operacional_resetado | acao=limpar_clientes_conversas_flood "
        "total=%s por_padrao=%s",
        total_removido,
        removidas_por_padrao,
    )
    return {
        "chaves_por_padrao": removidas_por_padrao,
        "total_removido": total_removido,
    }


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


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Utilitarios controlados de manutencao do cache Redis.",
    )
    parser.add_argument(
        "--operacional",
        action="store_true",
        help=(
            "remove somente cache de clientes, bloqueios de conversa e "
            "contadores de flood"
        ),
    )
    args = parser.parse_args(argv)

    if not args.operacional:
        parser.error("informe explicitamente --operacional")

    try:
        resultado = resetar_cache_operacional()
    except Exception as exc:
        logger.exception(
            "cache_operacional_reset_falhou | acao=abortar erro=%s",
            exc,
        )
        print(f"RESET_CACHE_OPERACIONAL_FALHOU: {exc}", file=sys.stderr)
        return 1

    print(
        "RESET_CACHE_OPERACIONAL_OK "
        f"total_removido={resultado['total_removido']} "
        f"por_padrao={resultado['chaves_por_padrao']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
