"""Operações manuais e controladas sobre o cache Redis remoto."""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger("utilitarios.cache_reset")


def resetar_cache_operacional(redis_client=None):
    """Remove estado efêmero sem apagar o cache de unidades."""
    dependencias = _carregar_dependencias_cache()
    redis = redis_client or dependencias["get_redis_safe"](
        retries=1,
        delay=0,
    )
    destino = dependencias["validar_redis_remoto"](redis)
    removidas_por_padrao = {
        padrao: _remover_por_padrao(redis, padrao)
        for padrao in dependencias["padroes_operacionais"]
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
    dependencias = _carregar_dependencias_cache()
    redis = redis_client or dependencias["get_redis_safe"](
        retries=1,
        delay=0,
    )
    destino = dependencias["validar_redis_remoto"](redis)
    padrao = dependencias["padrao_bloqueios"]
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
    dependencias = _carregar_dependencias_cache()
    total = dependencias["recarregar_cache_unidades_ou_erro"]()
    return {"unidades_recriadas": total}


def _carregar_dependencias_cache():
    """Importa o runtime somente depois de a fonte de ambiente ser escolhida."""
    from core.cache.cache_unidade import recarregar_cache_unidades_ou_erro
    from core.cache.redis_client import get_redis_safe, validar_redis_remoto
    from core.cache.runtime.cache_cliente import REDIS_PREFIX as cliente_prefix
    from core.cache.runtime.cache_conversas_bloqueadas import (
        REDIS_PREFIX as conversa_bloqueada_prefix,
    )
    from core.cache.runtime.cache_flood_redis import RATE_PREFIX
    from core.cache.runtime.cache_webhook_erro_inesperado import (
        REDIS_PREFIX as erro_inesperado_prefix,
    )

    return {
        "get_redis_safe": get_redis_safe,
        "validar_redis_remoto": validar_redis_remoto,
        "recarregar_cache_unidades_ou_erro": (
            recarregar_cache_unidades_ou_erro
        ),
        "padrao_bloqueios": f"{conversa_bloqueada_prefix}:*",
        "padroes_operacionais": (
            f"{cliente_prefix}*",
            f"{conversa_bloqueada_prefix}:*",
            f"{RATE_PREFIX}:*",
            f"{erro_inesperado_prefix}:*",
        ),
    }


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
        help="confirma a exclusão das chaves selecionadas",
    )
    parser.add_argument(
        "--env-file",
        help=(
            "usa explicitamente este arquivo de ambiente; sem a opção, "
            "usa utilitarios/local_settings.py"
        ),
    )
    return parser


def main(argv=None):
    parser = criar_parser()
    args = parser.parse_args(argv)

    if not args.confirmar:
        parser.error("toda alteração de cache exige --confirmar")

    try:
        from utilitarios.bootstrap import configurar_ambiente_utilitario

        configurar_ambiente_utilitario(args.env_file)

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
