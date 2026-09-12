"""Gera dashboards HTML e relatórios PDF semanais por unidade.

O utilitário é deliberadamente import-safe: banco, configuração privada e
ReportLab só são carregados quando ``main`` é executado.  A visão humana
agrupa as conversas técnicas por ``(id_unidade, id_cliente)`` sem alterar a
forma como o chatbot persiste ou processa cada conversa.

Uso padrão (configuração de ``utilitarios/local_settings.py``)::

    python -m utilitarios.reports_functions.weekly

Para consultar uma configuração explícita ou uma unidade específica::

    python -m utilitarios.reports_functions.weekly --env-file .env.prod \
        --id-unidade 1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
SAIDA_PADRAO = RAIZ_PROJETO / "monitoramento"
FUSO_RELATORIO = ZoneInfo("America/Sao_Paulo")
DIAS_PADRAO = 7
MAX_MENSAGENS_PADRAO = 100_000
IDADE_ADULTA_MINIMA = 18
IDADE_IDOSA_MINIMA = 60
IDADE_MINIMA_DEPENDENTE_PADRAO = 5
IDADE_MINIMA_DEPENDENTE_BPA = 4

PERFIS_ATENDIMENTO = (
    "dependente_infantil",
    "dependente_adulto",
    "dependente_idoso",
    "titular_adulto",
    "titular_idoso",
)

ROTULOS_TIPO_MENSAGEM = {
    "audio": "Áudio",
    "button": "Botão",
    "contacts": "Contato compartilhado",
    "document": "Documento",
    "image": "Imagem",
    "interactive": "Interação",
    "location": "Localização",
    "reaction": "Reação",
    "sticker": "Figurinha",
    "text": "Mensagem",
    "unknown": "Conteúdo não textual",
    "video": "Vídeo",
}


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera um dashboard HTML e um relatório PDF dos últimos dias "
            "para cada unidade."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Arquivo .env explícito; sem ele usa utilitarios/local_settings.py.",
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=DIAS_PADRAO,
        help=f"Tamanho da janela móvel (padrão: {DIAS_PADRAO}).",
    )
    parser.add_argument(
        "--ate",
        help=(
            "Fim da janela em ISO-8601. Sem fuso, considera America/Sao_Paulo; "
            "sem o parâmetro, usa o instante atual."
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
        help="Proteção contra um HTML grande demais.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=60_000,
        help="Timeout das consultas do snapshot (padrão: 60000).",
    )
    return parser


def resolver_janela(
    dias: int = DIAS_PADRAO,
    ate: str | datetime | None = None,
) -> tuple[datetime, datetime]:
    """Retorna ``[inicio, fim)`` em UTC para uma janela móvel."""
    if dias <= 0:
        raise ValueError("--dias precisa ser maior que zero")

    if ate is None:
        fim = datetime.now(timezone.utc)
    elif isinstance(ate, datetime):
        fim = ate
    else:
        valor = ate.strip().replace("Z", "+00:00")
        fim = datetime.fromisoformat(valor)

    if fim.tzinfo is None:
        fim = fim.replace(tzinfo=FUSO_RELATORIO)
    fim = fim.astimezone(timezone.utc)
    return fim - timedelta(days=dias), fim


def sanear_nome_unidade(nome: str, id_unidade: int | None = None) -> str:
    """Converte o nome de uma unidade em um componente de caminho seguro."""
    limpo = re.sub(r"^\s*supera(?:\s+|-)+", "", nome or "", flags=re.I)
    limpo = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", limpo)
    limpo = re.sub(r"\s+", " ", limpo).strip(" .")
    chave = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", limpo)
        if not unicodedata.combining(caractere)
    ).casefold()
    if chave in {"saj", "santo antonio de jesus"}:
        limpo = "SAJ"
    if not limpo:
        limpo = f"Unidade {id_unidade}" if id_unidade is not None else "Unidade"
    reservados_windows = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{numero}" for numero in range(1, 10)),
        *(f"LPT{numero}" for numero in range(1, 10)),
    }
    if limpo.upper() in reservados_windows:
        sufixo = f" {id_unidade}" if id_unidade is not None else " unidade"
        limpo += sufixo
    return limpo


def _texto_mensagem(texto: Any, tipo: Any) -> str:
    valor = str(texto).strip() if texto is not None else ""
    if valor:
        return valor
    tipo_normalizado = str(tipo or "unknown").strip().lower()
    return f"[{ROTULOS_TIPO_MENSAGEM.get(tipo_normalizado, tipo_normalizado or 'Conteúdo')}]"


def _iso(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc).isoformat()
    return str(valor)


def _data_local(valor: Any, formato: str = "%d/%m/%Y %H:%M") -> str:
    if valor is None:
        return "—"
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(FUSO_RELATORIO).strftime(formato)


def _profissao_atual(linha: Mapping[str, Any]) -> str | None:
    for chave in ("profissao_cliente", "profissao_conversa_recente"):
        valor = linha.get(chave)
        if valor is not None and str(valor).strip():
            return str(valor).strip()
    return None


def _idade_inteira(valor: Any) -> int | None:
    """Valida 1–99 anos sem converter booleanos ou truncar idades fracionárias."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor if 0 < valor < 100 else None


def _classificar_perfil_atendimento(
    *,
    status_dependente: Any,
    idade_titular: Any,
    idade_dependente: Any,
    idade_minima_dependente: int,
) -> str | None:
    """Classifica a pessoa atendida, mantendo ``NULL`` e legado como desconhecidos."""
    if status_dependente is True:
        idade = _idade_inteira(idade_dependente)
        if idade is None or idade < idade_minima_dependente:
            return None
        if idade < IDADE_ADULTA_MINIMA:
            return "dependente_infantil"
        if idade < IDADE_IDOSA_MINIMA:
            return "dependente_adulto"
        return "dependente_idoso"

    if status_dependente is False:
        idade = _idade_inteira(idade_titular)
        if idade is None or idade < IDADE_ADULTA_MINIMA:
            return None
        if idade < IDADE_IDOSA_MINIMA:
            return "titular_adulto"
        return "titular_idoso"

    return None


def _rotulos_perfis(idade_minima_dependente: int) -> dict[str, str]:
    return {
        "dependente_infantil": (
            f"Dependentes de {idade_minima_dependente} a 17 anos"
        ),
        "dependente_adulto": "Dependentes de 18 a 59 anos",
        "dependente_idoso": "Dependentes com 60 anos ou mais",
        "titular_adulto": "Titulares de 18 a 59 anos",
        "titular_idoso": "Titulares com 60 anos ou mais",
    }


def _montar_segmentacao_perfis(
    perfis_conversa: Sequence[Mapping[str, Any]],
    ids_conversas_funil: set[int],
    *,
    idade_minima_suporte: int | None,
    bpa_ativo: bool,
) -> dict[str, Any]:
    """Agrega perfis por conversa sem confundi-los com o lead consolidado.

    Um cliente conta uma vez em cada segmento no qual apareceu. A quantidade
    de conversas permanece disponível porque um mesmo contato pode iniciar
    atendimentos para pessoas diferentes durante o período.
    """
    validar_idade_minima_suporte(idade_minima_suporte)
    idade_minima_dependente = (
        IDADE_MINIMA_DEPENDENTE_BPA
        if bpa_ativo
        else IDADE_MINIMA_DEPENDENTE_PADRAO
    )
    rotulos = _rotulos_perfis(idade_minima_dependente)
    acumuladores = {
        chave: {
            "ids_clientes": set(),
            "ids_conversas": set(),
            "ids_clientes_funil": set(),
            "ids_conversas_funil": set(),
        }
        for chave in PERFIS_ATENDIMENTO
    }
    todos_clientes: set[int] = set()
    clientes_classificados: set[int] = set()
    clientes_por_perfil: dict[int, set[str]] = defaultdict(set)
    conversas_classificadas: set[int] = set()
    conversas_sem_classificacao: set[int] = set()
    clientes_funil_sem_classificacao: set[int] = set()
    clientes_funil_classificados: set[int] = set()

    for perfil in perfis_conversa:
        id_cliente = int(perfil["id_cliente"])
        id_conversa = int(perfil["id_conversa"])
        todos_clientes.add(id_cliente)
        chave = _classificar_perfil_atendimento(
            status_dependente=perfil.get("status_dependente"),
            idade_titular=perfil.get("idade_titular"),
            idade_dependente=perfil.get("idade_dependente"),
            idade_minima_dependente=idade_minima_dependente,
        )
        if chave is None:
            conversas_sem_classificacao.add(id_conversa)
            if id_conversa in ids_conversas_funil:
                clientes_funil_sem_classificacao.add(id_cliente)
            continue

        acumulador = acumuladores[chave]
        acumulador["ids_clientes"].add(id_cliente)
        acumulador["ids_conversas"].add(id_conversa)
        clientes_classificados.add(id_cliente)
        clientes_por_perfil[id_cliente].add(chave)
        conversas_classificadas.add(id_conversa)
        if id_conversa in ids_conversas_funil:
            acumulador["ids_clientes_funil"].add(id_cliente)
            acumulador["ids_conversas_funil"].add(id_conversa)
            clientes_funil_classificados.add(id_cliente)

    linhas: list[dict[str, Any]] = []
    for chave in PERFIS_ATENDIMENTO:
        acumulador = acumuladores[chave]
        total_leads = len(acumulador["ids_clientes"])
        total_conversas = len(acumulador["ids_conversas"])
        funil_observado = len(acumulador["ids_clientes_funil"])
        total_funil = funil_observado
        linhas.append(
            {
                "chave": chave,
                "rotulo": rotulos[chave],
                "leads": total_leads,
                "conversas": total_conversas,
                "leads_funil": total_funil,
                "leads_funil_observados": funil_observado,
                "conversas_funil": (
                    len(acumulador["ids_conversas_funil"])
                ),
                "conversas_funil_observadas": len(
                    acumulador["ids_conversas_funil"]
                ),
                "taxa_funil": (
                    round(total_funil / total_leads * 100, 1)
                    if total_leads
                    else 0.0
                ),
                "funil_nao_aplicavel": False,
            }
        )

    total_conversas = len(perfis_conversa)
    maior_volume = max(item["leads"] for item in linhas)
    perfis_predominantes = [
        item["rotulo"] for item in linhas
        if maior_volume and item["leads"] == maior_volume
    ]

    return {
        "linhas": linhas,
        "idade_minima_dependente": idade_minima_dependente,
        "leads_classificados": len(clientes_classificados),
        "leads_sem_classificacao": len(todos_clientes - clientes_classificados),
        "leads_multiperfil": sum(
            len(perfis) > 1 for perfis in clientes_por_perfil.values()
        ),
        "conversas_classificadas": len(conversas_classificadas),
        "conversas_sem_classificacao": len(conversas_sem_classificacao),
        "conversas_funil_sem_classificacao": len(
            conversas_sem_classificacao & ids_conversas_funil
        ),
        "leads_funil_apenas_sem_classificacao": len(
            clientes_funil_sem_classificacao - clientes_funil_classificados
        ),
        "conversas_apenas_envio_funil": sum(
            bool(perfil.get("apenas_envio_funil")) for perfil in perfis_conversa
        ),
        "cobertura_conversas": round(
            len(conversas_classificadas) / total_conversas * 100, 1
        )
        if total_conversas
        else 0.0,
        "perfis_predominantes": perfis_predominantes,
        "idade_minima_suporte": idade_minima_suporte,
    }


