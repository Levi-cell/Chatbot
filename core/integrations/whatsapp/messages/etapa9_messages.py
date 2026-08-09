# ENTRADA NA ETAPA 9 - RETORNO DO PROPRIO CLIENTE

MENSAGEM_RETORNO_CLIENTE_ETAPA9 = (
    "Que bom ver você aqui novamente, {nome_cliente}! "
    "Vamos dar continuidade ao seu agendamento? ☺️"
)


def montar_mensagem_retorno_cliente_etapa9(nome_cliente):
    return MENSAGEM_RETORNO_CLIENTE_ETAPA9.format(
        nome_cliente=nome_cliente,
    )


# ENTRADA NA ETAPA 9 - RETORNO PARA AGENDAMENTO DO DEPENDENTE

MENSAGEM_RETORNO_DEPENDENTE_ETAPA9 = (
    "Que bom ver você aqui novamente, {nome_cliente}! "
    "Vamos dar continuidade ao agendamento de {nome_dependente}? ☺️"
)


def montar_mensagem_retorno_dependente_etapa9(
    nome_cliente,
    nome_dependente,
):
    return MENSAGEM_RETORNO_DEPENDENTE_ETAPA9.format(
        nome_cliente=nome_cliente,
        nome_dependente=nome_dependente,
    )


# CLIENTE RESPONDE AO RETORNO PROPRIO COM MIDIA

MENSAGEM_RETORNO_CLIENTE_MIDIA_ETAPA9 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Vamos dar continuidade ao seu agendamento?"
)


def montar_mensagem_retorno_cliente_midia_etapa9():
    return MENSAGEM_RETORNO_CLIENTE_MIDIA_ETAPA9


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE COM MIDIA

MENSAGEM_RETORNO_DEPENDENTE_MIDIA_ETAPA9 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Vamos dar continuidade ao agendamento de {nome}?"
)


def montar_mensagem_retorno_dependente_midia_etapa9(nome):
    return MENSAGEM_RETORNO_DEPENDENTE_MIDIA_ETAPA9.format(nome=nome)


# CLIENTE RESPONDE AO RETORNO PROPRIO COM PERGUNTA FINANCEIRA

MENSAGEM_RETORNO_CLIENTE_FINANCEIRO_ETAPA9 = (
    "Olha, demais informações, como valores de investimento, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Vamos dar continuidade ao seu agendamento?"
)


def montar_mensagem_retorno_cliente_financeiro_etapa9():
    return MENSAGEM_RETORNO_CLIENTE_FINANCEIRO_ETAPA9


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_RETORNO_DEPENDENTE_FINANCEIRO_ETAPA9 = (
    "Olha, demais informações, como valores de investimento, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Vamos dar continuidade ao agendamento de {nome}?"
)


def montar_mensagem_retorno_dependente_financeiro_etapa9(nome):
    return MENSAGEM_RETORNO_DEPENDENTE_FINANCEIRO_ETAPA9.format(nome=nome)


# CLIENTE RESPONDE AO RETORNO PROPRIO FORA DO CONTEXTO

MENSAGEM_RETORNO_CLIENTE_CONTEXTO_INVALIDO_ETAPA9 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Vamos dar continuidade ao seu agendamento?"
)


def montar_mensagem_retorno_cliente_contexto_invalido_etapa9():
    return MENSAGEM_RETORNO_CLIENTE_CONTEXTO_INVALIDO_ETAPA9


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE FORA DO CONTEXTO

MENSAGEM_RETORNO_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA9 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Vamos dar continuidade ao agendamento de {nome}?"
)


def montar_mensagem_retorno_dependente_contexto_invalido_etapa9(nome):
    return MENSAGEM_RETORNO_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA9.format(
        nome=nome,
    )


# BOTOES DA ETAPA 9

BOTAO_ETAPA9_QUERO_AGENDAR = "Quero agendar"
BOTAO_ETAPA9_TALVEZ_MAIS_TARDE = "Talvez mais tarde"

BOTOES_ETAPA9 = (
    BOTAO_ETAPA9_QUERO_AGENDAR,
    BOTAO_ETAPA9_TALVEZ_MAIS_TARDE,
)


def montar_botoes_etapa9():
    return BOTOES_ETAPA9
