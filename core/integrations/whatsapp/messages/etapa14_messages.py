# ETAPA 14 - TESTE COGNITIVO, PERGUNTA 4

CABECALHO_ETAPA14 = "Pergunta 4"

MENSAGEM_CLIENTE_ETAPA14 = (
    "Com que frequência você esquece de levar suas coisas com você?"
)

MENSAGEM_DEPENDENTE_ETAPA14 = (
    "Com que frequência {nome} esquece de levar as próprias coisas?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA14 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA14
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA14 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA14
)


def montar_cabecalho_etapa14():
    return CABECALHO_ETAPA14


def montar_mensagem_cliente_etapa14():
    return MENSAGEM_CLIENTE_ETAPA14


def montar_mensagem_dependente_etapa14(nome):
    return MENSAGEM_DEPENDENTE_ETAPA14.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa14():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA14


def montar_mensagem_dependente_contexto_invalido_etapa14(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA14.format(nome=nome)
