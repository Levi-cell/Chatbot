# ETAPA 12 - TESTE COGNITIVO, PERGUNTA 1

CABECALHO_ETAPA12 = "Pergunta 1"

MENSAGEM_CLIENTE_ETAPA12 = (
    "Com que frequência você esquece de acontecimentos recentes, "
    "como o que fez no final de semana?"
)

MENSAGEM_DEPENDENTE_ETAPA12 = (
    "Com que frequência {nome} esquece de acontecimentos recentes, "
    "como o que fez no final de semana?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA12 = (
    "Não consegui entender sua resposta, mas me diz:\n\n"
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
