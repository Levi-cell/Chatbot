# ETAPA 10 - TESTE COGNITIVO, PERGUNTA 1

CABECALHO_ETAPA10 = "Pergunta 1"

MENSAGEM_CLIENTE_ETAPA10 = (
    "Com que frequência você esquece de acontecimentos recentes, "
    "como o que fez no final de semana?"
)

MENSAGEM_DEPENDENTE_ETAPA10 = (
    "Com que frequência {nome} esquece de acontecimentos recentes, "
    "como o que fez no final de semana?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA10 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA10
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA10 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA10
)


def montar_cabecalho_etapa10():
    return CABECALHO_ETAPA10


def montar_mensagem_cliente_etapa10():
    return MENSAGEM_CLIENTE_ETAPA10


def montar_mensagem_dependente_etapa10(nome):
    return MENSAGEM_DEPENDENTE_ETAPA10.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa10():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA10


def montar_mensagem_dependente_contexto_invalido_etapa10(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA10.format(nome=nome)
