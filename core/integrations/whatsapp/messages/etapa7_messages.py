# ENTRADA NA ETAPA 7 - RETORNO DO PROPRIO CLIENTE

MENSAGEM_RETORNO_CLIENTE_ETAPA7 = (
    "Bem vindo de volta! Vamos dar continuidade ao seu agendamento? ☺️"
)


def montar_mensagem_retorno_cliente_etapa7():
    return MENSAGEM_RETORNO_CLIENTE_ETAPA7


# ENTRADA NA ETAPA 7 - RETORNO PARA AGENDAMENTO DO DEPENDENTE

MENSAGEM_RETORNO_DEPENDENTE_ETAPA7 = (
    "Bem vindo de volta! Vamos dar continuidade ao agendamento de {nome}? ☺️"
)


def montar_mensagem_retorno_dependente_etapa7(nome):
    return MENSAGEM_RETORNO_DEPENDENTE_ETAPA7.format(nome=nome)


# CLIENTE RESPONDE AO RETORNO PROPRIO COM MIDIA

MENSAGEM_RETORNO_CLIENTE_MIDIA_ETAPA7 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Vamos dar continuidade ao seu agendamento?"
)


def montar_mensagem_retorno_cliente_midia_etapa7():
    return MENSAGEM_RETORNO_CLIENTE_MIDIA_ETAPA7


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE COM MIDIA

MENSAGEM_RETORNO_DEPENDENTE_MIDIA_ETAPA7 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Vamos dar continuidade ao agendamento de {nome}?"
)


def montar_mensagem_retorno_dependente_midia_etapa7(nome):
    return MENSAGEM_RETORNO_DEPENDENTE_MIDIA_ETAPA7.format(nome=nome)


# CLIENTE RESPONDE AO RETORNO PROPRIO COM PERGUNTA FINANCEIRA

MENSAGEM_RETORNO_CLIENTE_FINANCEIRO_ETAPA7 = (
    "Olha, demais informações, como valores, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Vamos dar continuidade ao seu agendamento?"
)


def montar_mensagem_retorno_cliente_financeiro_etapa7():
    return MENSAGEM_RETORNO_CLIENTE_FINANCEIRO_ETAPA7


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_RETORNO_DEPENDENTE_FINANCEIRO_ETAPA7 = (
    "Olha, demais informações, como valores, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Vamos dar continuidade ao agendamento de {nome}?"
)


def montar_mensagem_retorno_dependente_financeiro_etapa7(nome):
    return MENSAGEM_RETORNO_DEPENDENTE_FINANCEIRO_ETAPA7.format(nome=nome)


# CLIENTE RESPONDE AO RETORNO PROPRIO FORA DO CONTEXTO

MENSAGEM_RETORNO_CLIENTE_CONTEXTO_INVALIDO_ETAPA7 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Vamos dar continuidade ao seu agendamento?"
)


def montar_mensagem_retorno_cliente_contexto_invalido_etapa7():
    return MENSAGEM_RETORNO_CLIENTE_CONTEXTO_INVALIDO_ETAPA7


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE FORA DO CONTEXTO

MENSAGEM_RETORNO_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA7 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Vamos dar continuidade ao agendamento de {nome}?"
)


def montar_mensagem_retorno_dependente_contexto_invalido_etapa7(nome):
    return MENSAGEM_RETORNO_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA7.format(
        nome=nome,
    )


# BOTOES DA ETAPA 7

BOTAO_ETAPA7_QUERO_AGENDAR = "Quero agendar"
BOTAO_ETAPA7_TALVEZ_MAIS_TARDE = "Talvez mais tarde"

BOTOES_ETAPA7 = (
    BOTAO_ETAPA7_QUERO_AGENDAR,
    BOTAO_ETAPA7_TALVEZ_MAIS_TARDE,
)


def montar_botoes_etapa7():
    return BOTOES_ETAPA7
