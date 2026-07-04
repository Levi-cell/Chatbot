# ETAPA 15 - TESTE COGNITIVO, PERGUNTA 6

CABECALHO_ETAPA15 = "Teste Cognitivo - Pergunta 6"

MENSAGEM_CLIENTE_ETAPA15 = (
    "Com que frequência você esquece o que aconteceu em um filme, "
    "desenho, série ou novela?"
)

MENSAGEM_DEPENDENTE_ETAPA15 = (
    "Com que frequência {nome} esquece o que aconteceu em um filme, "
    "desenho, série ou novela?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA15 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA15
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA15 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA15
)


def montar_cabecalho_etapa15():
    return CABECALHO_ETAPA15


def montar_mensagem_cliente_etapa15():
    return MENSAGEM_CLIENTE_ETAPA15


def montar_mensagem_dependente_etapa15(nome):
    return MENSAGEM_DEPENDENTE_ETAPA15.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa15():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA15


def montar_mensagem_dependente_contexto_invalido_etapa15(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA15.format(nome=nome)
