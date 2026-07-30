"""Relatório operacional e somente leitura de conversas suspeitas de automação."""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from operations.bootstrap import configure_local_operations

MAX_CONVERSAS = 2000
MAX_MENSAGENS_POR_CONVERSA = 1000
MAX_MENSAGENS_TOTAL = 50000
DEFAULT_LIMITE_CONVERSAS = 200
DEFAULT_LIMITE_MENSAGENS = 250
DEFAULT_LIMIAR = 45
DEFAULT_STATEMENT_TIMEOUT_MS = 15000
DEFAULT_LOCK_TIMEOUT_MS = 1000
DEFAULT_IDLE_TIMEOUT_MS = 20000

_EMAIL = re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_CPF_CNPJ = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_TELEFONE = re.compile(r"(?<!\d)(?:\+?55\s*)?(?:\(?\d{2}\)?[\s.-]*)?\d{4,5}[\s.-]?\d{4}(?!\d)")
_NUMERO_LONGO = re.compile(r"\b\d{7,}\b")
_SEGREDO = re.compile(r"\b[A-Za-z0-9_-]{24,}\b")


def parse_instante(valor):
    texto = str(valor).strip()
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    instante = datetime.fromisoformat(texto)
    if instante.tzinfo is None:
        instante = instante.replace(tzinfo=timezone.utc)
    return instante.astimezone(timezone.utc)


def mascarar_pii(texto):
    if texto is None:
        return None
    valor = str(texto)
    valor = _EMAIL.sub("[EMAIL]", valor)
    valor = _URL.sub("[URL]", valor)
    valor = _CPF_CNPJ.sub("[DOCUMENTO]", valor)
    valor = _TELEFONE.sub("[TELEFONE]", valor)
    valor = _NUMERO_LONGO.sub("[NUMERO]", valor)
    return _SEGREDO.sub("[CHAVE]", valor)


def _iso(valor):
    if valor is None:
        return None
    if isinstance(valor, datetime):
        return valor.isoformat()
    return str(valor)


def _clamp(valor, minimo, maximo):
    return max(minimo, min(maximo, valor))


def _razao(parte, total):
    return parte / total if total else 0.0


def mascarar_wa_id(valor, *, mostrar=False):
    if valor is None:
        return None
    texto = str(valor).strip()
    if mostrar:
        return texto
    if len(texto) <= 4:
        return "*" * len(texto)
    return "*" * (len(texto) - 4) + texto[-4:]


def mascarar_nome(valor):
    if not valor:
        return None
    partes = str(valor).strip().split()
    return " ".join(
        parte[0] + "***" if parte else ""
        for parte in partes[:3]
    )


def reconstruir_movimentos(mensagens):
    """Pareia cliente/bot pela fila e classifica a evolução observada."""
    por_fila = defaultdict(list)
    for item in mensagens:
        if item.get("id_mensagem_fila") is not None:
            por_fila[item["id_mensagem_fila"]].append(item)
    movimentos = []
    for cliente in (
        item for item in mensagens if item["quem_enviou"] == "cliente"
    ):
        candidatos = [
            item
            for item in por_fila.get(cliente.get("id_mensagem_fila"), [])
            if item["quem_enviou"] == "bot"
            and item["instante"] >= cliente["instante"]
        ]
        bot = min(
            candidatos,
            key=lambda item: (item["instante"], item["id_mensagem"]),
            default=None,
        )
        if bot is None:
            tipo = "indeterminado"
        elif cliente["id_etapa"] is None and bot["id_etapa"] is not None:
            tipo = "inicializacao"
        elif cliente["id_etapa"] is None or bot["id_etapa"] is None:
            tipo = "indeterminado"
        elif cliente["id_etapa"] != bot["id_etapa"]:
            tipo = "avanco"
        else:
            tipo = "sem_avanco"
        movimentos.append(
            {
                "id_mensagem_cliente": cliente["id_mensagem"],
                "id_mensagem_bot": bot["id_mensagem"] if bot else None,
                "tipo": tipo,
                "etapa_cliente": cliente["id_etapa"],
                "etapa_bot": bot["id_etapa"] if bot else None,
            }
        )
    return movimentos