def _ordenar_data(valor: Any) -> datetime:
    if isinstance(valor, datetime):
        data = valor
    elif valor:
        data = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    else:
        return datetime.min.replace(tzinfo=timezone.utc)
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(timezone.utc)


def montar_snapshot(
    unidades: Sequence[Mapping[str, Any]],
    mensagens: Sequence[Mapping[str, Any]],
    funil: Sequence[Mapping[str, Any]],
    pesquisas: Sequence[Mapping[str, Any]],
    inicio: datetime,
    fim: datetime,
) -> dict[str, Any]:
    """Materializa a visão de relatório a partir de linhas do banco.

    A chave visual é sempre ``(id_unidade, id_cliente)``. Os IDs das
    conversas técnicas permanecem no resultado para auditoria.
    """
    unidades_por_id: dict[int, dict[str, Any]] = {}
    for linha in unidades:
        id_unidade = int(linha["id_unidade"])
        unidades_por_id[id_unidade] = {
            "id_unidade": id_unidade,
            "nome_unidade": str(linha["nome_unidade"]),
            "nome_agente": str(linha.get("nome_agente") or "Assistente"),
            "idade_minima_suporte": validar_idade_minima_suporte(linha["idade_minima_suporte"]),
            "bpa_ativo": bool(linha.get("bpa_ativo", False)),
            "conversas": [],
            "pesquisas": [],
        }

    funil_por_unidade: dict[int, set[int]] = defaultdict(set)
    conversas_funil_por_unidade: dict[int, set[int]] = defaultdict(set)
    for linha in funil:
        id_unidade = int(linha["id_unidade"])
        funil_por_unidade[id_unidade].add(int(linha["id_cliente"]))
        if linha.get("id_conversa") is not None:
            conversas_funil_por_unidade[id_unidade].add(
                int(linha["id_conversa"])
            )

    grupos: dict[tuple[int, int], dict[str, Any]] = {}
    perfis_conversa: dict[tuple[int, int, int], dict[str, Any]] = {}
    for linha in mensagens:
        id_unidade = int(linha["id_unidade"])
        id_cliente = int(linha["id_cliente"])
        if id_unidade not in unidades_por_id:
            continue
        chave = (id_unidade, id_cliente)
        grupo = grupos.get(chave)
        if grupo is None:
            grupo = {
                "id_cliente": id_cliente,
                "nome": str(linha.get("nome_cliente") or "Cliente sem nome"),
                "waid_telefone": str(linha.get("waid_telefone") or ""),
                "email": str(linha.get("email") or ""),
                "profissao": _profissao_atual(linha),
                "ids_conversa": [],
                "mensagens": [],
                "primeira_atividade": None,
                "ultima_atividade": None,
                "status_ativa": False,
                "etapa_atual": None,
                "foi_funil": False,
            }
            grupos[chave] = grupo

        id_conversa = int(linha["id_conversa"])
        if id_conversa not in grupo["ids_conversa"]:
            grupo["ids_conversa"].append(id_conversa)
        perfis_conversa.setdefault(
            (id_unidade, id_cliente, id_conversa),
            {
                "id_unidade": id_unidade,
                "id_cliente": id_cliente,
                "id_conversa": id_conversa,
                "status_dependente": linha.get("status_dependente"),
                "idade_titular": linha.get("idade_titular"),
                "idade_dependente": linha.get("idade_dependente"),
                "nome_dependente": linha.get("nome_dependente"),
                "apenas_envio_funil": False,
            },
        )

        data_mensagem = linha.get("received_data_hora")
        data_ordenacao = _ordenar_data(data_mensagem)
        if (
            grupo["primeira_atividade"] is None
            or data_ordenacao < _ordenar_data(grupo["primeira_atividade"])
        ):
            grupo["primeira_atividade"] = _iso(data_mensagem)
        if (
            grupo["ultima_atividade"] is None
            or data_ordenacao >= _ordenar_data(grupo["ultima_atividade"])
        ):
            grupo["ultima_atividade"] = _iso(data_mensagem)
            grupo["status_ativa"] = bool(linha.get("status_ativa"))
            grupo["etapa_atual"] = linha.get("id_etapa_atual")

        grupo["mensagens"].append(
            {
                "id_mensagem": int(linha["id_mensagem"]),
                "id_conversa": id_conversa,
                "data": _iso(data_mensagem),
                "quem_enviou": str(linha["quem_enviou"]),
                "tipo": str(linha.get("tipo_mensagem") or "unknown"),
                "texto": _texto_mensagem(
                    linha.get("conteudo_texto"), linha.get("tipo_mensagem")
                ),
                "id_etapa": linha.get("id_etapa"),
            }
        )

    for (id_unidade, id_cliente), grupo in grupos.items():
        grupo["mensagens"].sort(
            key=lambda item: (_ordenar_data(item["data"]), item["id_mensagem"])
        )
        grupo["foi_funil"] = id_cliente in funil_por_unidade[id_unidade]
        unidades_por_id[id_unidade]["conversas"].append(grupo)

    for unidade in unidades_por_id.values():
        unidade["conversas"].sort(
            key=lambda grupo: _ordenar_data(grupo["ultima_atividade"]), reverse=True
        )

    # Um retry pode confirmar o envio de uma conversa antiga enquanto o mesmo
    # contato interage em outra. Preservamos o perfil do envio, sem acrescentar
    # suas mensagens fora da janela ao dashboard de conversas.
    for linha in funil:
        id_unidade = int(linha["id_unidade"])
        id_cliente = int(linha["id_cliente"])
        if (id_unidade, id_cliente) not in grupos or linha.get("id_conversa") is None:
            continue
        id_conversa = int(linha["id_conversa"])
        perfis_conversa.setdefault(
            (id_unidade, id_cliente, id_conversa),
            {
                "id_unidade": id_unidade,
                "id_cliente": id_cliente,
                "id_conversa": id_conversa,
                "status_dependente": linha.get("status_dependente"),
                "idade_titular": linha.get("idade_titular"),
                "idade_dependente": linha.get("idade_dependente"),
                "nome_dependente": linha.get("nome_dependente"),
                "apenas_envio_funil": True,
            },
        )

    perfis_por_unidade: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for perfil in perfis_conversa.values():
        perfis_por_unidade[int(perfil["id_unidade"])].append(perfil)
    for id_unidade, unidade in unidades_por_id.items():
        unidade["perfis_atendimento"] = perfis_por_unidade[id_unidade]

    for linha in pesquisas:
        id_unidade = int(linha["id_unidade"])
        if id_unidade not in unidades_por_id:
            continue
        unidades_por_id[id_unidade]["pesquisas"].append(
            {
                "id_cliente": int(linha["id_cliente"]),
                "id_conversa": int(linha["id_conversa"]),
                "nome": str(linha.get("nome_cliente") or "Cliente sem nome"),
                "waid_telefone": str(linha.get("waid_telefone") or ""),
                "profissao": _profissao_atual(linha),
                "nota": linha.get("nota"),
                "comentario": (
                    str(linha["comentario"]).strip()
                    if linha.get("comentario") is not None
                    else ""
                ),
                "criado_em": _iso(linha.get("criado_em")),
            }
        )

    for id_unidade, unidade in unidades_por_id.items():
        ids_leads_periodo = {
            int(conversa["id_cliente"]) for conversa in unidade["conversas"]
        }
        # O relatório de satisfação responde à pergunta "quantos desses leads".
        # Portanto, notas e comentários só entram quando o cliente também faz
        # parte da coorte que enviou mensagem à unidade dentro da janela.
        unidade["pesquisas"] = [
            item
            for item in unidade["pesquisas"]
            if int(item["id_cliente"]) in ids_leads_periodo
        ]
        pesquisas_unidade = unidade["pesquisas"]
        notas = [int(item["nota"]) for item in pesquisas_unidade if item["nota"] is not None]
        distribuicao = {str(nota): notas.count(nota) for nota in range(1, 6)}
        leads_com_nota = {
            item["id_cliente"] for item in pesquisas_unidade if item["nota"] is not None
        }
        ids_funil_periodo = funil_por_unidade[id_unidade] & ids_leads_periodo
        total_leads = len(ids_leads_periodo)
        total_funil = len(ids_funil_periodo)
        unidade["metricas"] = {
            "leads_contato": total_leads,
            "leads_funil": total_funil,
            "taxa_funil": round((total_funil / total_leads * 100), 1)
            if total_leads
            else 0.0,
            "leads_com_nota": len(leads_com_nota),
            "respostas_satisfacao": len(notas),
            "media_satisfacao": round(sum(notas) / len(notas), 2) if notas else None,
            "distribuicao_notas": distribuicao,
            "comentarios": sum(bool(item["comentario"]) for item in pesquisas_unidade),
            "taxa_participacao_satisfacao": round(
                len(leads_com_nota) / total_leads * 100, 1
            ) if total_leads else 0.0,
            "segmentacao_perfis": _montar_segmentacao_perfis(
                perfis_por_unidade[id_unidade],
                conversas_funil_por_unidade[id_unidade],
                idade_minima_suporte=unidade["idade_minima_suporte"],
                bpa_ativo=bool(unidade["bpa_ativo"]),
            ),
        }
        pesquisas_unidade.sort(
            key=lambda item: _ordenar_data(item["criado_em"]), reverse=True
        )

    return {
        "periodo": {
            "tipo": "semanal",
            "inicio": inicio.astimezone(timezone.utc).isoformat(),
            "fim": fim.astimezone(timezone.utc).isoformat(),
            "dias": (fim - inicio).total_seconds() / 86_400,
            "rotulo": (
                f"{_data_local(inicio, '%d/%m/%Y %H:%M')} até "
                f"{_data_local(fim, '%d/%m/%Y %H:%M')}"
            ),
        },
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "unidades": sorted(
            unidades_por_id.values(), key=lambda item: item["nome_unidade"].casefold()
        ),
    }


