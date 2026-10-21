"""Apresentação do consumo mensal: datas locais e cálculos compartilhados com PDF."""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from django.db import connection

from core.consumo_meta.apuracao import ESTADOS_APURACAO, calcular_resumo
from core.consumo_meta.periodos import INICIO_ACOMPANHAMENTO, primeiro_dia, validar_mes
from core.repositories.monitoramento import consumo as repositorio

MESES = ("Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez")
AVISO_PRE_LANCAMENTO = "Disponível apenas dia primeiro de outubro."
# Referência somente para a navegação antes de o worker identificar o fuso.
# Não preenche a unidade nem define recortes, saldos ou coletas na Meta.
FUSO_NAVEGACAO_INICIAL = "America/Sao_Paulo"


def rotulo_mes(mes):
    return f"{MESES[mes.month - 1]} · {mes.year}"


def apresentar_mes(registro, agora):
    fuso = ZoneInfo(registro["fuso_horario"])
    estado = registro["status_apuracao"]
    if estado == "em_andamento" and agora >= registro["data_hora_fim"]:
        estado = "em_conferencia"
    resultado = {chave: registro[chave] for chave in (
        "qtd_janela_gratuita", "qtd_franquia_consumida", "qtd_cobradas_meta",
        "franquia_meta_mensal", "beneficio_esl_mensal", "fuso_horario",
    )}
    for campo in ("data_hora_inicio", "data_hora_fim", "ultimo_sucesso_em", "consolidado_em"):
        valor = registro.get(campo)
        resultado[campo] = valor.astimezone(fuso).isoformat() if valor else None
    inicio = registro["data_hora_inicio"].astimezone(fuso).strftime("%d/%m/%Y %H:%M")
    fim = registro["data_hora_fim"].astimezone(fuso).strftime("%d/%m/%Y %H:%M")
    resultado.update(
        mes=registro["mes_referencia"].strftime("%Y-%m"), rotulo=rotulo_mes(registro["mes_referencia"]),
        status_apuracao=estado, status_rotulo=dict(ESTADOS_APURACAO)[estado],
        periodo_texto=f"{inicio} até {fim} (fim exclusivo)",
        tarifa_referencia_brl=str(registro["tarifa_referencia_brl"]),
        tarifa_vigencia=registro["tarifa_vigencia"].isoformat(),
        coleta_com_falha=bool(registro.get("ultimo_erro")),
        **calcular_resumo(registro),
    )
    return resultado


def carregar_consumo(acesso, mes=None, *, agora=None):
    """Lê a unidade do guard; IDs enviados pelo navegador não definem o escopo."""
    escolhido = validar_mes(mes) if mes else None
    agora = agora or datetime.now(timezone.utc)
    with connection.cursor() as cursor:
        unidade = repositorio.buscar_unidade(cursor, acesso.id_unidade)
        if unidade is None:
            raise ValueError("Unidade indisponível.")
        nome_fuso = unidade["nome_fuso"]
        atual = primeiro_dia(agora, nome_fuso or FUSO_NAVEGACAO_INICIAL)
        pre_lancamento = atual < INICIO_ACOMPANHAMENTO
        limite = INICIO_ACOMPANHAMENTO if pre_lancamento else atual
        if escolhido and (escolhido < INICIO_ACOMPANHAMENTO or escolhido > limite):
            raise ValueError("Mês fora do período de acompanhamento.")
        if pre_lancamento:
            # Outubro é a única exceção à lista sem meses futuros. A prévia não
            # expõe indicadores ou PDFs, mesmo se houver registros antecipados.
            return {
                "unidade": {"nome": unidade["nome_unidade"]},
                "mes_atual": atual.strftime("%Y-%m"),
                "mes_selecionado": INICIO_ACOMPANHAMENTO.strftime("%Y-%m"),
                "meses": [{"chave": "2026-10", "rotulo": rotulo_mes(INICIO_ACOMPANHAMENTO), "atual": False}],
                "selecionado": None, "historico": [],
                "aviso": AVISO_PRE_LANCAMENTO, "coleta_com_falha": False,
                "pre_lancamento": True,
            }
        registros = [registro for registro in repositorio.listar_meses(cursor, acesso.id_unidade)
                     if INICIO_ACOMPANHAMENTO <= registro["mes_referencia"] <= atual]
        registros.sort(key=lambda registro: registro["mes_referencia"], reverse=True)
        disponiveis = {registro["mes_referencia"] for registro in registros} | {atual}
        escolhido = escolhido or atual
        if escolhido not in disponiveis:
            raise ValueError("Mês sem histórico disponível para esta unidade.")
        chave = escolhido.strftime("%Y-%m")
        falha_periodo = repositorio.buscar_falha_periodo(cursor, acesso.id_unidade, chave)
    historico = [apresentar_mes(registro, agora) for registro in registros]
    selecionado = next((registro for registro in historico if registro["mes"] == chave), None)
    meses = [{"chave": item.strftime("%Y-%m"), "rotulo": rotulo_mes(item), "atual": item == atual}
             for item in sorted(disponiveis, reverse=True)]
    erro = bool(unidade.get("erro_conta") or (falha_periodo or {}).get("ultimo_erro"))
    aviso = ""
    if erro:
        aviso = "Não foi possível concluir a última coleta. Os últimos dados disponíveis foram preservados."
    elif selecionado is None:
        aviso = "Aguardando a primeira coleta válida deste mês."
    return {
        "unidade": {"nome": unidade["nome_unidade"]},
        "mes_atual": atual.strftime("%Y-%m"),
        "mes_selecionado": chave, "meses": meses, "selecionado": selecionado,
        "historico": historico, "aviso": aviso, "coleta_com_falha": erro,
        "pre_lancamento": False,
    }
