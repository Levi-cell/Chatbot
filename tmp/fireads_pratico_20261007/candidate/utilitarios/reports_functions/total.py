"""Gera dashboards HTML e relatórios PDF totais por unidade.

O instante final é congelado no começo da execução. Para cada unidade, a
janela começa no primeiro contato recebido de um cliente e termina nesse mesmo
instante final, preservando a estrutura, a consolidação e as métricas do
relatório semanal.

Uso padrão::

    python -m utilitarios.reports_functions.total

Na VM::

    python -m utilitarios.reports_functions.total \
        --env-file /etc/chatbot/chatbot.env
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from utilitarios.reports_functions import weekly


SAIDA_PADRAO = weekly.SAIDA_PADRAO
MAX_MENSAGENS_PADRAO = weekly.MAX_MENSAGENS_PADRAO


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera um dashboard HTML e um relatório PDF com todo o histórico "
            "disponível de cada unidade."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Arquivo .env explícito; sem ele usa utilitarios/local_settings.py.",
    )
    parser.add_argument(
        "--ate",
        help=(
            "Fim do período em ISO-8601. Sem fuso, considera America/Sao_Paulo; "
            "sem o parâmetro, congela o instante atual no início da execução."
        ),
    )
    parser.add_argument(
        "--id-unidade",
        type=int,
        action="append",
        dest="ids_unidade",
        help="Limita a uma unidade; pode ser repetido.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAIDA_PADRAO,
        help="Diretório raiz da saída (padrão: monitoramento).",
    )
    parser.add_argument(
        "--max-mensagens",
        type=int,
        default=MAX_MENSAGENS_PADRAO,
        help="Limite por unidade; falha sem truncar quando for excedido.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=60_000,
        help="Timeout das consultas do snapshot (padrão: 60000).",
    )
    return parser


def resolver_fim(ate: str | datetime | None = None) -> datetime:
    """Normaliza e congela o instante final em UTC."""
    return weekly.resolver_janela(dias=1, ate=ate)[1]


def coletar_primeiros_registros(
    conn: Any,
    fim: datetime,
    ids_unidade: Sequence[int] | None = None,
    statement_timeout_ms: int = 60_000,
) -> list[dict[str, Any]]:
    """Obtém o primeiro contato real de cada unidade em uma leitura consistente.

    Unidades sem mensagem recebida de cliente continuam na lista com início
    nulo para que também recebam um relatório vazio.
    """
    if statement_timeout_ms <= 0:
        raise ValueError("--statement-timeout-ms precisa ser maior que zero")

    from psycopg.rows import dict_row

    cursor = conn.cursor(row_factory=dict_row)
    try:
        cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{statement_timeout_ms}ms",),
        )
        cursor.execute("SELECT set_config('lock_timeout', '5000ms', true)")
        filtro, params_filtro = weekly._filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT
                u.id_unidade,
                u.nome_unidade,
                MIN(h.received_data_hora) FILTER (
                    WHERE h.quem_enviou = 'cliente'
                      AND h.received_data_hora < %s
                ) AS primeiro_registro
              FROM chatbot.unidade_atendimento u
              LEFT JOIN chatbot.conversa c ON c.id_unidade = u.id_unidade
              LEFT JOIN chatbot.historico_mensagens h
                ON h.id_conversa = c.id_conversa
             WHERE TRUE {filtro}
             GROUP BY u.id_unidade, u.nome_unidade
             ORDER BY u.nome_unidade, u.id_unidade
            """,
            (fim, *params_filtro),
        )
        unidades = [dict(linha) for linha in cursor.fetchall()]
        if ids_unidade and len(unidades) != len(set(ids_unidade)):
            encontrados = {int(linha["id_unidade"]) for linha in unidades}
            ausentes = sorted(set(ids_unidade) - encontrados)
            raise RuntimeError(f"Unidade(s) não encontrada(s): {ausentes}")
        conn.rollback()
        return unidades
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def gerar_totais(
    conn: Any,
    unidades: Sequence[Mapping[str, Any]],
    fim: datetime,
    raiz_saida: Path,
    max_mensagens: int = MAX_MENSAGENS_PADRAO,
    statement_timeout_ms: int = 60_000,
) -> list[dict[str, Path]]:
    """Coleta e publica um snapshot total independente para cada unidade."""
    nomes_pasta = weekly.resolver_pastas_unidades(unidades)
    gerados: list[dict[str, Path]] = []
    for unidade in unidades:
        id_unidade = int(unidade["id_unidade"])
        primeiro_registro = unidade.get("primeiro_registro")
        inicio = primeiro_registro or fim
        if isinstance(inicio, datetime) and inicio.tzinfo is None:
            inicio = inicio.replace(tzinfo=timezone.utc)
        inicio = inicio.astimezone(timezone.utc)

        snapshot = weekly.coletar_snapshot(
            conn=conn,
            inicio=inicio,
            fim=fim,
            ids_unidade=[id_unidade],
            max_mensagens=max_mensagens,
            statement_timeout_ms=statement_timeout_ms,
        )
        snapshot["periodo"]["tipo"] = "total"
        snapshot["periodo"]["sem_registros"] = primeiro_registro is None
        gerados.extend(
            weekly.gerar_artefatos(
                snapshot,
                raiz_saida,
                nomes_pasta=nomes_pasta,
            )
        )
    return gerados


def executar(args: argparse.Namespace) -> list[dict[str, Path]]:
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario(args.env_file)
    from core.database.connection_aws import get_conn

    fim = resolver_fim(args.ate)
    conn = get_conn(application_name="utilitario_monitoramento_total")
    try:
        unidades = coletar_primeiros_registros(
            conn=conn,
            fim=fim,
            ids_unidade=args.ids_unidade,
            statement_timeout_ms=args.statement_timeout_ms,
        )
        return gerar_totais(
            conn=conn,
            unidades=unidades,
            fim=fim,
            raiz_saida=args.saida,
            max_mensagens=args.max_mensagens,
            statement_timeout_ms=args.statement_timeout_ms,
        )
    finally:
        conn.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = criar_parser()
    args = parser.parse_args(argv)
    try:
        gerados = executar(args)
    except Exception as exc:
        parser.exit(1, f"Falha ao gerar monitoramento total: {exc}\n")

    if not gerados:
        print("Nenhuma unidade encontrada; nenhum arquivo foi gerado.")
        return 0
    print(f"Monitoramento total concluído para {len(gerados)} unidade(s):")
    for item in gerados:
        print(f"- HTML: {item['html']}")
        print(f"  PDF:  {item['pdf']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