def _filtro_unidades(ids_unidade: Sequence[int] | None, alias: str = "u") -> tuple[str, tuple[Any, ...]]:
    if not ids_unidade:
        return "", ()
    ids = sorted(set(int(valor) for valor in ids_unidade))
    return f" AND {alias}.id_unidade = ANY(%s)", (ids,)


def _coluna_existe(cursor: Any, tabela: str, coluna: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'chatbot'
               AND table_name = %s
               AND column_name = %s
        ) AS existe
        """,
        (tabela, coluna),
    )
    return bool(cursor.fetchone()["existe"])


def coletar_snapshot(
    conn: Any,
    inicio: datetime,
    fim: datetime,
    ids_unidade: Sequence[int] | None = None,
    max_mensagens: int = MAX_MENSAGENS_PADRAO,
    statement_timeout_ms: int = 60_000,
) -> dict[str, Any]:
    """Consulta um snapshot consistente sem realizar nenhuma mutação."""
    if max_mensagens <= 0:
        raise ValueError("--max-mensagens precisa ser maior que zero")
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

        filtro, params_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT
                u.id_unidade,
                u.nome_unidade,
                u.nome_agente,
                u.idade_minima_suporte,
                u.bpa_ativo
              FROM chatbot.unidade u
             WHERE TRUE {filtro}
             ORDER BY u.nome_unidade, u.id_unidade
            """,
            params_filtro,
        )
        unidades = cursor.fetchall()
        if ids_unidade and len(unidades) != len(set(ids_unidade)):
            encontrados = {int(linha["id_unidade"]) for linha in unidades}
            ausentes = sorted(set(ids_unidade) - encontrados)
            raise RuntimeError(f"Unidade(s) não encontrada(s): {ausentes}")

        tem_profissao_cliente = _coluna_existe(cursor, "cliente", "profissao")
        tem_profissao_conversa = _coluna_existe(cursor, "conversa", "profissao")
        expr_profissao_cliente = (
            "cl.profissao" if tem_profissao_cliente else "NULL::text"
        )
        if tem_profissao_conversa:
            expr_profissao_conversa = "cx_prof.profissao"
            lateral_profissao = """
               LEFT JOIN LATERAL (
                    SELECT cx_prof.profissao
                      FROM chatbot.conversa cx_prof
                     WHERE cx_prof.id_cliente = c.id_cliente
                       AND NULLIF(BTRIM(cx_prof.profissao), '') IS NOT NULL
                     ORDER BY cx_prof.iniciou_em DESC, cx_prof.id_conversa DESC
                     LIMIT 1
               ) cx_prof ON TRUE
            """
        else:
            expr_profissao_conversa = "NULL::text"
            lateral_profissao = ""

        filtro_mensagens, params_mensagens_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            WITH clientes_janela AS (
                SELECT DISTINCT c.id_unidade, c.id_cliente
                  FROM chatbot.historico_mensagens h0
                  JOIN chatbot.conversa c ON c.id_conversa = h0.id_conversa
                  JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
                 WHERE h0.quem_enviou = 'cliente'
                   AND h0.received_data_hora >= %s
                   AND h0.received_data_hora < %s
                   {filtro_mensagens}
            )
            SELECT
                u.id_unidade,
                u.nome_unidade,
                c.id_cliente,
                cl.nome AS nome_cliente,
                cl.waid_telefone,
                cl.email,
                {expr_profissao_cliente} AS profissao_cliente,
                {expr_profissao_conversa} AS profissao_conversa_recente,
                c.id_conversa,
                c.status_ativa,
                c.status_dependente,
                c.id_etapa_atual,
                cl.idade AS idade_titular,
                d.idade AS idade_dependente,
                d.nome_dependente,
                h.id_mensagem,
                h.id_etapa,
                h.received_data_hora,
                h.quem_enviou,
                h.tipo_mensagem,
                h.conteudo_texto
              FROM clientes_janela cj
              JOIN chatbot.conversa c
                ON c.id_unidade = cj.id_unidade
               AND c.id_cliente = cj.id_cliente
              JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
              LEFT JOIN chatbot.dependente d
                ON d.id_conversa = c.id_conversa AND d.id_cliente = c.id_cliente
              JOIN chatbot.historico_mensagens h ON h.id_conversa = c.id_conversa
              {lateral_profissao}
             WHERE h.received_data_hora >= %s
               AND h.received_data_hora < %s
               AND (
                    h.quem_enviou = 'cliente'
                    OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent')
               )
             ORDER BY u.id_unidade, c.id_cliente,
                      h.received_data_hora, h.id_mensagem
             LIMIT %s
            """,
            (
                inicio,
                fim,
                *params_mensagens_filtro,
                inicio,
                fim,
                max_mensagens + 1,
            ),
        )
        mensagens = cursor.fetchall()
        if len(mensagens) > max_mensagens:
            raise RuntimeError(
                "O intervalo excedeu o limite de mensagens; reduza a janela ou "
                "aumente --max-mensagens conscientemente."
            )

        filtro_funil, params_funil_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT DISTINCT
                u.id_unidade,
                c.id_cliente,
                c.id_conversa,
                c.status_dependente,
                cl.idade AS idade_titular,
                d.idade AS idade_dependente,
                d.nome_dependente
              FROM chatbot.funil_envios f
              JOIN chatbot.conversa c ON c.id_conversa = f.id_conversa
              JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
              LEFT JOIN chatbot.dependente d
                ON d.id_conversa = c.id_conversa AND d.id_cliente = c.id_cliente
             WHERE f.status = 'sent'
               AND f.enviado_em >= %s
               AND f.enviado_em < %s
               {filtro_funil}
            """,
            (inicio, fim, *params_funil_filtro),
        )
        funil = cursor.fetchall()

        filtro_pesquisa, params_pesquisa_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT
                u.id_unidade,
                c.id_cliente,
                c.id_conversa,
                cl.nome AS nome_cliente,
                cl.waid_telefone,
                {expr_profissao_cliente} AS profissao_cliente,
                {expr_profissao_conversa} AS profissao_conversa_recente,
                p.nota,
                p.comentario,
                p.criado_em
              FROM chatbot.pesquisa_satisfacao p
              JOIN chatbot.conversa c ON c.id_conversa = p.id_conversa
              JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
               {lateral_profissao}
             WHERE p.criado_em >= %s
               AND p.criado_em < %s
               {filtro_pesquisa}
             ORDER BY p.criado_em DESC, p.id_pesquisa_satisfacao DESC
            """,
            (inicio, fim, *params_pesquisa_filtro),
        )
        pesquisas = cursor.fetchall()

        snapshot = montar_snapshot(
            unidades=unidades,
            mensagens=mensagens,
            funil=funil,
            pesquisas=pesquisas,
            inicio=inicio,
            fim=fim,
        )
        conn.rollback()
        return snapshot
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def _json_seguro(valor: Any) -> str:
    return (
        json.dumps(valor, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def renderizar_html(unidade: Mapping[str, Any], periodo: Mapping[str, Any]) -> str:
    """Cria um dashboard offline; dados do banco entram apenas como JSON seguro."""
    payload = {
        "unidade": {
            "id_unidade": unidade["id_unidade"],
            "nome_unidade": unidade["nome_unidade"],
            "nome_agente": unidade["nome_agente"],
            "conversas": unidade["conversas"],
            "pesquisas": unidade["pesquisas"],
            "metricas": unidade["metricas"],
        },
        "periodo": periodo,
    }
    nome_titulo = html_escape(str(unidade["nome_unidade"]), quote=True)
    dados_json = _json_seguro(payload)
    return f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>Conversas — {nome_titulo}</title>
  <style>
    :root{{--verde:#00a884;--verde2:#008069;--fundo:#efeae2;--painel:#f7f9fa;
      --linha:#e5e7eb;--texto:#182229;--muted:#667781;--bot:#d9fdd3;--cliente:#fff;
      --sombra:0 18px 60px rgba(24,34,41,.16)}}
    *{{box-sizing:border-box}} html,body{{height:100%;margin:0}}
    body{{font:14px/1.45 "Segoe UI",Arial,sans-serif;color:var(--texto);
      background:linear-gradient(180deg,var(--verde2) 0 126px,#e9edef 126px)}}
    button,input{{font:inherit}} .app{{height:calc(100vh - 34px);min-height:620px;max-width:1500px;
      margin:17px auto;background:#fff;display:grid;grid-template-columns:390px 1fr;grid-template-rows:minmax(0,1fr);
      overflow:hidden;box-shadow:var(--sombra);border-radius:5px}}
    .sidebar{{display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden;border-right:1px solid var(--linha);background:#fff}}
    .brand{{padding:18px 20px;background:#f0f2f5;border-bottom:1px solid var(--linha)}}
    .brand h1{{font-size:17px;margin:0 0 3px}} .brand p{{margin:0;color:var(--muted);font-size:12px}}
    .stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px;border-bottom:1px solid var(--linha)}}
    .stat{{padding:10px 8px;border:1px solid #e6ecea;border-radius:10px;background:#fbfdfc;text-align:center}}
    .stat b{{display:block;font-size:18px;color:var(--verde2)}} .stat span{{font-size:10px;color:var(--muted)}}
    .search{{padding:9px 12px;background:var(--painel)}}
    .search input{{width:100%;border:0;border-radius:8px;background:#fff;padding:10px 13px;outline:none}}
    .list{{min-height:0;overflow-y:auto;overscroll-behavior:contain;flex:1}} .empty{{padding:32px;color:var(--muted);text-align:center}}
    .chat-item{{width:100%;display:grid;grid-template-columns:46px 1fr;gap:11px;text-align:left;
      padding:12px 14px;border:0;border-bottom:1px solid #edf0f2;background:#fff;cursor:pointer}}
    .chat-item:hover,.chat-item.active{{background:#f0f2f5}}
    .avatar{{width:46px;height:46px;border-radius:50%;background:linear-gradient(145deg,#cfd8dc,#90a4ae);
      color:#fff;display:grid;place-items:center;font-weight:700;font-size:17px}}
    .item-top{{display:flex;justify-content:space-between;gap:8px}} .item-top strong{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .item-top time{{font-size:11px;color:var(--muted);white-space:nowrap}}
    .preview{{color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px;margin-top:4px}}
    .main{{min-width:0;min-height:0;overflow:hidden;display:flex;flex-direction:column;background:var(--fundo)}}
    .topbar{{min-height:74px;padding:11px 18px;background:#f0f2f5;border-bottom:1px solid var(--linha);display:flex;align-items:center;gap:13px}}
    .identity{{min-width:0;flex:1}} .identity h2{{font-size:16px;margin:0 0 2px}} .identity p{{margin:0;color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .tag{{border:1px solid #badfd7;background:#e8f7f3;color:#087966;border-radius:999px;padding:4px 9px;font-size:11px}}
    .messages{{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:28px clamp(18px,6vw,84px);background-color:var(--fundo);
      background-image:radial-gradient(rgba(98,114,124,.09) .7px,transparent .7px);background-size:14px 14px}}
    .intro{{max-width:720px;margin:20vh auto 0;padding:26px;text-align:center;background:rgba(255,255,255,.82);border-radius:14px;color:var(--muted)}}
    .day,.conversation-cut{{width:max-content;max-width:95%;margin:14px auto;padding:5px 10px;border-radius:7px;background:#fff;color:var(--muted);font-size:11px;box-shadow:0 1px 2px rgba(0,0,0,.08)}}
    .conversation-cut{{background:#fff6cf;color:#665c25}}
    .row{{display:flex;margin:3px 0}} .row.bot{{justify-content:flex-end}}
    .bubble{{position:relative;max-width:min(72%,720px);padding:7px 9px 5px;border-radius:8px;background:var(--cliente);box-shadow:0 1px 1px rgba(0,0,0,.08);white-space:pre-wrap;overflow-wrap:anywhere}}
    .row.bot .bubble{{background:var(--bot)}} .meta{{display:flex;justify-content:flex-end;gap:7px;margin:4px 0 0 16px;color:var(--muted);font-size:10px}}
    .details{{padding:9px 18px;background:#f0f2f5;color:var(--muted);font-size:11px;border-top:1px solid var(--linha)}}
    @media(max-width:820px){{.app{{margin:0;height:100vh;min-height:0;border-radius:0;grid-template-columns:132px 1fr}}.brand p,.stats,.preview,.chat-item .item-top time{{display:none}}.chat-item{{grid-template-columns:40px 1fr;padding:10px 8px}}.avatar{{width:40px;height:40px}}.bubble{{max-width:90%}}}}
    @media print{{body{{background:#fff}}.app{{height:auto;margin:0;box-shadow:none}}}}
  </style>
  <style>
    :root{{--wa-bg:#0b141a;--wa-panel:#111b21;--wa-panel-2:#202c33;--wa-border:#2a3942;
      --wa-text:#e9edef;--wa-muted:#8696a0;--wa-green:#00a884;--wa-green-dark:#005c4b;
      --wa-client:#202c33;--wa-bot:#005c4b;--wa-blue:#53bdeb}}
    body{{color:var(--wa-text);background:var(--wa-bg)}}
    .app{{height:100vh;min-height:560px;max-width:none;margin:0;border-radius:0;
      grid-template-columns:390px minmax(0,1fr);background:var(--wa-bg);box-shadow:none}}
    .sidebar{{background:var(--wa-panel);border-color:var(--wa-border)}}
    .brand{{padding:17px 18px;background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .brand h1{{font-size:18px;color:var(--wa-text)}} .brand p{{color:var(--wa-muted)}}
    .stats{{grid-template-columns:repeat(4,1fr);gap:6px;padding:10px;background:var(--wa-panel);border-color:var(--wa-border)}}
    .stat{{padding:9px 4px;border-color:var(--wa-border);border-radius:8px;background:#18252d}}
    .stat b{{font-size:17px;color:#66d6bc}} .stat span{{font-size:9px;color:var(--wa-muted)}}
    .search{{padding:8px 12px;background:var(--wa-panel)}}
    .search input{{color:var(--wa-text);background:var(--wa-panel-2);padding:10px 14px}}
    .search input::placeholder{{color:var(--wa-muted)}}
    .filters{{display:flex;gap:6px;padding:0 12px 10px;overflow-x:auto;border-bottom:1px solid var(--wa-border)}}
    .filter{{border:1px solid var(--wa-border);border-radius:999px;padding:6px 10px;color:var(--wa-muted);
      background:transparent;cursor:pointer;white-space:nowrap;font-size:11px}}
    .filter:hover,.filter.active{{color:#d8fff5;background:#123c35;border-color:#1f6c5d}}
    .list{{background:var(--wa-panel)}} .empty{{color:var(--wa-muted)}}
    .chat-item{{grid-template-columns:49px 1fr;gap:12px;padding:12px 14px;color:var(--wa-text);
      border-color:var(--wa-border);background:var(--wa-panel)}}
    .chat-item:hover,.chat-item.active{{background:var(--wa-panel-2)}}
    .avatar{{width:49px;height:49px;background:#667781;color:#fff}}
    .item-top time,.preview{{color:var(--wa-muted)}}
    .item-bottom{{display:flex;align-items:center;gap:7px;margin-top:4px;min-width:0}}
    .item-bottom .preview{{flex:1;margin:0}} .count{{min-width:20px;padding:2px 6px;border-radius:999px;
      background:var(--wa-green);color:#061b16;text-align:center;font-size:10px;font-weight:700}}
    .flags{{display:flex;gap:4px;margin-top:5px;min-height:17px}}
    .flag{{padding:2px 6px;border-radius:4px;background:#23343e;color:#aebac1;font-size:9px}}
    .flag.green{{background:#12493f;color:#8de7d1}} .flag.gold{{background:#4a3e1f;color:#f2d57a}}
    .main{{position:relative;background-color:var(--wa-bg);
      background-image:radial-gradient(rgba(255,255,255,.035) .75px,transparent .75px);background-size:13px 13px}}
    .topbar{{min-height:66px;padding:8px 15px;background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .identity h2{{color:var(--wa-text)}} .identity p{{color:var(--wa-muted)}}
    .tag{{border-color:#1e6e5d;background:#123c35;color:#8de7d1}}
    .icon-button{{border:1px solid var(--wa-border);border-radius:8px;padding:7px 10px;color:var(--wa-muted);
      background:#18252d;cursor:pointer}} .icon-button:hover,.icon-button[aria-pressed="true"]{{color:#d8fff5;border-color:#1f6c5d}}
    .back{{display:none;font-size:25px;line-height:1;padding:3px 10px}}
    .messages{{padding:24px clamp(18px,6vw,82px);background:transparent}}
    .intro{{margin-top:18vh;background:rgba(32,44,51,.94);color:var(--wa-muted);border:1px solid var(--wa-border)}}
    .intro h2{{color:var(--wa-text)}}
    .day,.conversation-cut{{background:#18252d;color:#aebac1;box-shadow:0 1px 1px rgba(0,0,0,.35)}}
    .conversation-cut{{background:#23343e;color:#aebac1;border:1px solid #304652}}
    .conversation-cut.continuation{{background:#123c35;color:#8de7d1;border-color:#1f6c5d}}
    .bubble{{max-width:min(76%,760px);padding:7px 9px 6px;color:var(--wa-text);background:var(--wa-client);
      box-shadow:0 1px 1px rgba(0,0,0,.28)}} .row.bot .bubble{{background:var(--wa-bot)}}
    .message-kind{{display:inline-block;margin-bottom:4px;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,.09);
      color:#b7c7cf;font-size:9px;text-transform:uppercase;letter-spacing:.04em}}
    .meta{{color:#aebac1}} .ticks{{color:var(--wa-blue);font-weight:700}}
    .technical{{display:none;padding-top:4px;color:#8fa2ac;font-size:9px}} body.show-metadata .technical{{display:block}}
    .details{{padding:8px 18px;color:var(--wa-muted);background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .scroll-bottom{{position:absolute;right:24px;bottom:50px;width:42px;height:42px;border:1px solid var(--wa-border);
      border-radius:50%;color:var(--wa-text);background:var(--wa-panel-2);box-shadow:0 4px 16px rgba(0,0,0,.35);
      cursor:pointer;font-size:22px}}
    @media(max-width:820px){{
      .app{{display:block;height:100vh}} .sidebar{{height:100vh}} .main{{display:none;height:100vh}}
      body.chat-open .sidebar{{display:none}} body.chat-open .main{{display:flex}} .back{{display:inline-block}}
      .brand p,.preview,.item-top time{{display:block}} .stats{{display:grid}}
      .chat-item{{grid-template-columns:46px 1fr;padding:11px 13px}} .avatar{{width:46px;height:46px}}
      .bubble{{max-width:90%}} .messages{{padding:18px 12px}} .tag{{display:none}}
    }}
    @media print{{body{{background:#fff;color:#111}}.app{{height:auto}}}}
  </style>
</head>
<body>
  <main class="app">
    <aside class="sidebar">
      <header class="brand"><h1 id="unitName"></h1><p id="period"></p></header>
      <section class="stats" aria-label="Resumo do período">
        <div class="stat"><b id="leadCount">0</b><span>LEADS</span></div>
        <div class="stat"><b id="messageCount">0</b><span>MENSAGENS</span></div>
        <div class="stat"><b id="funnelCount">0</b><span>FUNIL</span></div>
        <div class="stat"><b id="ratingAverage">—</b><span>NOTA MÉDIA</span></div>
      </section>
      <div class="search"><input id="search" type="search" placeholder="Pesquisar lead ou mensagem" aria-label="Pesquisar conversas"></div>
      <nav class="filters" aria-label="Filtrar conversas">
        <button type="button" class="filter active" data-filter="all">Todas</button>
        <button type="button" class="filter" data-filter="continued">Continuações</button>
        <button type="button" class="filter" data-filter="funnel">Funil</button>
        <button type="button" class="filter" data-filter="rated">Avaliadas</button>
      </nav>
      <div id="chatList" class="list"></div>
    </aside>
    <section class="main">
      <header id="topbar" class="topbar" hidden>
        <button id="backButton" class="icon-button back" type="button" aria-label="Voltar para conversas">‹</button>
        <div id="avatarMain" class="avatar"></div>
        <div class="identity"><h2 id="clientName"></h2><p id="clientDetails"></p></div>
        <span id="funnelTag" class="tag" hidden>Enviado ao funil</span>
        <button id="metadataButton" class="icon-button" type="button" aria-pressed="false">Detalhes</button>
      </header>
      <div id="messages" class="messages"><div class="intro"><h2>Conversas do período</h2><p>Selecione um lead para visualizar a sequência completa das conversas técnicas no período.</p></div></div>
      <button id="scrollBottom" class="scroll-bottom" type="button" aria-label="Ir para a mensagem mais recente" hidden>↓</button>
      <footer id="details" class="details">Relatório privado: contém dados pessoais e deve ser compartilhado somente com a unidade responsável.</footer>
    </section>
  </main>
  <script id="report-data" type="application/json">{dados_json}</script>
  <script>
  (() => {{
    'use strict';
    const data = JSON.parse(document.getElementById('report-data').textContent);
    const unit = data.unidade, conversations = unit.conversas || [];
    const $ = id => document.getElementById(id);
    const fmt = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{dateStyle:'short',timeStyle:'short',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const fmtDate = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{dateStyle:'short',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const fmtTime = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const initials = name => (name || '?').split(/\\s+/).slice(0,2).map(x => x[0] || '').join('').toUpperCase();
    $('unitName').textContent = unit.nome_unidade;
    $('period').textContent = data.periodo.rotulo;
    $('leadCount').textContent = unit.metricas.leads_contato;
    $('funnelCount').textContent = unit.metricas.leads_funil;
    $('ratingAverage').textContent = unit.metricas.media_satisfacao ?? '—';

    function addText(parent, tag, className, text) {{
      const node = document.createElement(tag); node.className = className || ''; node.textContent = text; parent.appendChild(node); return node;
    }}
    function showConversation(item) {{
      document.querySelectorAll('.chat-item').forEach(x => x.classList.toggle('active', x.dataset.client === String(item.id_cliente)));
      $('topbar').hidden = false; $('clientName').textContent = item.nome; $('avatarMain').textContent = initials(item.nome);
      const parts = [item.waid_telefone && `WA ID: ${{item.waid_telefone}}`, item.email, item.profissao && `Profissão: ${{item.profissao}}`].filter(Boolean);
      $('clientDetails').textContent = parts.join(' • ') || `Cliente #${{item.id_cliente}}`;
      $('funnelTag').hidden = !item.foi_funil;
      const box = $('messages'); box.replaceChildren(); let lastDay = '', lastConversation = null;
      item.mensagens.forEach(msg => {{
        const d = new Date(msg.data); const day = new Intl.DateTimeFormat('pt-BR', {{dateStyle:'long',timeZone:'America/Sao_Paulo'}}).format(d);
        if (day !== lastDay) {{ addText(box,'div','day',day); lastDay = day; }}
        if (lastConversation !== null && lastConversation !== msg.id_conversa) addText(box,'div','conversation-cut',`Continuação técnica • conversa #${{msg.id_conversa}}`);
        lastConversation = msg.id_conversa;
        const row = document.createElement('div'); row.className = `row ${{msg.quem_enviou === 'bot' ? 'bot' : 'client'}}`;
        const bubble = document.createElement('div'); bubble.className = 'bubble'; addText(bubble,'div','',msg.texto);
        const meta = addText(bubble,'div','meta',''); addText(meta,'span','',`etapa ${{msg.id_etapa ?? '—'}}`); addText(meta,'time','',fmtTime(msg.data));
        row.appendChild(bubble); box.appendChild(row);
      }});
      $('details').textContent = `Cliente #${{item.id_cliente}} • conversas técnicas: ${{item.ids_conversa.join(', ')}} • ${{item.mensagens.length}} mensagens visíveis no período`;
      box.scrollTop = box.scrollHeight;
    }}
    function renderList(filter='') {{
      const needle = filter.trim().toLocaleLowerCase('pt-BR'); const list = $('chatList'); list.replaceChildren();
      const visible = conversations.filter(item => [item.nome,item.waid_telefone,item.email,item.profissao].filter(Boolean).join(' ').toLocaleLowerCase('pt-BR').includes(needle));
      if (!visible.length) {{ addText(list,'div','empty',conversations.length ? 'Nenhum lead encontrado.' : 'Nenhuma mensagem de cliente no período.'); return; }}
      visible.forEach(item => {{
        const button = document.createElement('button'); button.type='button'; button.className='chat-item'; button.dataset.client=String(item.id_cliente);
        addText(button,'div','avatar',initials(item.nome)); const body=document.createElement('div'); const top=document.createElement('div'); top.className='item-top';
        addText(top,'strong','',item.nome); addText(top,'time','',fmtDate(item.ultima_atividade)); body.appendChild(top);
        const last=item.mensagens[item.mensagens.length-1]; addText(body,'div','preview',last ? `${{last.quem_enviou==='bot'?'✓ ':''}}${{last.texto}}` : 'Sem mensagens'); button.appendChild(body);
        button.addEventListener('click',()=>showConversation(item)); list.appendChild(button);
      }});
    }}
    $('search').addEventListener('input',event=>renderList(event.target.value)); renderList(); if (conversations[0]) showConversation(conversations[0]);
  }})();
  </script>
  <script>
  (() => {{
    'use strict';
    const data = JSON.parse(document.getElementById('report-data').textContent);
    const unit = data.unidade;
    const conversations = unit.conversas || [];
    const surveys = unit.pesquisas || [];
    const $ = id => document.getElementById(id);
    const colors = ['#7e57c2','#00897b','#5c6bc0','#d97706','#0288d1','#c44569','#5f7c3a','#8d6e63'];
    const ratingsByClient = new Map();
    let activeFilter = 'all';
    let selectedClient = null;

    surveys.forEach(survey => {{
      if (survey.nota !== null && survey.nota !== undefined) {{
        ratingsByClient.set(String(survey.id_cliente), survey.nota);
      }}
    }});

    const fmtDate = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      dateStyle:'short', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const fmtTime = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      hour:'2-digit', minute:'2-digit', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const fmtDay = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      dateStyle:'long', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const initials = name => (name || '?').split(/\\s+/).slice(0,2)
      .map(part => part[0] || '').join('').toUpperCase();
    const avatarColor = id => colors[Math.abs(Number(id) || 0) % colors.length];

    function addText(parent, tag, className, value) {{
      const node = document.createElement(tag);
      node.className = className || '';
      node.textContent = value;
      parent.appendChild(node);
      return node;
    }}

    function preview(message) {{
      if (!message) return 'Sem mensagens';
      const content = message.texto || '[' + (message.tipo || 'mensagem') + ']';
      return (message.quem_enviou === 'bot' ? '✓✓ ' : '') + content;
    }}

    function matchesFilter(item) {{
      if (activeFilter === 'continued') return item.ids_conversa.length > 1;
      if (activeFilter === 'funnel') return Boolean(item.foi_funil);
      if (activeFilter === 'rated') return ratingsByClient.has(String(item.id_cliente));
      return true;
    }}

    function showConversation(item) {{
      selectedClient = String(item.id_cliente);
      document.body.classList.add('chat-open');
      document.querySelectorAll('.chat-item').forEach(button => {{
        button.classList.toggle('active', button.dataset.client === selectedClient);
      }});
      $('topbar').hidden = false;
      $('clientName').textContent = item.nome;
      $('avatarMain').textContent = initials(item.nome);
      $('avatarMain').style.backgroundColor = avatarColor(item.id_cliente);
      const parts = [
        item.waid_telefone ? 'WA ID: ' + item.waid_telefone : '',
        item.email || '',
        item.profissao ? 'Profissão: ' + item.profissao : ''
      ].filter(Boolean);
      $('clientDetails').textContent = parts.join(' • ') || 'Cliente #' + item.id_cliente;
      $('funnelTag').hidden = !item.foi_funil;

      const box = $('messages');
      box.replaceChildren();
      let lastDay = '';
      let lastConversation = null;
      item.mensagens.forEach(message => {{
        const day = fmtDay(message.data);
        if (day !== lastDay) {{
          addText(box,'div','day',day);
          lastDay = day;
        }}
        if (lastConversation !== message.id_conversa) {{
          const first = lastConversation === null;
          const label = (first ? 'Início técnico' : 'Continuação técnica') +
            ' • conversa #' + message.id_conversa;
          const separator = addText(
            box,'div','conversation-cut' + (first ? '' : ' continuation'),label
          );
          separator.title = 'As conversas foram unidas porque pertencem ao mesmo cliente e à mesma unidade.';
        }}
        lastConversation = message.id_conversa;
        const isBot = message.quem_enviou === 'bot';
        const row = document.createElement('div');
        row.className = 'row ' + (isBot ? 'bot' : 'client');
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        if (message.tipo && message.tipo !== 'text') {{
          addText(bubble,'span','message-kind',message.tipo);
        }}
        addText(
          bubble,'div','',
          message.texto || '[' + (message.tipo || 'mensagem sem texto') + ']'
        );
        const technical = addText(
          bubble,'div','technical',
          'mensagem #' + message.id_mensagem +
          ' • conversa #' + message.id_conversa +
          ' • etapa ' + (message.id_etapa ?? '—') +
          ' • tipo ' + (message.tipo || '—')
        );
        technical.setAttribute('aria-hidden','true');
        const meta = addText(bubble,'div','meta','');
        addText(meta,'time','',fmtTime(message.data));
        if (isBot) addText(meta,'span','ticks','✓✓');
        row.appendChild(bubble);
        box.appendChild(row);
      }});

      const rating = ratingsByClient.get(String(item.id_cliente));
      $('details').textContent =
        'Cliente #' + item.id_cliente +
        ' • conversas técnicas: ' + item.ids_conversa.join(', ') +
        ' • ' + item.mensagens.length + ' mensagens no período' +
        (rating === undefined ? '' : ' • satisfação: ' + rating);
      box.scrollTop = box.scrollHeight;
      $('scrollBottom').hidden = true;
    }}

    const oldSearch = $('search');
    const search = oldSearch.cloneNode(true);
    oldSearch.replaceWith(search);

    function renderList() {{
      const needle = search.value.trim().toLocaleLowerCase('pt-BR');
      const list = $('chatList');
      list.replaceChildren();
      const visible = conversations.filter(item => {{
        const searchable = [item.nome,item.waid_telefone,item.email,item.profissao]
          .concat(item.mensagens.map(message => message.texto))
          .filter(Boolean).join(' ').toLocaleLowerCase('pt-BR');
        return matchesFilter(item) && searchable.includes(needle);
      }});
      if (!visible.length) {{
        addText(
          list,'div','empty',
          conversations.length ? 'Nenhum lead encontrado.' : 'Nenhuma mensagem de cliente no período.'
        );
        return;
      }}
      visible.forEach(item => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'chat-item';
        button.dataset.client = String(item.id_cliente);
        if (selectedClient === button.dataset.client) button.classList.add('active');
        const avatar = addText(button,'div','avatar',initials(item.nome));
        avatar.style.backgroundColor = avatarColor(item.id_cliente);
        const body = document.createElement('div');
        const top = document.createElement('div');
        top.className = 'item-top';
        addText(top,'strong','',item.nome);
        addText(top,'time','',fmtDate(item.ultima_atividade));
        body.appendChild(top);
        const bottom = document.createElement('div');
        bottom.className = 'item-bottom';
        addText(bottom,'div','preview',preview(item.mensagens[item.mensagens.length - 1]));
        addText(bottom,'span','count',String(item.mensagens.length));
        body.appendChild(bottom);
        const flags = document.createElement('div');
        flags.className = 'flags';
        if (item.ids_conversa.length > 1) {{
          addText(flags,'span','flag',item.ids_conversa.length + ' conversas unidas');
        }}
        if (item.foi_funil) addText(flags,'span','flag green','funil');
        const rating = ratingsByClient.get(String(item.id_cliente));
        if (rating !== undefined) addText(flags,'span','flag gold','nota ' + rating);
        body.appendChild(flags);
        button.appendChild(body);
        button.addEventListener('click',() => showConversation(item));
        list.appendChild(button);
      }});
    }}

    $('period').textContent =
      (unit.nome_agente ? 'Agente ' + unit.nome_agente + ' • ' : '') + data.periodo.rotulo;
    $('messageCount').textContent = conversations.reduce(
      (total,item) => total + item.mensagens.length, 0
    );
    search.addEventListener('input',renderList);
    document.querySelectorAll('.filter').forEach(button => {{
      button.addEventListener('click',() => {{
        activeFilter = button.dataset.filter;
        document.querySelectorAll('.filter').forEach(candidate => {{
          candidate.classList.toggle('active',candidate === button);
        }});
        renderList();
      }});
    }});
    $('metadataButton').addEventListener('click',() => {{
      const enabled = document.body.classList.toggle('show-metadata');
      $('metadataButton').setAttribute('aria-pressed',String(enabled));
      document.querySelectorAll('.technical').forEach(node => {{
        node.setAttribute('aria-hidden',String(!enabled));
      }});
    }});
    $('backButton').addEventListener('click',() => {{
      document.body.classList.remove('chat-open');
    }});
    $('messages').addEventListener('scroll',() => {{
      const box = $('messages');
      $('scrollBottom').hidden = box.scrollHeight - box.scrollTop - box.clientHeight < 140;
    }});
    $('scrollBottom').addEventListener('click',() => {{
      $('messages').scrollTo({{top:$('messages').scrollHeight,behavior:'smooth'}});
    }});
    renderList();
    if (conversations[0] && window.matchMedia('(min-width:821px)').matches) {{
      showConversation(conversations[0]);
    }}
  }})();
  </script>
</body>
</html>'''


def _registrar_fontes_pdf() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidatos = [
        (
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf",
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arialbd.ttf",
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]
    for regular, bold in candidatos:
        if regular.is_file() and bold.is_file():
            try:
                pdfmetrics.registerFont(TTFont("Monitoramento", str(regular)))
                pdfmetrics.registerFont(TTFont("Monitoramento-Bold", str(bold)))
                pdfmetrics.registerFontFamily(
                    "Monitoramento",
                    normal="Monitoramento",
                    bold="Monitoramento-Bold",
                )
                return "Monitoramento", "Monitoramento-Bold"
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"


def renderizar_pdf(
    unidade: Mapping[str, Any],
    periodo: Mapping[str, Any],
    destino: Path,
) -> None:
    """Renderiza um PDF vetorial, paginado e adequado para impressão."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            CondPageBreak,
            HRFlowable,
            KeepTogether,
            LongTable,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "ReportLab não está instalado. Execute: "
            "pip install -r utilitarios/requirements-monitoramento.txt"
        ) from exc

    fonte, fonte_bold = _registrar_fontes_pdf()
    verde = colors.HexColor("#008069")
    cinza = colors.HexColor("#667781")
    cinza_claro = colors.HexColor("#F4F6F7")
    amarelo = colors.HexColor("#F4B400")
    texto = colors.HexColor("#182229")

    estilos_base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle(
            "Titulo",
            parent=estilos_base["Title"],
            fontName=fonte_bold,
            fontSize=20,
            leading=24,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        ),
        "subtitulo_capa": ParagraphStyle(
            "SubtituloCapa",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#D6F3EC"),
        ),
        "secao": ParagraphStyle(
            "Secao",
            parent=estilos_base["Heading2"],
            fontName=fonte_bold,
            fontSize=15,
            leading=19,
            textColor=verde,
            spaceBefore=4 * mm,
            spaceAfter=2.5 * mm,
        ),
        "corpo": ParagraphStyle(
            "Corpo",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=13,
            textColor=texto,
        ),
        "pequeno": ParagraphStyle(
            "Pequeno",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=7.5,
            leading=10,
            textColor=cinza,
        ),
        "centro": ParagraphStyle(
            "Centro",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=texto,
        ),
        "cabecalho_tabela": ParagraphStyle(
            "CabecalhoTabela",
            fontName=fonte_bold,
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "indicador": ParagraphStyle(
            "Indicador",
            fontName=fonte_bold,
            fontSize=23,
            leading=28,
            alignment=TA_CENTER,
            textColor=verde,
        ),
        "rotulo_indicador": ParagraphStyle(
            "RotuloIndicador",
            fontName=fonte,
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=texto,
        ),
        "comentario": ParagraphStyle(
            "Comentario",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=14,
            leftIndent=4 * mm,
            rightIndent=3 * mm,
            borderColor=colors.HexColor("#B9E4D9"),
            borderWidth=0,
            borderPadding=(2 * mm, 3 * mm, 2 * mm, 3 * mm),
            backColor=colors.HexColor("#F5FBF9"),
            textColor=texto,
            spaceAfter=2 * mm,
        ),
    }

    def p(valor: Any, estilo: str = "corpo") -> Any:
        texto_seguro = html_escape(str(valor if valor not in (None, "") else "—"))
        return Paragraph(texto_seguro.replace("\n", "<br/>"), estilos[estilo])

    def percentual(valor: float) -> str:
        return f"{valor:.1f}%".replace(".", ",")

    nome_unidade = str(unidade["nome_unidade"])
    metricas = unidade["metricas"]
    gerado_em = datetime.now(timezone.utc)
    dias_periodo = float(periodo.get("dias") or 0)
    if periodo.get("tipo") == "total":
        selo_periodo = "HISTÓRICO TOTAL"
    elif dias_periodo.is_integer():
        selo_periodo = f"ÚLTIMOS {int(dias_periodo)} DIAS"
    else:
        selo_periodo = "JANELA DO RELATÓRIO"
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Desempenho — {nome_unidade}",
        author="Monitoramento do chatbot",
        subject=f"Indicadores de {periodo['rotulo']}",
    )

    def cabecalho_rodape(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        largura, altura = A4
        canvas.setStrokeColor(colors.HexColor("#DDE4E7"))
        canvas.line(16 * mm, 13 * mm, largura - 16 * mm, 13 * mm)
        canvas.setFont(fonte, 7.5)
        canvas.setFillColor(cinza)
        canvas.drawString(16 * mm, 8.5 * mm, nome_unidade)
        canvas.drawRightString(
            largura - 16 * mm,
            8.5 * mm,
            f"Página {doc.page} • gerado {_data_local(gerado_em)}",
        )
        canvas.setFont(fonte, 6.5)
        canvas.drawString(
            16 * mm, 4.5 * mm,
            "Documento privado • dados pessoais • uso exclusivo de pessoas autorizadas da unidade.",
        )
        canvas.restoreState()

    historia: list[Any] = []
    capa = Table(
        [
            [
                Paragraph("Relatório de desempenho", estilos["titulo"]),
                p(selo_periodo, "centro"),
            ],
            [
                Paragraph(
                    f"<b>{html_escape(nome_unidade)}</b><br/>{html_escape(str(periodo['rotulo']))}",
                    estilos["subtitulo_capa"],
                ),
                "",
            ],
        ],
        colWidths=[135 * mm, 32 * mm],
    )
    capa.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), verde),
                ("SPAN", (0, 1), (1, 1)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TEXTCOLOR", (1, 0), (1, 0), verde),
                ("BACKGROUND", (1, 0), (1, 0), colors.white),
                ("BOX", (1, 0), (1, 0), 0.5, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                ("ROUNDEDCORNERS", [5]),
            ]
        )
    )
    historia.extend([capa, Spacer(1, 3 * mm)])

    valores_cards = [
        (metricas["leads_contato"], "Leads em contato"),
        (metricas["leads_funil"], "Enviados ao funil"),
        (metricas["leads_com_nota"], "Leads que avaliaram"),
        (
            f"{metricas['media_satisfacao']:.2f}".replace(".", ",")
            if metricas["media_satisfacao"] is not None
            else "—",
            "Nota média / 5",
        ),
    ]
    cards = []
    for valor, rotulo in valores_cards:
        cards.append(
            Table(
                [
                    [p(valor, "indicador")],
                    [p(rotulo, "rotulo_indicador")],
                ],
                colWidths=[38.75 * mm],
                style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
                       ("RIGHTPADDING", (0, 0), (-1, -1), 0)],
            )
        )
    tabela_cards = Table(
        [cards],
        colWidths=[41.75 * mm] * 4,
        rowHeights=[26 * mm],
    )
    tabela_cards.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), cinza_claro),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE4E7")),
                ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ]
        )
    )
    descricao_intervalo = (
        "todo o histórico disponível até o instante final do relatório"
        if periodo.get("tipo") == "total"
        else "eventos ocorridos dentro da janela móvel"
    )
    historia.extend(
        [
            Paragraph("Visão geral", estilos["secao"]),
            p(
                f"Os indicadores abaixo usam {descricao_intervalo}. "
                "Conversas técnicas do mesmo cliente foram consolidadas apenas quando "
                "pertencem à mesma unidade. "
                f"A taxa geral de envio ao funil foi de {percentual(metricas['taxa_funil'])}."
            ),
            Spacer(1, 3 * mm),
            tabela_cards,
            Spacer(1, 5 * mm),
        ]
    )

    segmentacao = metricas["segmentacao_perfis"]
    linhas_perfis: list[list[Any]] = [
        [
            p("Perfil atendido", "cabecalho_tabela"),
            p("Leads", "cabecalho_tabela"),
            p("Conversas", "cabecalho_tabela"),
            p("No funil", "cabecalho_tabela"),
            p("Taxa de envio", "cabecalho_tabela"),
        ]
    ]
    linhas_politica: list[int] = []
    for perfil in segmentacao["linhas"]:
        if perfil["funil_nao_aplicavel"]:
            valor_funil = "Não se aplica*"
            valor_taxa = "—"
            linhas_politica.append(len(linhas_perfis))
        else:
            valor_funil = perfil["leads_funil"]
            valor_taxa = percentual(perfil["taxa_funil"])
        linhas_perfis.append(
            [
                p(perfil["rotulo"], "pequeno"),
                p(perfil["leads"], "centro"),
                p(perfil["conversas"], "centro"),
                p(valor_funil, "centro"),
                p(valor_taxa, "centro"),
            ]
        )

    tabela_perfis = Table(
        linhas_perfis,
        colWidths=[67 * mm, 20 * mm, 24 * mm, 31 * mm, 25 * mm],
        repeatRows=1,
    )
    estilo_perfis = [
        ("BACKGROUND", (0, 0), (-1, 0), verde),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
    ]
    for indice_linha in linhas_politica:
        estilo_perfis.append(
            (
                "BACKGROUND",
                (0, indice_linha),
                (-1, indice_linha),
                colors.HexColor("#FFF4D6"),
            )
        )
    tabela_perfis.setStyle(TableStyle(estilo_perfis))

    total_conversas_perfil = (
        segmentacao["conversas_classificadas"]
        + segmentacao["conversas_sem_classificacao"]
    )
    leituras_rapidas: list[str] = []
    predominantes = segmentacao["perfis_predominantes"]
    if len(predominantes) == 1:
        leituras_rapidas.append(f"Maior volume: {predominantes[0]}.")
    elif predominantes:
        leituras_rapidas.append("Maior volume, em empate: " + "; ".join(predominantes) + ".")
    if segmentacao["leads_multiperfil"]:
        leituras_rapidas.append(
            f"{segmentacao['leads_multiperfil']} lead(s) apareceram em mais de um "
            "perfil de atendimento."
        )
    if segmentacao["conversas_sem_classificacao"]:
        leituras_rapidas.append(
            f"{segmentacao['conversas_sem_classificacao']} conversa(s) tinham "
            "tipo/idade ausente ou inválido, ou idade fora das faixas atuais."
        )
    if not leituras_rapidas:
        leituras_rapidas.append("Nenhum atendimento para classificar neste período.")

    bloco_perfis = [
        Paragraph("Perfil dos atendimentos", estilos["secao"]),
        p(
            "Leads representa clientes únicos dentro de cada perfil; Conversas "
            "mostra a demanda técnica. Um cliente pode aparecer em mais de um "
            "perfil quando iniciou atendimentos para pessoas diferentes, portanto "
            "as linhas não devem ser somadas para obter o total geral."
        ),
        Spacer(1, 2 * mm),
        tabela_perfis,
        Spacer(1, 2.5 * mm),
        p(
            f"Cobertura etária: {segmentacao['conversas_classificadas']} de "
            f"{total_conversas_perfil} conversa(s) ({percentual(segmentacao['cobertura_conversas'])}). "
            f"A faixa infantil começa aos {segmentacao['idade_minima_dependente']} "
            "anos conforme a configuração de BPA da unidade."
        ),
        p("Leitura rápida: " + " ".join(leituras_rapidas), "pequeno"),
    ]
    limite = segmentacao["idade_minima_suporte"]
    politica_suporte = (
        "Encaminhamento por idade: desativado."
        if limite is None
        else f"Encaminhamento ao comercial: titulares a partir de {limite} anos, na etapa de idade."
    )
    bloco_perfis.append(p(
        politica_suporte + " As faixas etárias permanecem fixas. Os números e taxas "
        "incluem os envios confirmados; a configuração atual não apaga o histórico "
        "nem comprova qual regra vigorava na época.",
        "pequeno",
    ))
    if segmentacao["conversas_funil_sem_classificacao"]:
        bloco_perfis.append(p(
            f"Envios fora das cinco faixas: {segmentacao['conversas_funil_sem_classificacao']} "
            "conversa(s) sem classificação, cujos leads continuam considerados "
            "no total geral de enviados.",
            "pequeno",
        ))
    historia.append(KeepTogether(bloco_perfis))
    if not metricas["leads_contato"]:
        historia.extend([
            Spacer(1, 4 * mm),
            p("Nenhum lead entrou em contato neste período. Não há notas, "
              "comentários ou relação de leads a apresentar."),
        ])
        documento.build(
            historia, onFirstPage=cabecalho_rodape, onLaterPages=cabecalho_rodape,
        )
        return
    historia.append(PageBreak())

    distribuicao = metricas["distribuicao_notas"]
    maximo = max([int(valor) for valor in distribuicao.values()] + [1])
    linhas_notas: list[list[Any]] = [[p("Nota", "cabecalho_tabela"), p("Distribuição", "cabecalho_tabela"), p("Respostas", "cabecalho_tabela")]]
    for nota in range(5, 0, -1):
        quantidade = int(distribuicao[str(nota)])
        barra: Any = ""
        if quantidade:
            barra = Table([[""]], colWidths=[90 * quantidade / maximo * mm], rowHeights=[4 * mm], hAlign="LEFT")
            barra.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), amarelo)]))
        linhas_notas.append([p(f"{nota} / 5"), barra, p(quantidade, "centro")])
    tabela_notas = Table(linhas_notas, colWidths=[23 * mm, 120 * mm, 24 * mm], repeatRows=1)
    tabela_notas.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), verde),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.3 * mm),
            ]
        )
    )
    historia.extend(
        [
            Paragraph("Satisfação", estilos["secao"]),
            p(
                f"Foram registradas {metricas['respostas_satisfacao']} nota(s) e "
                f"{metricas['comentarios']} comentário(s) no período. "
                f"Participação: {percentual(metricas['taxa_participacao_satisfacao'])} "
                "dos leads em contato deram pelo menos uma nota."
            ),
            Spacer(1, 2 * mm),
            tabela_notas,
            Spacer(1, 4 * mm),
            Paragraph("Como interpretar os números", estilos["secao"]),
            p(
                "No funil significa envio confirmado no registro local de integração, "
                "dentro do período; não significa agendamento ou venda. Cada faixa "
                "considera o envio da própria conversa, nunca de outro atendimento "
                "do mesmo contato.", "pequeno",
            ),
            p(
                "A idade do titular usa o cadastro atual; a do dependente usa o "
                "registro ligado à conversa. Idades e configurações de BPA/suporte "
                "ao idoso refletem o banco na extração, não um retrato histórico "
                "da época de cada atendimento. Idades fora de 1–99, ausentes e "
                "fora das faixas exibidas ficam sem classificação.", "pequeno",
            ),
            p(
                f"{segmentacao['leads_sem_classificacao']} lead(s) apenas sem "
                f"classificação; {segmentacao['leads_funil_apenas_sem_classificacao']} "
                "lead(s) enviados somente por conversas sem classificação. "
                f"{segmentacao['conversas_apenas_envio_funil']} conversa(s) foram "
                "incluídas nos perfis pelo envio confirmado, mesmo sem mensagem "
                "na janela, sempre de clientes que entraram em contato no período.",
                "pequeno",
            ),
        ]
    )

    cabecalho_leads = [
        p("Lead", "cabecalho_tabela"),
        p("Profissão atual", "cabecalho_tabela"),
        p("Conversa(s)", "cabecalho_tabela"),
        p("Última atividade", "cabecalho_tabela"),
        p("Funil", "cabecalho_tabela"),
    ]
    linhas_leads: list[list[Any]] = [cabecalho_leads]
    for lead in unidade["conversas"]:
        identificacao = lead["nome"]
        if lead.get("waid_telefone"):
            identificacao += f"\nWA ID: {lead['waid_telefone']}"
        linhas_leads.append(
            [
                p(identificacao, "pequeno"),
                p(lead.get("profissao"), "pequeno"),
                p(", ".join(map(str, lead["ids_conversa"])), "pequeno"),
                p(_data_local(lead["ultima_atividade"]), "pequeno"),
                p("Sim" if lead["foi_funil"] else "Não", "centro"),
            ]
        )
    if len(linhas_leads) == 1:
        linhas_leads.append([p("Nenhum lead no período"), "", "", "", ""])
    tabela_leads = LongTable(
        linhas_leads,
        colWidths=[52 * mm, 35 * mm, 26 * mm, 37 * mm, 17 * mm],
        repeatRows=1,
    )
    tabela_leads.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), verde),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
                ("SPAN", (0, 1), (-1, 1)) if len(unidade["conversas"]) == 0 else ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.white),
            ]
        )
    )
    historia.extend([Spacer(1, 4 * mm), Paragraph("Comentários recebidos", estilos["secao"])])

    comentarios = [item for item in unidade["pesquisas"] if item["comentario"]]
    if not comentarios:
        historia.append(p("Nenhum comentário foi registrado no período."))
    else:
        for indice, item in enumerate(comentarios, 1):
            historia.append(CondPageBreak(28 * mm))
            cabecalho = (
                f"<b>{html_escape(item['nome'])}</b> • nota "
                f"{html_escape(str(item['nota'] if item['nota'] is not None else 'não informada'))}"
                f"<br/><font color='#667781'>Profissão: "
                f"{html_escape(item['profissao'] or 'não informada')} • "
                f"{html_escape(_data_local(item['criado_em']))} • "
                f"conversa #{item['id_conversa']}</font>"
            )
            historia.append(Paragraph(cabecalho, estilos["corpo"]))
            historia.append(
                Paragraph(
                    "“" + html_escape(item["comentario"]).replace("\n", "<br/>") + "”",
                    estilos["comentario"],
                )
            )
            if indice != len(comentarios):
                historia.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#DCE4E7"), spaceBefore=1 * mm, spaceAfter=2 * mm))

    historia.extend(
        [
            PageBreak(),
            Paragraph("Leads identificados no período", estilos["secao"]),
            p(
                "Relação consolidada por cliente da unidade. Os IDs abaixo remetem "
                "às conversas do dashboard de histórico, que permanece separado "
                "deste relatório de indicadores.",
                "pequeno",
            ),
            Spacer(1, 3 * mm),
            tabela_leads,
        ]
    )
    documento.build(
        historia,
        onFirstPage=cabecalho_rodape,
        onLaterPages=cabecalho_rodape,
    )