def _maior_sequencia_sem_avanco(movimentos):
    maior = atual = 0
    for movimento in movimentos:
        if movimento["tipo"] == "sem_avanco":
            atual += 1
            maior = max(maior, atual)
        else:
            atual = 0
    return maior


def _latencias_bot_cliente(mensagens):
    """Mede somente a resposta externa após a última mensagem do nosso bot."""
    ultima_bot = None
    latencias = []
    for item in mensagens:
        if item["quem_enviou"] == "bot":
            ultima_bot = item
        elif ultima_bot is not None:
            segundos = (item["instante"] - ultima_bot["instante"]).total_seconds()
            if segundos >= 0:
                latencias.append(
                    {
                        "segundos": segundos,
                        "estruturada_curta": (
                            item["tipo_mensagem"]
                            in {
                                "button",
                                "interactive",
                                "list",
                                "quick_reply",
                            }
                            and (item.get("tamanho_texto") or 0) <= 40
                        ),
                    }
                )
            ultima_bot = None
    return latencias


def _contar_ciclos(estados):
    ciclos = 0
    for tamanho in (2, 3):
        for indice in range(tamanho * 2, len(estados) + 1):
            if estados[indice - tamanho:indice] == estados[indice - tamanho * 2:indice - tamanho]:
                ciclos += 1
    return ciclos


