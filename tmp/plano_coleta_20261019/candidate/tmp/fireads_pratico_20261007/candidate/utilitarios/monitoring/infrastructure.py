"""Healthcheck manual do PostgreSQL e do Redis remotos."""

import argparse
import ipaddress
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from utilitarios.bootstrap import configurar_ambiente_local


def verificar_postgresql(*, connection_factory=None):
    if connection_factory is None:
        configurar_ambiente_local()
        from core.database.connection_aws import get_conn

        connection_factory = get_conn

    conn = connection_factory(
        application_name="utilitarios_infrastructure_readonly",
    )
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                current_database(),
                current_user,
                inet_server_addr()::text;
            """
        )
        banco, usuario, endereco = cursor.fetchone()
        return {
            "ok": True,
            "banco": banco,
            "usuario": usuario,
            "endereco": endereco,
            "remoto": _endereco_remoto(endereco),
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def verificar_redis(*, redis_factory=None):
    if redis_factory is None:
        configurar_ambiente_local()
        from core.cache.redis_client import (
            get_redis_safe,
            validar_redis_remoto,
        )

        redis = get_redis_safe(retries=1, delay=0)
        destino = validar_redis_remoto(redis)
    else:
        redis = redis_factory()
        from core.cache.redis_client import validar_redis_remoto

        destino = validar_redis_remoto(redis)

    return {
        "ok": bool(redis.ping()),
        "destino": destino,
        "remoto": True,
    }


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Verifica as conexões remotas usadas pela aplicação.",
    )
    parser.add_argument(
        "--only",
        choices=("postgresql", "redis"),
        help="limita a verificação a um dos serviços",
    )
    return parser


def main(argv=None):
    args = criar_parser().parse_args(argv)
    try:
        if args.only in {None, "postgresql"}:
            banco = verificar_postgresql()
            if not banco["remoto"]:
                raise RuntimeError(
                    f"PostgreSQL local detectado: {banco['endereco']}"
                )
            print(
                "POSTGRESQL_REMOTO_OK "
                f"banco={banco['banco']} endereço={banco['endereco']}"
            )

        if args.only in {None, "redis"}:
            redis = verificar_redis()
            print(f"REDIS_REMOTO_OK destino={redis['destino']}")
        return 0
    except Exception as exc:
        print(
            f"INFRAESTRUTURA_FALHOU: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


def _endereco_remoto(endereco):
    if not endereco:
        return False
    ip = ipaddress.ip_address(str(endereco))
    return not (ip.is_loopback or ip.is_unspecified)


if __name__ == "__main__":
    raise SystemExit(main())
