MENSAGEM_MIDIA_INICIO = (
    "Ola! Vi que voce iniciou o atendimento com uma midia.\n\n"
    "Por enquanto eu so consigo continuar por mensagem de texto ou botoes. "
    "Envie uma mensagem de texto para começarmos."
)

MENSAGEM_MIDIA_ETAPA = (
    "Recebi uma midia, mas nesta etapa eu preciso que voce responda por texto "
    "ou use os botoes disponíveis.\n\n"
    "Envie uma mensagem de texto para continuarmos."
)

TITULO_BOTAO_CONTINUAR = "Continuar"
CALLBACK_RETORNAR_ATENDIMENTO = "retornar_atendimento"


def montar_mensagem_tipo_nao_suportado(conversa_nova):
    if conversa_nova:
        return MENSAGEM_MIDIA_INICIO

    return MENSAGEM_MIDIA_ETAPA