def pontuar_conversa(conversa, mensagens):
    mensagens = sorted(
        mensagens,
        key=lambda item: (item["instante"], item["id_mensagem"]),
    )
    total = len(mensagens)
    clientes = [item for item in mensagens if item["quem_enviou"] == "cliente"]
    bots_contexto = [
        item for item in mensagens if item["quem_enviou"] == "bot"
    ]
    movimentos = reconstruir_movimentos(mensagens)
    chaves_cliente = [
        (item["id_etapa"], item["fingerprint"])
        for item in clientes
        if item.get("fingerprint")
    ]
    contagens_cliente = Counter(chaves_cliente)
    repeticoes_cliente = sum(
        max(0, quantidade - 1)
        for quantidade in contagens_cliente.values()
    )
    razao_repeticao = _razao(
        repeticoes_cliente,
        len(chaves_cliente),
    )
    estados = [
        (item["id_etapa"], item.get("fingerprint"))
        for item in clientes
        if item.get("fingerprint")
    ]
    ciclos = _contar_ciclos(estados)
    sequencia_sem_avanco = _maior_sequencia_sem_avanco(movimentos)
    contagem_movimentos = Counter(
        movimento["tipo"] for movimento in movimentos
    )

    razoes_fluxo = []
    turnos = conversa.get("turnos_sem_avanco")
    sinal_fluxo = max(turnos or 0, sequencia_sem_avanco)
    if sinal_fluxo >= 12:
        pontos_fluxo = 70
    elif sinal_fluxo >= 9:
        pontos_fluxo = 50
    elif sinal_fluxo >= 6:
        pontos_fluxo = 30
    elif sinal_fluxo >= 4:
        pontos_fluxo = 15
    else:
        pontos_fluxo = 0
    if turnos:
        razoes_fluxo.append(
            f"contador persistido em {turnos} turno(s) sem avanço"
        )
    if sequencia_sem_avanco:
        razoes_fluxo.append(
            f"{sequencia_sem_avanco} movimento(s) pareado(s) consecutivo(s) sem avanço"
        )
    if pontos_fluxo:
        razoes_fluxo.append(
            f"faixa principal de fluxo sem avanço (+{pontos_fluxo})"
        )

    pontos_repeticao = min(
        15,
        round(10 * razao_repeticao) + min(5, ciclos),
    )
    razoes_repeticao = []
    if repeticoes_cliente:
        razoes_repeticao.append(
            f"{repeticoes_cliente} resposta(s) do cliente repetida(s) na mesma etapa (+{round(10 * razao_repeticao)})"
        )
    if ciclos:
        razoes_repeticao.append(
            f"{ciclos} ciclo(s) de 2 ou 3 estados (+{min(5, ciclos)})"
        )

    latencias = _latencias_bot_cliente(mensagens)
    latencias_nao_estruturadas = [
        item["segundos"]
        for item in latencias
        if not item["estruturada_curta"]
    ]
    rapidas_nao_estruturadas = sum(
        valor <= 2 for valor in latencias_nao_estruturadas
    )
    rapidas_estruturadas = sum(
        item["segundos"] <= 2 and item["estruturada_curta"]
        for item in latencias
    )
    razao_rapida = _razao(
        rapidas_nao_estruturadas,
        len(latencias_nao_estruturadas),
    )
    cv = None
    if len(latencias_nao_estruturadas) >= 3:
        media = statistics.fmean(latencias_nao_estruturadas)
        if media > 0:
            cv = statistics.pstdev(latencias_nao_estruturadas) / media
    pontos_cadencia = min(
        20,
        round(14 * razao_rapida)
        + min(3, rapidas_estruturadas)
        + (6 if cv is not None and cv <= 0.12 else 0),
    )
    razoes_cadencia = []
    if rapidas_nao_estruturadas:
        razoes_cadencia.append(
            f"{rapidas_nao_estruturadas}/{len(latencias_nao_estruturadas)} latência(s) bot→cliente não estruturadas de até 2 s (+{round(14 * razao_rapida)})"
        )
    if rapidas_estruturadas:
        razoes_cadencia.append(
            f"{rapidas_estruturadas} resposta(s) estruturada(s) rápida(s), com peso reduzido (+{min(3, rapidas_estruturadas)})"
        )
    if cv is not None and cv <= 0.12:
        razoes_cadencia.append("latência bot→cliente muito regular (+6)")

    tipos_cliente = Counter(
        item["tipo_mensagem"] for item in clientes
    )
    tamanhos_cliente = [
        item["tamanho_texto"]
        for item in clientes
        if item.get("tamanho_texto") is not None
    ]
    tamanhos_estaveis = False
    if (
        len(tamanhos_cliente) >= 4
        and statistics.fmean(tamanhos_cliente) > 0
    ):
        tamanhos_estaveis = (
            statistics.pstdev(tamanhos_cliente)
            / statistics.fmean(tamanhos_cliente)
            <= 0.10
        )
    marcadores_automacao = sum(
        bool(item.get("tem_marcador_automacao"))
        or bool(
            item.get("texto")
            and re.search(
                r"\b(?:assistente virtual|mensagem autom[aá]tica|"
                r"n[aã]o consigo entender|digite uma op[cç][aã]o|"
                r"escolha uma op[cç][aã]o)\b",
                item["texto"],
                re.IGNORECASE,
            )
        )
        for item in clientes
    )
    mensagens_com_url = sum(bool(item.get("tem_url")) for item in clientes)
    somente_estruturadas_curtas = bool(clientes) and all(
        item["tipo_mensagem"]
        in {"button", "interactive", "list", "quick_reply"}
        and (item.get("tamanho_texto") or 0) <= 40
        for item in clientes
    )
    pontos_conteudo = min(
        15,
        (0 if somente_estruturadas_curtas else round(6 * razao_repeticao))
        + min(6, marcadores_automacao * 3)
        + min(2, mensagens_com_url)
        + (2 if tamanhos_estaveis and not somente_estruturadas_curtas else 0)
        + (
            1
            if len(tipos_cliente) == 1
            and len(clientes) >= 5
            and not somente_estruturadas_curtas
            else 0
        ),
    )
    razoes_conteudo = []
    if razao_repeticao and not somente_estruturadas_curtas:
        razoes_conteudo.append(
            f"templates idênticos do cliente na mesma etapa em {razao_repeticao:.0%} das respostas (+{round(6 * razao_repeticao)})"
        )
    if marcadores_automacao:
        razoes_conteudo.append(
            f"{marcadores_automacao} texto(s) do cliente com expressão de automação (+{min(6, marcadores_automacao * 3)})"
        )
    if mensagens_com_url:
        razoes_conteudo.append(
            f"{mensagens_com_url} mensagem(ns) do cliente com URL (+{min(2, mensagens_com_url)})"
        )
    if tamanhos_estaveis and not somente_estruturadas_curtas:
        razoes_conteudo.append("tamanho das mensagens do cliente muito estável (+2)")
    if (
        len(tipos_cliente) == 1
        and len(clientes) >= 5
        and not somente_estruturadas_curtas
    ):
        razoes_conteudo.append("um único tipo de mensagem do cliente (+1)")

    pontos_conclusao = 0
    razoes_conclusao = []
    duracao_segundos = None
    if conversa.get("finalizou_em") and conversa.get("iniciou_em"):
        duracao_segundos = max(
            0,
            (conversa["finalizou_em"] - conversa["iniciou_em"]).total_seconds(),
        )
        if len(clientes) >= 4 and duracao_segundos <= 30:
            pontos_conclusao = 10
        elif len(clientes) >= 3 and duracao_segundos <= 60:
            pontos_conclusao = 7
        elif len(clientes) >= 2 and duracao_segundos <= 120:
            pontos_conclusao = 4
        if pontos_conclusao:
            razoes_conclusao.append(
                f"conversa encerrada em {duracao_segundos:.0f} s com {len(clientes)} mensagens do cliente (+{pontos_conclusao})"
            )

    dimensoes = {
        "fluxo_sem_avanco": {
            "pontos": pontos_fluxo,
            "maximo": 70,
            "razoes": razoes_fluxo,
        },
        "repeticao_ciclos": {
            "pontos": pontos_repeticao,
            "maximo": 15,
            "razoes": razoes_repeticao,
        },
        "cadencia": {
            "pontos": pontos_cadencia,
            "maximo": 20,
            "razoes": razoes_cadencia,
        },
        "conteudo_automatizado": {
            "pontos": pontos_conteudo,
            "maximo": 15,
            "razoes": razoes_conteudo,
        },
        "conclusao_rapida": {
            "pontos": pontos_conclusao,
            "maximo": 10,
            "razoes": razoes_conclusao,
        },
    }
    score = min(100, sum(item["pontos"] for item in dimensoes.values()))
    return {
        "score": score,
        "dimensoes": dimensoes,
        "metricas": {
            "total_mensagens_analisadas": total,
            "mensagens_cliente": len(clientes),
            "mensagens_bot_contexto": len(bots_contexto),
            "movimentos": dict(contagem_movimentos),
            "maior_sequencia_sem_avanco": sequencia_sem_avanco,
            "respostas_cliente_repetidas_na_mesma_etapa": repeticoes_cliente,
            "ciclos_cliente_detectados": ciclos,
            "latencias_bot_cliente": [
                round(item["segundos"], 3) for item in latencias
            ],
            "duracao_segundos": duracao_segundos,
        },
    }


