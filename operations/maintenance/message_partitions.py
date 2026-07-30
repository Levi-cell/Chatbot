import argparse
import logging
import sys
from datetime import datetime, timezone, date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from operations.bootstrap import configure_local_operations

logger = logging.getLogger("db.particoes")

def add_months(base_date, months):
    """Avanca meses corretamente."""
    year = base_date.year + (base_date.month - 1 + months) // 12
    month = (base_date.month - 1 + months) % 12 + 1
    return date(year, month, 1)


def criar_particoes_historico_mensagens(
    meses_a_frente=3,
    *,
    connection_factory=None,
):
    """
    Cria particoes mensais para historico_mensagens.

    Estrategia:
    - Cria mes atual + N meses a frente
    - Seguro para rodar 1x por mes
    """

    if meses_a_frente < 0:
        raise ValueError("meses_a_frente nao pode ser negativo")

    hoje = datetime.now(timezone.utc).date()
    primeiro_dia_mes = hoje.replace(day=1)

    particoes_criadas = []

    if connection_factory is None:
        configure_local_operations()
        from core.database.connection_aws import get_conn

        connection_factory = get_conn

    conn = None
    try:
        conn = connection_factory(
            application_name="operations_message_partitions",
        )
        cursor = conn.cursor()

        for i in range(meses_a_frente + 1):
            inicio = add_months(primeiro_dia_mes, i)
            fim = add_months(primeiro_dia_mes, i + 1)

            nome_particao = f"historico_{inicio.year}_{inicio.month:02d}"

            sql = f"""
            CREATE TABLE IF NOT EXISTS chatbot.{nome_particao}
            PARTITION OF chatbot.historico_mensagens
            FOR VALUES FROM (%s) TO (%s);
            """

            cursor.execute(sql, (inicio, fim))
            particoes_criadas.append(nome_particao)

        conn.commit()

        logger.info(
            "particoes_garantidas | acao=criar_particoes meses_a_frente=%s total=%s particoes=%s",
            meses_a_frente,
            len(particoes_criadas),
            ",".join(particoes_criadas),
        )
        return particoes_criadas

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "particoes_erro | acao=criar_particoes meses_a_frente=%s erro=%s",
            meses_a_frente,
            erro,
        )
        raise

    finally:
        if conn:
            conn.close()


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Garante partições mensais do histórico de mensagens.",
    )
    parser.add_argument("--months-ahead", type=int, default=3)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="confirma a execução de DDL no banco configurado",
    )
    return parser


def main(argv=None):
    parser = criar_parser()
    args = parser.parse_args(argv)
    if not args.confirm:
        parser.error("a criação de partições exige --confirm")

    try:
        particoes = criar_particoes_historico_mensagens(
            args.months_ahead,
        )
    except Exception as exc:
        print(
            f"PARTICOES_FALHARAM: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        "PARTICOES_OK "
        f"total={len(particoes)} nomes={','.join(particoes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