def _datas_nome_arquivo(periodo: Mapping[str, Any]) -> str:
    inicio = _ordenar_data(periodo["inicio"]).astimezone(FUSO_RELATORIO).date()
    fim = _ordenar_data(periodo["fim"]).astimezone(FUSO_RELATORIO).date()
    return f"{inicio.isoformat()}_a_{fim.isoformat()}"


def _arquivo_temporario(diretorio: Path, sufixo: str) -> Path:
    diretorio.mkdir(parents=True, exist_ok=True)
    descritor, caminho = tempfile.mkstemp(prefix=".gerando-", suffix=sufixo, dir=diretorio)
    os.close(descritor)
    return Path(caminho)


def _publicar_lote_recuperavel(pares: Sequence[tuple[Path, Path]]) -> None:
    """Publica um lote completo, restaurando os arquivos anteriores em erro.

    Uma troca verdadeiramente atômica de vários arquivos não existe no sistema
    de arquivos. O protocolo guarda todos os destinos antigos antes de publicar
    qualquer arquivo. Se uma troca falhar, restaura o lote anterior. Backups que
    não puderem ser restaurados são preservados para recuperação manual.
    """
    backups: dict[Path, Path] = {}
    publicados: list[Path] = []
    try:
        for _, destino in pares:
            if destino.exists():
                backup = _arquivo_temporario(
                    destino.parent, f"{destino.suffix}.backup"
                )
                backup.unlink()
                destino.replace(backup)
                backups[destino] = backup

        for temporario, destino in pares:
            temporario.replace(destino)
            publicados.append(destino)
    except Exception as erro_publicacao:
        erros_recuperacao: list[str] = []
        for destino in reversed(publicados):
            try:
                destino.unlink(missing_ok=True)
            except OSError as exc:
                erros_recuperacao.append(f"remover {destino}: {exc}")
        for destino, backup in backups.items():
            if backup.exists():
                try:
                    backup.replace(destino)
                except OSError as exc:
                    erros_recuperacao.append(
                        f"restaurar {destino} a partir de {backup}: {exc}"
                    )
        if erros_recuperacao:
            detalhes = "; ".join(erros_recuperacao)
            preservados = ", ".join(
                str(backup) for backup in backups.values() if backup.exists()
            )
            raise RuntimeError(
                "Falha ao publicar e ao restaurar o lote. "
                f"Backups preservados: {preservados or 'nenhum'}. {detalhes}"
            ) from erro_publicacao
        raise
    else:
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    finally:
        for temporario, _ in pares:
            temporario.unlink(missing_ok=True)