def _configurar_transacao(cursor, args):
    cursor.execute(
        "BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"
    )
    cursor.execute(
        "SELECT set_config('statement_timeout', %s, true)",
        (f"{args.statement_timeout_ms}ms",),
    )
    cursor.execute(
        "SELECT set_config('lock_timeout', %s, true)",
        (f"{args.lock_timeout_ms}ms",),
    )
    cursor.execute(
        "SELECT set_config('idle_in_transaction_session_timeout', %s, true)",
        (f"{args.idle_timeout_ms}ms",),
    )


def _possui_turnos_sem_avanco(cursor):
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'chatbot'
              AND table_name = 'conversa'
              AND column_name = 'turnos_sem_avanco'
        )
        """
    )
    return bool(cursor.fetchone()[0])


def _buscar_conversas(cursor, args, inicio, fim, possui_turnos):
    filtros = [
        "c.iniciou_em <= %s",
        "COALESCE(c.finalizou_em, c.last_interaction_at, c.iniciou_em) >= %s",
    ]
    parametros = [fim, inicio]
    if args.id_conversa:
        filtros.append("c.id_conversa = ANY(%s)")
        parametros.append(args.id_conversa)
    if args.id_unidade:
        filtros.append("c.id_unidade = ANY(%s)")
        parametros.append(args.id_unidade)
    coluna_turnos = (
        "c.turnos_sem_avanco"
        if possui_turnos
        else "NULL::integer AS turnos_sem_avanco"
    )
    parametros.append(args.limite_conversas + 1)
    cursor.execute(
        f"""
        SELECT
            c.id_conversa,
            c.id_cliente,
            cl.nome AS nome_cliente,
            cl.waid_telefone,
            c.id_unidade,
            u.nome AS nome_unidade,
            u.waba_id,
            u.phone_number_id,
            c.id_etapa_atual,
            c.status_ativa,
            c.iniciou_em,
            c.finalizou_em,
            c.motivo_encerramento,
            {coluna_turnos}
        FROM chatbot.conversa AS c
        JOIN chatbot.cliente AS cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade AS u
          ON u.id_unidade = c.id_unidade
        WHERE {" AND ".join(filtros)}
        ORDER BY c.iniciou_em DESC, c.id_conversa DESC
        LIMIT %s
        """,
        tuple(parametros),
    )
    linhas = cursor.fetchall()
    if len(linhas) > args.limite_conversas:
        raise RuntimeError(
            "limite de conversas atingido; reduza a janela ou refine os filtros"
        )
    chaves = (
        "id_conversa",
        "id_cliente",
        "nome_cliente",
        "waid_telefone",
        "id_unidade",
        "nome_unidade",
        "waba_id",
        "phone_number_id",
        "id_etapa_atual",
        "status_ativa",
        "iniciou_em",
        "finalizou_em",
        "motivo_encerramento",
        "turnos_sem_avanco",
    )
    return [dict(zip(chaves, linha)) for linha in linhas]


def _buscar_mensagens(cursor, ids_conversa, args, inicio, fim):
    if not ids_conversa:
        return defaultdict(list), {}
    texto_sql = (
        "h.conteudo_texto"
        if args.incluir_textos
        else "NULL::text AS conteudo_texto"
    )
    cursor.execute(
        f"""
        WITH ordenadas AS (
            SELECT
                h.id_mensagem,
                h.id_mensagem_fila,
                h.id_conversa,
                h.id_etapa,
                h.received_data_hora,
                h.tipo_mensagem,
                h.quem_enviou,
                CASE
                    WHEN NULLIF(BTRIM(h.conteudo_texto), '') IS NULL
                    THEN NULL
                    ELSE md5(
                        lower(
                            regexp_replace(
                                h.conteudo_texto,
                                '\\s+',
                                ' ',
                                'g'
                            )
                        )
                    )
                END AS fingerprint,
                char_length(h.conteudo_texto) AS tamanho_texto,
                COALESCE(
                    h.conteudo_texto ~* '(https?://|www\\.)',
                    FALSE
                ) AS tem_url,
                COALESCE(
                    h.conteudo_texto ~* (
                        'assistente virtual|mensagem autom[aá]tica|'
                        'n[aã]o consigo entender|digite uma op[cç][aã]o|'
                        'escolha uma op[cç][aã]o'
                    ),
                    FALSE
                ) AS tem_marcador_automacao,
                {texto_sql},
                row_number() OVER (
                    PARTITION BY h.id_conversa
                    ORDER BY h.received_data_hora DESC, h.id_mensagem DESC
                ) AS ordem,
                count(*) OVER (
                    PARTITION BY h.id_conversa
                ) AS total_conversa
            FROM chatbot.historico_mensagens AS h
            WHERE h.id_conversa = ANY(%s)
              AND h.received_data_hora >= %s
              AND h.received_data_hora <= %s
        )
        SELECT
            id_mensagem,
            id_mensagem_fila,
            id_conversa,
            id_etapa,
            received_data_hora,
            tipo_mensagem,
            quem_enviou,
            fingerprint,
            tamanho_texto,
            tem_url,
            tem_marcador_automacao,
            conteudo_texto,
            total_conversa
        FROM ordenadas
        WHERE ordem <= %s
        ORDER BY id_conversa, received_data_hora, id_mensagem
        LIMIT %s
        """,
        (
            ids_conversa,
            inicio,
            fim,
            args.limite_mensagens,
            args.max_mensagens_total + 1,
        ),
    )
    por_conversa = defaultdict(list)
    totais = {}
    for linha in cursor.fetchall():
        mensagem = {
            "id_mensagem": linha[0],
            "id_mensagem_fila": linha[1],
            "id_conversa": linha[2],
            "id_etapa": linha[3],
            "instante": linha[4],
            "tipo_mensagem": linha[5],
            "quem_enviou": linha[6],
            "fingerprint": linha[7],
            "tamanho_texto": linha[8],
            "tem_url": bool(linha[9]),
            "tem_marcador_automacao": bool(linha[10]),
            "texto": mascarar_pii(linha[11]) if linha[11] is not None else None,
        }
        por_conversa[linha[2]].append(mensagem)
        totais[linha[2]] = linha[12]
    carregadas = sum(len(itens) for itens in por_conversa.values())
    if carregadas > args.max_mensagens_total:
        raise RuntimeError(
            "limite total de mensagens atingido; reduza a janela ou os limites"
        )
    return por_conversa, totais


def gerar_relatorio(args, *, connection_factory=None):
    if connection_factory is None:
        configure_local_operations()
        from core.database.connection_aws import get_conn

        connection_factory = get_conn

    inicio, fim = resolver_janela(args)
    conn = connection_factory(
        application_name="relatorio_conversas_suspeitas_readonly"
    )
    try:
        cursor = conn.cursor()
        _configurar_transacao(cursor, args)
        possui_turnos = _possui_turnos_sem_avanco(cursor)
        conversas = _buscar_conversas(
            cursor,
            args,
            inicio,
            fim,
            possui_turnos,
        )
        ids = [item["id_conversa"] for item in conversas]
        mensagens, totais = _buscar_mensagens(
            cursor,
            ids,
            args,
            inicio,
            fim,
        )
        resultados = []
        for conversa in conversas:
            analise = pontuar_conversa(
                conversa,
                mensagens.get(conversa["id_conversa"], []),
            )
            if analise["score"] < args.limiar:
                continue
            item = {
                "id_conversa": conversa["id_conversa"],
                "id_cliente": conversa["id_cliente"],
                "nome_cliente_mascarado": mascarar_nome(
                    conversa["nome_cliente"]
                ),
                "wa_id_cliente": mascarar_wa_id(
                    conversa["waid_telefone"],
                    mostrar=args.mostrar_wa_id,
                ),
                "id_unidade": conversa["id_unidade"],
                "nome_unidade": conversa["nome_unidade"],
                "waba_id": conversa["waba_id"],
                "phone_number_id": conversa["phone_number_id"],
                "score": analise["score"],
                "status_ativa": conversa["status_ativa"],
                "id_etapa_atual": conversa["id_etapa_atual"],
                "iniciou_em": _iso(conversa["iniciou_em"]),
                "finalizou_em": _iso(conversa["finalizou_em"]),
                "motivo_encerramento": conversa["motivo_encerramento"],
                "turnos_sem_avanco": conversa["turnos_sem_avanco"],
                "historico_truncado": (
                    totais.get(conversa["id_conversa"], 0)
                    > args.limite_mensagens
                ),
                "metricas_sobre_recorte": (
                    "mensagens mais recentes da conversa dentro da janela"
                ),
                **analise,
            }
            if args.incluir_textos:
                item["amostras_texto_mascarado"] = [
                    {
                        "quem_enviou": mensagem["quem_enviou"],
                        "instante": _iso(mensagem["instante"]),
                        "texto": mensagem["texto"][: args.max_caracteres_texto],
                    }
                    for mensagem in mensagens.get(conversa["id_conversa"], [])
                    if mensagem.get("texto")
                ][: args.max_amostras_texto]
            resultados.append(item)
        resultados.sort(
            key=lambda item: (-item["score"], item["id_conversa"])
        )
        return {
            "metadados": {
                "gerado_em": datetime.now(timezone.utc).isoformat(),
                "inicio": inicio.isoformat(),
                "fim": fim.isoformat(),
                "somente_leitura": True,
                "isolamento": "REPEATABLE READ",
                "coluna_turnos_sem_avanco_disponivel": possui_turnos,
                "conversas_lidas": len(conversas),
                "conversas_reportadas": len(resultados),
                "limiar": args.limiar,
                "textos_incluidos": bool(args.incluir_textos),
                "wa_id_completo": bool(args.mostrar_wa_id),
                "recorte_historico": (
                    "até o limite de mensagens mais recentes por conversa "
                    "dentro da janela; métricas não representam mensagens "
                    "anteriores ao recorte"
                ),
            },
            "conversas": resultados,
        }
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def resolver_janela(args):
    fim = parse_instante(args.fim) if args.fim else datetime.now(timezone.utc)
    inicio = (
        parse_instante(args.inicio)
        if args.inicio
        else fim - timedelta(hours=args.ultimas_horas)
    )
    if inicio >= fim:
        raise ValueError("--inicio deve ser anterior a --fim")
    if fim - inicio > timedelta(days=31):
        raise ValueError("a janela máxima é de 31 dias")
    return inicio, fim


def _razoes_texto(item):
    razoes = []
    for nome, dimensao in item["dimensoes"].items():
        for razao in dimensao["razoes"]:
            razoes.append(f"{nome}: {razao}")
    return razoes


def formatar_texto(relatorio):
    meta = relatorio["metadados"]
    linhas = [
        "RELATÓRIO MANUAL DE CONVERSAS SUSPEITAS",
        (
            f"janela={meta['inicio']}..{meta['fim']} "
            f"lidas={meta['conversas_lidas']} "
            f"reportadas={meta['conversas_reportadas']} "
            f"limiar={meta['limiar']}"
        ),
    ]
    for item in relatorio["conversas"]:
        linhas.append(
            (
                f"\nconversa={item['id_conversa']} "
                f"cliente={item['id_cliente']} "
                f"wa_id={item['wa_id_cliente']} "
                f"unidade={item['id_unidade']} "
                f"waba_id={item['waba_id']} "
                f"phone_number_id={item['phone_number_id']} "
                f"score={item['score']}/100 "
                f"ativa={item['status_ativa']}"
            )
        )
        for razao in _razoes_texto(item):
            linhas.append(f"  - {razao}")
        if item.get("historico_truncado"):
            linhas.append("  - aviso: histórico truncado pelo limite de carga")
        for amostra in item.get("amostras_texto_mascarado", []):
            linhas.append(
                f"  - amostra {amostra['quem_enviou']} "
                f"{amostra['instante']}: {amostra['texto']}"
            )
    return "\n".join(linhas) + "\n"


def formatar_csv(relatorio):
    saida = io.StringIO()
    campos = [
        "id_conversa",
        "id_cliente",
        "nome_cliente_mascarado",
        "wa_id_cliente",
        "id_unidade",
        "nome_unidade",
        "waba_id",
        "phone_number_id",
        "score",
        "status_ativa",
        "id_etapa_atual",
        "iniciou_em",
        "finalizou_em",
        "turnos_sem_avanco",
        "historico_truncado",
        "razoes",
    ]
    writer = csv.DictWriter(saida, fieldnames=campos)
    writer.writeheader()
    for item in relatorio["conversas"]:
        linha = {campo: item.get(campo) for campo in campos}
        linha["razoes"] = " | ".join(_razoes_texto(item))
        writer.writerow(linha)
    return saida.getvalue()


def formatar_saida(relatorio, formato):
    if formato == "json":
        return json.dumps(
            relatorio,
            ensure_ascii=False,
            indent=2,
            default=_iso,
        ) + "\n"
    if formato == "csv":
        return formatar_csv(relatorio)
    return formatar_texto(relatorio)


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Gera relatório manual, explicável e somente leitura.",
    )
    parser.add_argument("--id-conversa", type=int, action="append")
    parser.add_argument("--id-unidade", type=int, action="append")
    parser.add_argument("--todas-unidades", action="store_true")
    parser.add_argument("--inicio")
    parser.add_argument("--fim")
    parser.add_argument("--ultimas-horas", type=int, default=24)
    parser.add_argument(
        "--limite-conversas",
        type=int,
        default=DEFAULT_LIMITE_CONVERSAS,
    )
    parser.add_argument(
        "--limite-mensagens",
        type=int,
        default=DEFAULT_LIMITE_MENSAGENS,
    )
    parser.add_argument(
        "--max-mensagens-total",
        type=int,
        default=MAX_MENSAGENS_TOTAL,
    )
    parser.add_argument("--limiar", type=int, default=DEFAULT_LIMIAR)
    parser.add_argument(
        "--formato",
        choices=("texto", "json", "csv"),
        default="texto",
    )
    parser.add_argument("--saida")
    parser.add_argument("--incluir-textos", action="store_true")
    parser.add_argument("--mostrar-wa-id", action="store_true")
    parser.add_argument("--max-amostras-texto", type=int, default=5)
    parser.add_argument("--max-caracteres-texto", type=int, default=160)
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=DEFAULT_STATEMENT_TIMEOUT_MS,
    )
    parser.add_argument(
        "--lock-timeout-ms",
        type=int,
        default=DEFAULT_LOCK_TIMEOUT_MS,
    )
    parser.add_argument(
        "--idle-timeout-ms",
        type=int,
        default=DEFAULT_IDLE_TIMEOUT_MS,
    )
    return parser


def validar_args(parser, args):
    if not (args.id_conversa or args.id_unidade or args.todas_unidades):
        parser.error(
            "informe --id-conversa, --id-unidade ou --todas-unidades"
        )
    limites = (
        ("--limite-conversas", args.limite_conversas, 1, MAX_CONVERSAS),
        (
            "--limite-mensagens",
            args.limite_mensagens,
            1,
            MAX_MENSAGENS_POR_CONVERSA,
        ),
        (
            "--max-mensagens-total",
            args.max_mensagens_total,
            1,
            MAX_MENSAGENS_TOTAL,
        ),
        ("--limiar", args.limiar, 0, 100),
        ("--ultimas-horas", args.ultimas_horas, 1, 31 * 24),
        ("--max-amostras-texto", args.max_amostras_texto, 0, 20),
        ("--max-caracteres-texto", args.max_caracteres_texto, 20, 500),
        ("--statement-timeout-ms", args.statement_timeout_ms, 100, 120000),
        ("--lock-timeout-ms", args.lock_timeout_ms, 50, 10000),
        ("--idle-timeout-ms", args.idle_timeout_ms, 1000, 120000),
    )
    for nome, valor, minimo, maximo in limites:
        if not minimo <= valor <= maximo:
            parser.error(f"{nome} deve estar entre {minimo} e {maximo}")
    if args.inicio and not args.fim:
        parser.error("--inicio exige --fim")
    ids = (args.id_conversa or []) + (args.id_unidade or [])
    if any(valor <= 0 for valor in ids):
        parser.error("IDs devem ser inteiros positivos")
    if (
        args.limite_conversas * args.limite_mensagens
        > args.max_mensagens_total
    ):
        parser.error(
            "--limite-conversas x --limite-mensagens não pode exceder "
            "--max-mensagens-total"
        )


def main(argv=None):
    parser = criar_parser()
    args = parser.parse_args(argv)
    validar_args(parser, args)
    try:
        relatorio = gerar_relatorio(args)
        conteudo = formatar_saida(relatorio, args.formato)
        if args.saida:
            with open(args.saida, "w", encoding="utf-8", newline="") as arquivo:
                arquivo.write(conteudo)
        else:
            sys.stdout.write(conteudo)
        return 0
    except (ValueError, RuntimeError) as exc:
        parser.exit(2, f"erro: {exc}\n")
    except Exception as exc:
        sys.stderr.write(f"erro ao gerar relatório: {type(exc).__name__}: {exc}\n")
        return 1


if __name__ == "__main__":
    argumentos = sys.argv[1:] or [
        "--todas-unidades",
        "--ultimas-horas",
        "24",
        "--formato",
        "texto",
    ]
    raise SystemExit(main(argumentos))
