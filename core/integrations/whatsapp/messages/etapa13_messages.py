# ETAPA 13 - TESTE COGNITIVO, PERGUNTA 4

CABECALHO_ETAPA13 = "Pergunta 4"

MENSAGEM_CLIENTE_ETAPA13 = (
    "Com que frequência você esquece de levar suas coisas com você?"
)

MENSAGEM_DEPENDENTE_ETAPA13 = (
    "Com que frequência {nome} esquece de levar as próprias coisas?"
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
