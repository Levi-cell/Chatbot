# ETAPA 11 - TESTE COGNITIVO, PERGUNTA 2

CABECALHO_ETAPA11 = "Pergunta 2"

MENSAGEM_CLIENTE_ETAPA11 = (
    "Com que frequência você esquece o que foi fazer ou procurar "
    "em outro lugar?"
)

MENSAGEM_DEPENDENTE_ETAPA11 = (
    "Com que frequência {nome} esquece o que foi fazer ou procurar "
    "em outro lugar?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA11 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA11
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA11 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA11
)


def montar_cabecalho_etapa11():
    return CABECALHO_ETAPA11


def montar_mensagem_cliente_etapa11():
    return MENSAGEM_CLIENTE_ETAPA11


def montar_mensagem_dependente_etapa11(nome):
    return MENSAGEM_DEPENDENTE_ETAPA11.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa11():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA11


def montar_mensagem_dependente_contexto_invalido_etapa11(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA11.format(nome=nome)
