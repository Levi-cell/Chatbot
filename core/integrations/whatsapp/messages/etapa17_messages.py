# ETAPA 17 - TESTE COGNITIVO, PERGUNTA 6

CABECALHO_ETAPA17 = "Pergunta 6"

MENSAGEM_CLIENTE_ETAPA17 = (
    "Com que frequência você esquece o que aconteceu em um filme, "
    "desenho, série ou novela?"
)

MENSAGEM_DEPENDENTE_ETAPA17 = (
    "Com que frequência {nome} esquece o que aconteceu em um filme, "
    "desenho, série ou novela?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA17 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA17
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA17 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA17
)


def montar_cabecalho_etapa17():
    return CABECALHO_ETAPA17


def montar_mensagem_cliente_etapa17():
    return MENSAGEM_CLIENTE_ETAPA17


def montar_mensagem_dependente_etapa17(nome):
    return MENSAGEM_DEPENDENTE_ETAPA17.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa17():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA17


def montar_mensagem_dependente_contexto_invalido_etapa17(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA17.format(nome=nome)
