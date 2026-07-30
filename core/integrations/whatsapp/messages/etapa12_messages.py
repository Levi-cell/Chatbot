# ETAPA 12 - TESTE COGNITIVO, PERGUNTA 2

CABECALHO_ETAPA12 = "Pergunta 2"

MENSAGEM_CLIENTE_ETAPA12 = (
    "Com que frequência você esquece o que foi fazer ou procurar "
    "em outro lugar?"
)

MENSAGEM_DEPENDENTE_ETAPA12 = (
    "Com que frequência {nome} esquece o que foi fazer ou procurar "
    "em outro lugar?"
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
