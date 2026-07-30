"""Operações manuais e controladas sobre o cache Redis remoto."""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if __name__ == "__main__":
    from operations.bootstrap import configure_local_operations

    configure_local_operations()

from core.cache.cache_unidade import (
    CACHE_DB_VERSION_KEY,
    CACHE_TEMP_KEY,
    CACHE_VERSION_KEY,
    REDIS_KEY,
    recarregar_cache_unidades_ou_erro,
)
from core.cache.runtime.cache_cliente import REDIS_PREFIX as CLIENTE_PREFIX
from core.cache.runtime.cache_conversas_bloqueadas import (
    REDIS_PREFIX as CONVERSA_BLOQUEADA_PREFIX,
)
from core.cache.runtime.cache_flood_redis import RATE_PREFIX
from core.cache.runtime.cache_webhook_erro_inesperado import (
    REDIS_PREFIX as ERRO_INESPERADO_PREFIX,
)
from core.cache.redis_client import get_redis_safe, validar_redis_remoto


logger = logging.getLogger("operations.cache_reset")

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
    f"{ERRO_INESPERADO_PREFIX}:*",
)


def resetar_cache_operacional(redis_client=None):
    """Remove estado efêmero sem apagar o cache de unidades."""
    redis = redis_client or get_redis_safe(retries=1, delay=0)
    destino = validar_redis_remoto(redis)
    removidas_por_padrao = {
        padrao: _remover_por_padrao(redis, padrao)
        for padrao in PADROES_OPERACIONAIS_RESET
    }
    total_removido = sum(removidas_por_padrao.values())
    logger.warning(
        "cache_operacional_resetado | destino=%s total=%s por_padrao=%s",
        destino,
        total_removido,
        removidas_por_padrao,
    )
    return {
        "destino": destino,
        "chaves_por_padrao": removidas_por_padrao,
        "total_removido": total_removido,
    }


def resetar_bloqueios_conversa(redis_client=None):
    """Remove somente os bloqueios temporários de conversa."""
    redis = redis_client or get_redis_safe(retries=1, delay=0)
    destino = validar_redis_remoto(redis)
    padrao = f"{CONVERSA_BLOQUEADA_PREFIX}:*"
    total_removido = _remover_por_padrao(redis, padrao)
    logger.warning(
        "cache_bloqueios_resetado | destino=%s total=%s padrao=%s",
        destino,
        total_removido,
        padrao,
    )
    return {
        "destino": destino,
        "padrao": padrao,
        "total_removido": total_removido,
    }


def recarregar_unidades():
    """Reconstrói de forma explícita o cache derivado de unidades."""
    total = recarregar_cache_unidades_ou_erro()
    return {"unidades_recriadas": total}


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


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Manutenção controlada do cache Redis remoto.",
    )
    modos = parser.add_mutually_exclusive_group(required=True)
    modos.add_argument(
        "--operacional",
        action="store_true",
        help="remove caches efêmeros de clientes, bloqueios e proteções",
    )
    modos.add_argument(
        "--bloqueios",
        action="store_true",
        help="remove apenas bloqueios temporários de conversa",
    )
    modos.add_argument(
        "--unidades",
        action="store_true",
        help="reconstrói o cache derivado de unidades a partir do banco",
    )
    parser.add_argument(
        "--confirmar",
        action="store_true",
        help="confirma a exclusão de bloqueios temporários",
    )
    return parser


def main(argv=None):
    parser = criar_parser()
    args = parser.parse_args(argv)

    if args.bloqueios and not args.confirmar:
        parser.error("--bloqueios exige --confirmar")

    try:
        if args.bloqueios:
            resultado = resetar_bloqueios_conversa()
            print(
                "RESET_CACHE_BLOQUEIOS_OK "
                f"total_removido={resultado['total_removido']} "
                f"destino={resultado['destino']} "
                f"padrao={resultado['padrao']}"
            )
            return 0

        if args.unidades:
            resultado = recarregar_unidades()
            print(
                "RECARREGAR_CACHE_UNIDADES_OK "
                f"unidades={resultado['unidades_recriadas']}"
            )
            return 0

        resultado = resetar_cache_operacional()
        print(
            "RESET_CACHE_OPERACIONAL_OK "
            f"total_removido={resultado['total_removido']} "
            f"destino={resultado['destino']} "
            f"por_padrao={resultado['chaves_por_padrao']}"
        )
        return 0
    except Exception as exc:
        logger.exception("cache_operacao_falhou | erro=%s", exc)
        print(
            f"OPERACAO_CACHE_FALHOU: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
