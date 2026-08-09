# ETAPA 16 - TESTE COGNITIVO, PERGUNTA 5

CABECALHO_ETAPA16 = "Pergunta 5"

MENSAGEM_CLIENTE_ETAPA16 = (
    "Com que frequência você perde a atenção/foco na atividade "
    "que está fazendo?"
)

MENSAGEM_DEPENDENTE_ETAPA16 = (
    "Com que frequência {nome} perde a atenção/foco na atividade "
    "que está fazendo?"
)

MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA16 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_CLIENTE_ETAPA16
)

MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA16 = (
    "Não consegui entender sua resposta.\n\n"
    + MENSAGEM_DEPENDENTE_ETAPA16
)


def montar_cabecalho_etapa16():
    return CABECALHO_ETAPA16


def montar_mensagem_cliente_etapa16():
    return MENSAGEM_CLIENTE_ETAPA16


def montar_mensagem_dependente_etapa16(nome):
    return MENSAGEM_DEPENDENTE_ETAPA16.format(nome=nome)


def montar_mensagem_cliente_contexto_invalido_etapa16():
    return MENSAGEM_CLIENTE_CONTEXTO_INVALIDO_ETAPA16


def montar_mensagem_dependente_contexto_invalido_etapa16(nome):
    return MENSAGEM_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA16.format(nome=nome)