def resolver_pastas_unidades(
    unidades: Sequence[Mapping[str, Any]],
) -> dict[int, str]:
    """Resolve nomes de pasta estáveis, inclusive quando nomes comerciais colidem."""
    pastas_usadas: set[str] = set()
    resultado: dict[int, str] = {}
    for unidade in unidades:
        id_unidade = int(unidade["id_unidade"])
        pasta_base = sanear_nome_unidade(unidade["nome_unidade"], id_unidade)
        pasta = pasta_base
        tentativa = 0
        while pasta.casefold() in pastas_usadas:
            tentativa += 1
            sufixo = str(id_unidade) if tentativa == 1 else f"{id_unidade}-{tentativa}"
            pasta = f"{pasta_base} ({sufixo})"
        pastas_usadas.add(pasta.casefold())
        resultado[id_unidade] = pasta
    return resultado


def gerar_artefatos(
    snapshot: Mapping[str, Any],
    raiz_saida: Path,
    nomes_pasta: Mapping[int, str] | None = None,
) -> list[dict[str, Path]]:
    """Gera os pares HTML/PDF e restaura o par anterior se a publicação falhar."""
    raiz_saida = raiz_saida.expanduser().resolve()
    periodo = snapshot["periodo"]
    tipo_periodo = str(periodo.get("tipo") or "semanal")
    if tipo_periodo not in {"semanal", "total"}:
        raise ValueError(f"Tipo de período inválido: {tipo_periodo!r}")
    intervalo = _datas_nome_arquivo(periodo)
    pastas = dict(nomes_pasta or resolver_pastas_unidades(snapshot["unidades"]))
    gerados: list[dict[str, Path]] = []
    publicacao: list[tuple[Path, Path]] = []

    try:
        for unidade in snapshot["unidades"]:
            id_unidade = int(unidade["id_unidade"])
            pasta = pastas.get(id_unidade)
            if not pasta:
                raise RuntimeError(f"Pasta não resolvida para a unidade {id_unidade}")
            raiz_unidade = raiz_saida / pasta / tipo_periodo
            diretorio_html = raiz_unidade / "dashbord"
            diretorio_pdf = raiz_unidade / "relatorios"
            destino_html = diretorio_html / f"conversas_{intervalo}.html"
            destino_pdf = diretorio_pdf / f"desempenho_{intervalo}.pdf"
            temporario_html = _arquivo_temporario(diretorio_html, ".html")
            temporario_pdf = _arquivo_temporario(diretorio_pdf, ".pdf")
            publicacao.extend(
                ((temporario_html, destino_html), (temporario_pdf, destino_pdf))
            )

            temporario_html.write_text(
                renderizar_html(unidade, periodo), encoding="utf-8", newline="\n"
            )
            renderizar_pdf(unidade, periodo, temporario_pdf)
            gerados.append({"html": destino_html, "pdf": destino_pdf})

        _publicar_lote_recuperavel(publicacao)
    except Exception:
        for temporario, _ in publicacao:
            temporario.unlink(missing_ok=True)
        raise
    return gerados


