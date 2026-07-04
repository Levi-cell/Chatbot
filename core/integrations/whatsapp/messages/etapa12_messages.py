# ETAPA 12 - TESTE COGNITIVO, PERGUNTA 3

CABECALHO_ETAPA12 = "Teste Cognitivo - Pergunta 3"

MENSAGEM_CLIENTE_ETAPA12 = (
    "Com que frequência você esquece nomes de pessoas conhecidas "
    "ou familiares?"
)

MENSAGEM_DEPENDENTE_ETAPA12 = (
    "Com que frequência {nome} esquece nomes de pessoas conhecidas "
    "ou familiares?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA12 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA12
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA12 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA12
)


def montar_cabecalho_etapa12():
    return CABECALHO_ETAPA12


def montar_mensagem_cliente_etapa12():
    return MENSAGEM_CLIENTE_ETAPA12


def montar_mensagem_dependente_etapa12(nome):
    return MENSAGEM_DEPENDENTE_ETAPA12.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa12():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA12


def montar_mensagem_dependente_contexto_invalido_etapa12(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA12.format(nome=nome)
