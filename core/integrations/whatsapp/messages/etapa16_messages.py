# ETAPA 16 - TESTE COGNITIVO, PERGUNTA 6

CABECALHO_ETAPA16 = "Pergunta 6"

MENSAGEM_CLIENTE_ETAPA16 = (
    "Com que frequência você esquece o que aconteceu em um filme, "
    "desenho, série ou novela?"
)

MENSAGEM_DEPENDENTE_ETAPA16 = (
    "Com que frequência {nome} esquece o que aconteceu em um filme, "
    "desenho, série ou novela?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA16 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA16
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA16 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA16
)


def montar_cabecalho_etapa16():
    return CABECALHO_ETAPA16


def montar_mensagem_cliente_etapa16():
    return MENSAGEM_CLIENTE_ETAPA16


def montar_mensagem_dependente_etapa16(nome):
    return MENSAGEM_DEPENDENTE_ETAPA16.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa16():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA16


def montar_mensagem_dependente_contexto_invalido_etapa16(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA16.format(nome=nome)
