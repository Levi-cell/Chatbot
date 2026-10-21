"""Leitura do consumo Meta por conta e número; sem persistência ou bootstrap de IDE."""

import json
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests

INICIO_FRANQUIA = date(2026, 10, 1)
LIMITE_MENSAL = 1000
LIMITE_MENSAL_ESL = 1000
TIPOS_PRECO = ("FREE_CUSTOMER_SERVICE", "FREE_ENTRY_POINT", "REGULAR")
# IDs oficiais da Meta, não deslocamentos UTC. O fuso IANA define os limites
# do mês inclusive quando houver mudança de regras regionais no calendário.
# https://developers.facebook.com/docs/marketing-api/reference/ad-account/timezone-ids/
FUSOS_META_BRASIL = {
    "22": "America/Noronha", "23": "America/Campo_Grande",
    "24": "America/Belem", "25": "America/Sao_Paulo",
    "195": "America/Araguaina", "206": "America/Bahia",
    "210": "America/Boa_Vista", "218": "America/Cuiaba",
    "222": "America/Eirunepe", "224": "America/Fortaleza",
    "248": "America/Maceio", "249": "America/Manaus",
    "270": "America/Porto_Velho", "273": "America/Recife",
    "275": "America/Rio_Branco", "276": "America/Santarem",
}
def _validar_id(valor, nome):
    identificador = str(valor or "").strip()
    if not re.fullmatch(r"[0-9]+", identificador):
        raise ValueError(f"{nome} deve conter somente dígitos ASCII")
    return identificador


def _normalizar_telefone(valor):
    texto = str(valor or "").strip()
    if not re.fullmatch(r"\+?[0-9 ()-]+", texto):
        raise RuntimeError("A Meta retornou um telefone inválido")
    numero = re.sub(r"[^0-9]", "", texto)
    if not 7 <= len(numero) <= 15:
        raise RuntimeError("A Meta retornou um telefone inválido")
    return numero


def _consultar_json(session, caminho, params):
    # Import tardio: CLI ou IDE escolhe o ambiente antes da configuração.
    from core.integrations.whatsapp.tools.config import (
        construir_url_graph_api,
        get_meta_http_timeout,
        get_token_usuario_meta,
    )

    try:
        resposta = session.get(
            construir_url_graph_api(caminho),
            headers={"Authorization": f"Bearer {get_token_usuario_meta()}"},
            params=params,
            timeout=get_meta_http_timeout(),
            allow_redirects=False,
        )
    except requests.RequestException:
        raise RuntimeError("Falha de conexão ao consultar a Meta") from None
    try:
        dados = resposta.json()
    except ValueError:
        raise RuntimeError("A Meta não retornou JSON válido") from None
    if not isinstance(dados, dict):
        raise RuntimeError("A Meta retornou uma estrutura inesperada")
    if not 200 <= resposta.status_code < 300 or "error" in dados:
        erro = dados.get("error")
        codigo = erro.get("code") if isinstance(erro, dict) else None
        detalhe = f", código Meta {codigo}" if type(codigo) is int else ""
        # Não imprimir payload, token, URL de paginação ou mensagem arbitrária.
        raise RuntimeError(
            f"A Meta recusou a consulta (HTTP {resposta.status_code}{detalhe})"
        )
    return dados


def _listar_numeros(session, waba_id):
    params = {"fields": "id,display_phone_number,verified_name", "limit": 100}
    numeros = {}
    cursores_vistos = set()
    while True:
        dados = _consultar_json(session, f"{waba_id}/phone_numbers", params)
        pagina = dados.get("data")
        if not isinstance(pagina, list):
            raise RuntimeError("Lista de números ausente na resposta da Meta")
        for item in pagina:
            if not isinstance(item, dict):
                raise RuntimeError("Número inválido na resposta da Meta")
            phone_id = _validar_id(item.get("id"), "phone_number_id retornado")
            numeros[phone_id] = {
                "phone_number_id": phone_id,
                "telefone": _normalizar_telefone(item.get("display_phone_number")),
                "nome": item.get("verified_name") or "",
            }
        paging = dados.get("paging") or {}
        if not isinstance(paging, dict):
            raise RuntimeError("Paginação de números inválida")
        if not paging.get("next"):
            return list(numeros.values())
        cursores = paging.get("cursors")
        cursor = cursores.get("after") if isinstance(cursores, dict) else None
        if not isinstance(cursor, str) or not cursor or cursor in cursores_vistos:
            raise RuntimeError("Paginação de números incompleta ou repetida")
        cursores_vistos.add(cursor)
        # Nunca seguir URLs arbitrárias que possam carregar o access_token.
        params["after"] = cursor


def _consultar_fuso_waba(session, waba_id):
    """Lê o fuso da conta de mensagens, sem alterar a WABA ou o portfólio."""
    dados = _consultar_json(session, waba_id, {"fields": "id,timezone_id"})
    if str(dados.get("id")) != waba_id:
        raise RuntimeError("A Meta não confirmou a identificação da WABA")
    timezone_id = str(dados.get("timezone_id"))
    fuso = FUSOS_META_BRASIL.get(timezone_id)
    if fuso is None:
        # Inclusive TZ_UNKNOWN=0: não presumir UTC ou o fuso do servidor.
        raise RuntimeError(
            "Fuso da WABA ausente ou não mapeado entre os fusos brasileiros; "
            "confira timezone_id antes de consultar um período mensal"
        )
    return timezone_id, fuso


