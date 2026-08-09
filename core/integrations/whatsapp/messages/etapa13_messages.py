# ETAPA 13 - TESTE COGNITIVO, PERGUNTA 2

CABECALHO_ETAPA13 = "Pergunta 2"

MENSAGEM_CLIENTE_ETAPA13 = (
    "Com que frequência você esquece o que foi fazer ou procurar "
    "em outro lugar?"
)

MENSAGEM_DEPENDENTE_ETAPA13 = (
    "Com que frequência {nome} esquece o que foi fazer ou procurar "
    "em outro lugar?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA13 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA13
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA13 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA13
)


def montar_cabecalho_etapa13():
    return CABECALHO_ETAPA13


def montar_mensagem_cliente_etapa13():
    return MENSAGEM_CLIENTE_ETAPA13


def montar_mensagem_dependente_etapa13(nome):
    return MENSAGEM_DEPENDENTE_ETAPA13.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa13():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA13


def montar_mensagem_dependente_contexto_invalido_etapa13(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA13.format(nome=nome)
