"""Cliente HTTP da ApiCarrossel, sem acesso a banco ou controle de retry."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from core.integrations.funil.exceptions import (
    ErroIntegracaoFunil,
    OportunidadeRejeitadaFunil,
    RespostaFunilInvalida,
)


def montar_url_envio(link_api_carrossel, codigo_canal_venda):
    """Preserva o widget da unidade e força o canal configurado no Admin."""
    partes = urlsplit(link_api_carrossel.strip())
    parametros = dict(parse_qsl(partes.query, keep_blank_values=True))
    parametros["ForceCodeChannel"] = str(codigo_canal_venda).strip()

    return urlunsplit(
        (
            partes.scheme,
            partes.netloc,
            partes.path,
            urlencode(parametros),
            partes.fragment,
        )
    )


def enviar_oportunidade(
    *,
    link_api_carrossel,
    codigo_canal_venda,
    payload,
    timeout,
    session=requests,
):
    """Envia uma oportunidade e valida HTTP e o status lógico da API."""
    url = montar_url_envio(link_api_carrossel, codigo_canal_venda)

    try:
        response = session.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        raise ErroIntegracaoFunil(
            f"Falha HTTP ao enviar oportunidade: {exc}"
        ) from exc

    try:
        corpo = response.json()
    except ValueError as exc:
        raise RespostaFunilInvalida(
            "A ApiCarrossel não retornou um JSON válido"
        ) from exc

    if not isinstance(corpo, dict):
        raise RespostaFunilInvalida(
            "A ApiCarrossel retornou uma estrutura inesperada"
        )

    status_logico = str(corpo.get("response", "")).strip().casefold()
    if status_logico != "success":
        detalhe = corpo.get("message") or corpo.get("error") or status_logico
        raise OportunidadeRejeitadaFunil(
            f"A ApiCarrossel recusou a oportunidade: {detalhe or 'sem detalhe'}"
        )

    return {
        "status_http": response.status_code,
        "resposta": corpo,
    }