def _exigir_metricas_completas(objeto):
    paging = objeto.get("paging") or {}
    if not isinstance(paging, dict):
        raise RuntimeError("Paginação de métricas inválida; saldo indisponível")
    if paging.get("next"):
        raise RuntimeError("Métricas paginadas; saldo parcial não será calculado")


def _resolver_periodo(mes, fuso_horario, agora):
    try:
        fuso = ZoneInfo(fuso_horario)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ValueError("Informe um fuso IANA, como America/Sao_Paulo") from None
    agora = agora or datetime.now(timezone.utc)
    if agora.tzinfo is None or agora.utcoffset() is None:
        raise ValueError("O instante da consulta precisa conter fuso horário")
    agora = agora.astimezone(fuso)
    mes = mes or agora.strftime("%Y-%m")
    if not isinstance(mes, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}", mes):
        raise ValueError("Use --mes no formato AAAA-MM")
    try:
        ano, numero_mes = map(int, mes.split("-"))
        inicio = datetime(ano, numero_mes, 1, tzinfo=fuso)
        proximo_mes = datetime(
            ano + (numero_mes == 12), numero_mes % 12 + 1, 1, tzinfo=fuso
        )
    except ValueError:
        raise ValueError("Mês inválido") from None
    # Graph recebe timestamps em segundos inteiros. O retorno precisa indicar
    # o mesmo limite solicitado, sem alegar cobertura de frações de segundo.
    fim_consulta = min(proximo_mes, agora).replace(microsecond=0)
    if inicio >= fim_consulta:
        raise ValueError("O mês informado ainda não possui período consultável")
    return inicio, fim_consulta, agora, proximo_mes


def _somar_metricas(dados, telefone):
    analytics = dados.get("pricing_analytics")
    if not isinstance(analytics, dict) or not isinstance(analytics.get("data"), list):
        raise RuntimeError("pricing_analytics ausente ou inválido; saldo indisponível")
    # Se a API mudar para uma resposta paginada, não anunciar saldo parcial.
    for objeto in (dados, analytics):
        _exigir_metricas_completas(objeto)
    totais = dict.fromkeys(TIPOS_PRECO, 0)
    for grupo in analytics["data"]:
        if not isinstance(grupo, dict) or not isinstance(grupo.get("data_points"), list):
            raise RuntimeError("Pontos de análise ausentes; saldo indisponível")
        _exigir_metricas_completas(grupo)
        for ponto in grupo["data_points"]:
            if not isinstance(ponto, dict):
                raise RuntimeError("Ponto de análise inválido")
            if _normalizar_telefone(ponto.get("phone_number")) != telefone:
                raise RuntimeError("A Meta retornou métricas de outro telefone")
            if ponto.get("pricing_category") != "SERVICE":
                raise RuntimeError("A Meta retornou categoria diferente de SERVICE")
            tipo = ponto.get("pricing_type")
            volume = ponto.get("volume")
            if tipo not in totais or type(volume) is not int or volume < 0:
                raise RuntimeError("Tipo de preço ou volume inesperado; saldo indisponível")
            totais[tipo] += volume
    return totais


def consultar_franquia_meta(
    waba_id, *, fuso_horario=None, phone_number_id=None, mes=None,
    session=requests, agora=None,
):
    """Retorna métricas e saldo estimado por número, sem efeitos de escrita.

    Núcleo compartilhado pelo worker e utilitário: recebe o ambiente já carregado, somente faz GET
    e retorna dados; não imprime, dorme, reinicia ambiente ou grava no banco.
    O token vem da configuração central. Para uma unidade, informe waba_id e
    phone_number_id; sem o segundo, consulta todos os números da WABA.
    Consulta o timezone_id da WABA. fuso_horario, quando informado, é uma
    conferência explícita e deve coincidir com o fuso da conta, não substituí-lo.
    Antes de outubro/2026, FREE_CUSTOMER_SERVICE não representa consumo da nova
    franquia: nesse caso o saldo e a divisão ESL/unidade retornam None.
    """
    waba_id = _validar_id(waba_id, "waba_id")
    if phone_number_id is not None:
        phone_number_id = _validar_id(phone_number_id, "phone_number_id")
    referencia = agora or datetime.now(timezone.utc)
    if fuso_horario is not None:
        # Rejeitar parâmetros locais inválidos antes de acessar a API.
        _resolver_periodo(mes, fuso_horario, referencia)
    timezone_id, fuso_waba = _consultar_fuso_waba(session, waba_id)
    if fuso_horario is not None and fuso_horario != fuso_waba:
        raise ValueError(
            f"Fuso informado diverge da WABA: a Meta informa {fuso_waba}. "
            "Omita fuso_horario para usar o da conta automaticamente"
        )
    conta = {"waba_id": waba_id, "timezone_id": timezone_id, "fuso_horario": fuso_waba}
    return consultar_metricas_conta(
        conta, phone_number_id=phone_number_id, mes=mes, session=session, agora=referencia,
    )


