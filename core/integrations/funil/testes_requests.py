"""Ferramentas manuais para validar a integração sem consultar o chatbot."""

import json
from datetime import datetime

import requests

from core.integrations.funil.cliente import enviar_oportunidade
from core.integrations.funil.oportunidades import (
    montar_dados_lead_teste,
    montar_payload_oportunidade,
)


URL_CONSULTA_INTEGRACOES = (
    "https://leads.funildevendas.com.br/supera/ApiConsult"
)
URL_BASE_CONSULTA_OPORTUNIDADES = (
    "https://app.funildevendas.com.br/api/v2/methodologies"
)

WIDGET_UNIDADE_SAJ = "FJA4E20240923185844"
LINK_API_UNIDADE_SAJ = (
    "https://leads.funildevendas.com.br/apicarrossel/api/"
    "?W=FJA4E20240923185844"
)
CANAL_META_ADS = "113340"
HTTP_TIMEOUT = (10, 30)


def consultar_integracao_unidade(widget=WIDGET_UNIDADE_SAJ):
    """Consulta o catálogo público e retorna a integração da unidade."""
    response = requests.get(URL_CONSULTA_INTEGRACOES, timeout=HTTP_TIMEOUT)
    response.raise_for_status()

    try:
        integracoes = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "O catálogo ApiCarrossel não retornou um JSON válido"
        ) from exc

    if not isinstance(integracoes, list):
        raise RuntimeError(
            "O catálogo ApiCarrossel retornou uma estrutura inesperada"
        )

    for integracao in integracoes:
        if integracao.get("Widget") == widget:
            return {
                "nome_unidade": integracao.get("Name_Widget"),
                "widget": integracao.get("Widget"),
                "link": integracao.get("Link"),
                "ativa": str(integracao.get("Active_Widget")) == "1",
                "salva_em": integracao.get("SaveDate_Widget"),
            }

    return None


def montar_payload_oportunidade_teste():
    """Monta o lead fictício completo sem executar qualquer POST."""
    return montar_payload_oportunidade(montar_dados_lead_teste())


def criar_oportunidade_teste(*, confirmar_envio_real=False):
    """Cria um lead de teste real somente mediante confirmação explícita."""
    if confirmar_envio_real is not True:
        raise ValueError(
            "Passe confirmar_envio_real=True para inserir o teste no CRM"
        )

    return enviar_oportunidade(
        link_api_carrossel=LINK_API_UNIDADE_SAJ,
        codigo_canal_venda=CANAL_META_ADS,
        payload=montar_payload_oportunidade_teste(),
        timeout=HTTP_TIMEOUT,
    )


def consultar_codigo_oportunidade(
    *,
    titulo,
    codigo_funil,
    email_api,
    senha_api,
    data_inicial=None,
    data_final=None,
):
    """Localiza pelo título exato e devolve o código da oportunidade."""
    hoje = datetime.now().astimezone().date()
    data_inicial = data_inicial or hoje
    data_final = data_final or hoje

    response = requests.get(
        f"{URL_BASE_CONSULTA_OPORTUNIDADES}/{codigo_funil}/opportunities/",
        params={
            "text": titulo,
            "initial_date": _formatar_data_consulta(data_inicial),
            "final_date": _formatar_data_consulta(data_final),
            "offset": 0,
            "limit": 100,
        },
        auth=(email_api, senha_api),
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()

    try:
        corpo = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "A consulta de oportunidades não retornou um JSON válido"
        ) from exc

    resultados = corpo.get("results")
    if not isinstance(resultados, list):
        raise RuntimeError(
            "A consulta de oportunidades retornou uma estrutura inesperada"
        )

    titulo_normalizado = titulo.strip().casefold()
    correspondencias = [
        oportunidade
        for oportunidade in resultados
        if str(oportunidade.get("title", "")).strip().casefold()
        == titulo_normalizado
    ]

    if not correspondencias:
        return None
    if len(correspondencias) > 1:
        codigos = [item.get("code") for item in correspondencias]
        raise RuntimeError(
            "Mais de uma oportunidade possui o mesmo título exato: "
            f"códigos={codigos}"
        )

    codigo = correspondencias[0].get("code")
    if codigo is None:
        raise RuntimeError(
            "A oportunidade foi localizada, mas veio sem o campo code"
        )
    return codigo


def _formatar_data_consulta(valor):
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def _imprimir_resultado(resultado):
    print(json.dumps(resultado, ensure_ascii=False, indent=2))




print(criar_oportunidade_teste(confirmar_envio_real=True))