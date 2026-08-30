"""Sondas manuais do Funil de SAJ sem usar o chatbot."""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.integrations.funil.cliente import enviar_oportunidade
from core.integrations.funil.oportunidades import montar_payload_oportunidade
from utilitarios.montar_lead_teste import montar_dados_lead_teste_saj


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
    """Monta o lead fictício de SAJ sem executar qualquer POST."""
    return montar_payload_oportunidade(montar_dados_lead_teste_saj())


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


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Consulta e testa a integração externa do Funil de SAJ.",
    )
    subparsers = parser.add_subparsers(dest="comando", required=True)
    catalogo = subparsers.add_parser(
        "catalog",
        help="consulta a integração de uma unidade pelo widget",
    )
    catalogo.add_argument("--widget", default=WIDGET_UNIDADE_SAJ)
    subparsers.add_parser(
        "payload",
        help="mostra o payload fictício sem executar POST",
    )
    envio = subparsers.add_parser(
        "send-test",
        help="insere uma oportunidade fictícia real no CRM",
    )
    envio.add_argument(
        "--confirm-real-send",
        action="store_true",
        help="confirma conscientemente o POST real no CRM",
    )
    return parser


def main(argv=None):
    parser = criar_parser()
    args = parser.parse_args(argv)

    try:
        if args.comando == "catalog":
            _imprimir_resultado(
                consultar_integracao_unidade(widget=args.widget)
            )
            return 0

        if args.comando == "payload":
            _imprimir_resultado(montar_payload_oportunidade_teste())
            return 0

        if not args.confirm_real_send:
            parser.error("send-test exige --confirm-real-send")

        _imprimir_resultado(
            criar_oportunidade_teste(confirmar_envio_real=True)
        )
        return 0
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        print(
            f"FUNIL_SAJ_FALHOU: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