def consultar_conta_consumo(waba_id, *, session=requests):
    """Resolve o fuso uma vez por conta/ciclo, antes de consultar seus meses."""
    waba_id = _validar_id(waba_id, "waba_id")
    timezone_id, nome = _consultar_fuso_waba(session, waba_id)
    return {"waba_id": waba_id, "timezone_id": timezone_id, "fuso_horario": nome}


def consultar_metricas_conta(conta, *, phone_number_id, mes=None, session=requests, agora=None):
    """Consulta volumes usando a conta já validada neste ciclo pelo worker.

    O cadastro de fuso pode ser confirmado antes desta operação; erro nos volumes
    não transforma essa leitura em uma coleta mensal bem-sucedida.
    """
    waba_id = _validar_id(conta["waba_id"], "waba_id")
    timezone_id = str(conta["timezone_id"])
    fuso_horario = conta["fuso_horario"]
    if FUSOS_META_BRASIL.get(timezone_id) != fuso_horario:
        raise ValueError("Código e nome de fuso inconsistentes.")
    referencia = agora or datetime.now(timezone.utc)
    if phone_number_id is not None:
        phone_number_id = _validar_id(phone_number_id, "phone_number_id")
    inicio, fim, instante, fim_mensal = _resolver_periodo(mes, fuso_horario, referencia)
    numeros = _listar_numeros(session, waba_id)
    if phone_number_id is not None:
        numeros = [n for n in numeros if n["phone_number_id"] == phone_number_id]
        if not numeros:
            raise ValueError("O phone_number_id não pertence à WABA consultada")

    franquia_vigente = inicio.date() >= INICIO_FRANQUIA
    resultados = []
    for numero in numeros:
        telefone = numero["telefone"]
        fields = (
            f"pricing_analytics.start({int(inicio.timestamp())})"
            f".end({int(fim.timestamp())}).granularity(DAILY)"
            f".phone_numbers({json.dumps([telefone])})"
            ".metric_types(VOLUME).pricing_categories(SERVICE)"
            ".dimensions(PHONE,PRICING_CATEGORY,PRICING_TYPE)"
        )
        totais = _somar_metricas(
            _consultar_json(session, waba_id, {"fields": fields}), telefone
        )
        consumidas = totais["FREE_CUSTOMER_SERVICE"] if franquia_vigente else None
        cobradas = totais["REGULAR"]
        resultados.append({
            **numero,
            "volumes_por_tipo": totais,
            "total_mensagens": sum(totais.values()),
            "mensagens_cobradas_meta": cobradas,
            "franquia_mensal": LIMITE_MENSAL if franquia_vigente else None,
            "consumidas_na_franquia": consumidas,
            "restantes_estimadas": (
                max(0, LIMITE_MENSAL - consumidas) if franquia_vigente else None
            ),
            # Benefício comercial da ESL, separado da franquia concedida pela
            # Meta. São quantidades, não valores monetários ou fatura fechada.
            "limite_mensal_esl": LIMITE_MENSAL_ESL if franquia_vigente else None,
            "mensagens_assumidas_esl": (
                min(cobradas, LIMITE_MENSAL_ESL) if franquia_vigente else None
            ),
            "mensagens_excedentes_unidade": (
                max(cobradas - LIMITE_MENSAL_ESL, 0) if franquia_vigente else None
            ),
        })
    avisos = [
        "Estimativa de analytics, não saldo em tempo real nem garantia de envio gratuito.",
        "Escopo: serviço individual desta WABA; grupos e outras contas no mesmo "
        "número podem consumir a mesma franquia e não estão incluídos neste cálculo.",
        "Volumes de mensagens entregues na categoria SERVICE, não apenas envios "
        "aceitos pela API nem todas as categorias do WhatsApp.",
        "Fuso consultado na WABA. O fim do período mensal é fixo; "
        "fim_exclusivo limita a consulta ao instante de referência no mês atual.",
    ]
    if not franquia_vigente:
        avisos.append(
            "Período anterior a 01/10/2026: FREE_CUSTOMER_SERVICE ainda não mede "
            "a nova franquia de 1.000; os campos de saldo ficam nulos. Nesse "
            "período a categoria SERVICE também pode incluir templates de utilidade."
        )
    return {
        "waba_id": waba_id,
        "mes": inicio.strftime("%Y-%m"),
        "fuso_horario": fuso_horario,
        "timezone_id": timezone_id,
        "inicio_inclusivo": inicio.isoformat(),
        "fim_exclusivo": fim.isoformat(),
        "data_hora_inicio": inicio.isoformat(),
        "data_hora_fim": fim_mensal.isoformat(),
        "mes_em_andamento": instante < fim_mensal,
        "categoria_consultada": "SERVICE",
        "consultado_em": instante.isoformat(),
        "franquia_vigente_no_periodo": franquia_vigente,
        "numeros": resultados,
        "avisos": avisos,
    }


