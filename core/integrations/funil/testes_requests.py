import json
from datetime import datetime
from urllib.parse import urlencode

import requests


URL_CONSULTA_INTEGRACOES = (
    "https://leads.funildevendas.com.br/supera/ApiConsult"
)
URL_BASE_API_CARROSSEL = (
    "https://leads.funildevendas.com.br/apicarrossel/api/"
)
URL_BASE_CONSULTA_OPORTUNIDADES = (
    "https://app.funildevendas.com.br/api/v2/methodologies"
)

WIDGET_UNIDADE_SAJ = "FJA4E20240923185844"
CANAL_META_ADS = 113340

HTTP_TIMEOUT = (10, 30)

OBSERVACOES_TESTE = (
    "TESTE DE INTEGRACAO DO CHATBOT.\n"
    "Oportunidade criada somente para validar o envio automatico ao CRM.\n"
    "Nao entrar em contato com este registro."
)
ORIGEM_LEAD_TESTE = "Chatbot - Meta Ads"

MARCADORES_API_CARROSSEL = {
    "codigo_vendedor": "Code_User",
    "codigo_metodologia": "Code_Methodology",
    "codigo_canal_venda": "Code_Channel",
    "codigo_etapa": "Code_StepMethodology",
}


def montar_url_api_carrossel(
    widget=WIDGET_UNIDADE_SAJ,
    codigo_canal=CANAL_META_ADS,
):
    query_string = urlencode(
        {
            "W": widget,
            "ForceCodeChannel": codigo_canal,
        }
    )
    return f"{URL_BASE_API_CARROSSEL}?{query_string}"


def consultar_integracao_unidade(widget=WIDGET_UNIDADE_SAJ):
    """Consulta o catalogo publico e retorna a integracao da unidade."""
    response = requests.get(
        URL_CONSULTA_INTEGRACOES,
        timeout=HTTP_TIMEOUT,
    )
    response.raise_for_status()

    try:
        integracoes = response.json()
    except ValueError as exc:
        raise RuntimeError(
            "O catalogo ApiCarrossel nao retornou um JSON valido."
        ) from exc

    if not isinstance(integracoes, list):
        raise RuntimeError(
            "O catalogo ApiCarrossel retornou uma estrutura inesperada."
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


def montar_payload_oportunidade_teste(
    *,
    nome_contato,
    email="",
    telefone="",
    titulo=None,
    observacoes=OBSERVACOES_TESTE,
    origem_lead=ORIGEM_LEAD_TESTE,
):
    """Monta uma oportunidade de teste com os campos validados no CRM."""
    if not titulo:
        agora = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        titulo = f"[TESTE CHATBOT {agora}] {nome_contato}"

    return {
        "oportunidades": [
            {
                "titulo": titulo,
                "valor": "0",
                **MARCADORES_API_CARROSSEL,
                "personalizados": [
                    {
                        "titulo": "Observações",
                        "valor": observacoes,
                    },
                    {
                        "titulo": "Origem do lead",
                        "valor": origem_lead,
                    },
                ],
                "empresa": {
                    "nome": nome_contato,
                    "cnpj": "",
                    "codigo_segmento": "0",
                    "endereco_completo": {
                        "logradouro": "",
                        "numero": "",
                        "complemento": "",
                        "bairro": "",
                        "cidade": "",
                        "uf": "",
                        "cep": "",
                    },
                    "personalizados": [],
                },
                "contato": {
                    "nome": nome_contato,
                    "email": email,
                    "telefone1": telefone,
                    "telefone2": "",
                    "cargo": "",
                    "cpf": "",
                    "personalizados": [],
                },
            }
        ]
    }


def criar_oportunidade_teste(
    *,
    confirmar_envio_real=False,
    nome_contato="Teste Chatbot - Nao contatar",
    email="",
    telefone="",
    titulo=None,
    observacoes=OBSERVACOES_TESTE,
    origem_lead=ORIGEM_LEAD_TESTE,
):
    """Envia uma oportunidade real para a unidade configurada no endpoint."""
    if confirmar_envio_real is not True:
        raise ValueError(
            "Passe confirmar_envio_real=True para inserir no CRM."
        )

    payload = montar_payload_oportunidade_teste(
        nome_contato=nome_contato,
        email=email,
        telefone=telefone,
        titulo=titulo,
        observacoes=observacoes,
        origem_lead=origem_lead,
    )
    response = requests.post(
        montar_url_api_carrossel(),
        json=payload,
        timeout=HTTP_TIMEOUT,
    )

    return {
        "status_http": response.status_code,
        "sucesso_http": response.ok,
        "content_type": response.headers.get("Content-Type"),
        "resposta": _normalizar_resposta(response),
        "titulo_enviado": payload["oportunidades"][0]["titulo"],
    }


def consultar_codigo_oportunidade(
    *,
    titulo,
    codigo_funil,
    email_api,
    senha_api,
    data_inicial=None,
    data_final=None,
):
    """Localiza pelo titulo exato e devolve o codigo da oportunidade.

    A consulta pertence a API autenticada do Funil de Vendas. As credenciais
    sao argumentos para que este arquivo de teste nao armazene senha real.
    """
    hoje = datetime.now().astimezone().date()
    data_inicial = data_inicial or hoje
    data_final = data_final or hoje

    response = requests.get(
        (
            f"{URL_BASE_CONSULTA_OPORTUNIDADES}/"
            f"{codigo_funil}/opportunities/"
        ),
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
            "A consulta de oportunidades nao retornou um JSON valido."
        ) from exc

    resultados = corpo.get("results")
    if not isinstance(resultados, list):
        raise RuntimeError(
            "A consulta de oportunidades retornou uma estrutura inesperada."
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
        codigos = [
            oportunidade.get("code")
            for oportunidade in correspondencias
        ]
        raise RuntimeError(
            "Mais de uma oportunidade possui o mesmo titulo exato: "
            f"codigos={codigos}."
        )

    codigo = correspondencias[0].get("code")
    if codigo is None:
        raise RuntimeError(
            "A oportunidade foi localizada, mas veio sem o campo code."
        )

    return codigo


def _formatar_data_consulta(valor):
    if hasattr(valor, "strftime"):
        return valor.strftime("%Y-%m-%d")
    return str(valor)


def _normalizar_resposta(response):
    try:
        return response.json()
    except ValueError:
        return response.text


def _imprimir_resultado(resultado):
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    # TESTE GET PUBLICO: consulta a configuracao sem criar oportunidade.
    resultado_consulta = consultar_integracao_unidade()
    _imprimir_resultado(resultado_consulta)

    # TESTE POST REAL: descomente conscientemente para criar no CRM.
    # resultado_envio = criar_oportunidade_teste(
    #     confirmar_envio_real=True,
    #     nome_contato="Teste Chatbot - Nao contatar",
    #     email="",
    #     telefone="",
    # )
    # _imprimir_resultado(resultado_envio)

    # TESTE GET AUTENTICADO: informe o titulo exato retornado pelo POST.
    # codigo_oportunidade = consultar_codigo_oportunidade(
    #     titulo="[TESTE CHATBOT AAAAMMDD-HHMMSS] Teste Chatbot - Nao contatar",
    #     codigo_funil=123,
    #     email_api="usuario-api@exemplo.com",
    #     senha_api="informe-somente-no-teste-local",
    # )
    # print(f"codigo_oportunidade={codigo_oportunidade}")
