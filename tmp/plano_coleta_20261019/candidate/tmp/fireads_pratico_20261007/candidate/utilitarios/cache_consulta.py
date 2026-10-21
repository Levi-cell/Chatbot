"""Consulta manual dos bloqueios temporários armazenados no Redis."""

import argparse
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def consultar_bloqueios_cache(redis_client, limite=200):
    """Retorna no máximo ``limite`` bloqueios sem materializar todo o Redis."""
    resultados = []

    for chave in redis_client.scan_iter(
        match="conversa_bloqueada:*",
        count=100,
    ):
        dados = redis_client.hgetall(chave)
        ttl = redis_client.ttl(chave)
        expira_em = (
            datetime.now(timezone.utc) + timedelta(seconds=ttl)
            if ttl > 0
            else None
        )
        resultados.append(
            {
                "chave": chave,
                "telefone": dados.get("cliente_telefone"),
                "phone_number_id": dados.get("id_phone_unidade"),
                "finalizou_em": dados.get("finalizou_em"),
                "bloqueio_dias": dados.get("bloqueio_dias"),
                "ttl": ttl,
                "expira_em": expira_em,
            }
        )

        if len(resultados) >= limite:
            break

    return resultados


def _mascarar(valor, visivel_inicio=4, visivel_fim=3):
    texto = str(valor or "")
    if len(texto) <= visivel_inicio + visivel_fim:
        return "*" * len(texto)
    return f"{texto[:visivel_inicio]}...{texto[-visivel_fim:]}"


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Consulta bloqueios temporários no Redis remoto.",
    )
    parser.add_argument(
        "--limite",
        type=int,
        default=200,
        help="quantidade máxima de registros (1 a 2000)",
    )
    parser.add_argument(
        "--mostrar-identificadores",
        action="store_true",
        help="exibe chave, telefone e phone ID completos",
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

    if not 1 <= args.limite <= 2000:
        parser.error("--limite deve estar entre 1 e 2000")

    try:
        from utilitarios.bootstrap import configurar_ambiente_utilitario

        configurar_ambiente_utilitario(args.env_file)

        from core.cache.redis_client import (
            get_redis_safe,
            validar_redis_remoto,
        )

        redis_client = get_redis_safe(retries=1, delay=0, validate=True)
        try:
            validar_redis_remoto(redis_client)
            resultados = consultar_bloqueios_cache(
                redis_client,
                args.limite,
            )
        finally:
            redis_client.close()

        print(f"Total exibido: {len(resultados)}")
        for item in resultados:
            chave = item["chave"]
            telefone = item["telefone"]
            phone_number_id = item["phone_number_id"]

            if not args.mostrar_identificadores:
                chave = _mascarar(chave)
                telefone = _mascarar(telefone)
                phone_number_id = _mascarar(phone_number_id)

            print("\n" + "=" * 70)
            print("Chave:", chave)
            print("Telefone:", telefone)
            print("Phone Number ID:", phone_number_id)
            print("Finalizou em:", item["finalizou_em"])
            print("Dias de bloqueio:", item["bloqueio_dias"])
            print("TTL em segundos:", item["ttl"])
            print("Expira aproximadamente em:", item["expira_em"])
        return 0
    except Exception as exc:
        print(
            f"CONSULTA_CACHE_FALHOU: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
