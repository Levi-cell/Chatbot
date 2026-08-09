# ETAPA 15 - TESTE COGNITIVO, PERGUNTA 4

CABECALHO_ETAPA15 = "Pergunta 4"

MENSAGEM_CLIENTE_ETAPA15 = (
    "Com que frequência você esquece de levar suas coisas com você?"
)

MENSAGEM_DEPENDENTE_ETAPA15 = (
    "Com que frequência {nome} esquece de levar as próprias coisas?"
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