def executar(args: argparse.Namespace) -> list[dict[str, Path]]:
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario(args.env_file)
    # Import tardio: connection_aws lê o ambiente no momento do import.
    from core.database.connection_aws import get_conn

    inicio, fim = resolver_janela(args.dias, args.ate)
    conn = get_conn(application_name="utilitario_monitoramento_semanal")
    try:
        snapshot = coletar_snapshot(
            conn=conn,
            inicio=inicio,
            fim=fim,
            ids_unidade=args.ids_unidade,
            max_mensagens=args.max_mensagens,
            statement_timeout_ms=args.statement_timeout_ms,
        )
    finally:
        conn.close()
    return gerar_artefatos(snapshot, args.saida)


def main(argv: Sequence[str] | None = None) -> int:
    parser = criar_parser()
    args = parser.parse_args(argv)
    try:
        gerados = executar(args)
    except Exception as exc:
        parser.exit(1, f"Falha ao gerar monitoramento: {exc}\n")

    if not gerados:
        print("Nenhuma unidade encontrada; nenhum arquivo foi gerado.")
        return 0
    print(f"Monitoramento concluído para {len(gerados)} unidade(s):")
    for item in gerados:
        print(f"- HTML: {item['html']}")
        print(f"  PDF:  {item['pdf']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
