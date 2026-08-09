# ENTRADA NA ETAPA 11

MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11 = (
    "Antes de continuarmos o agendamento, vamos realizar uma pequena triagem "
    "cognitiva com 6 perguntas objetivas de seleção única, ok?"
)


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM COM MÍDIA

MENSAGEM_MIDIA_ETAPA11 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11}"
)


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM COM PERGUNTA FINANCEIRA

MENSAGEM_FINANCEIRO_ETAPA11 = (
    "Olha, demais informações, como valores de investimento, são "
    "apresentadas no atendimento presencial após a aula *gratuita*.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11}"
)


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM FORA DO CONTEXTO

MENSAGEM_CONTEXTO_INVALIDO_ETAPA11 = (
    "Desculpe, não entendi.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11}"
)


BOTAO_ETAPA11_INICIAR_TRIAGEM = "Iniciar triagem"


def montar_mensagem_triagem_cognitiva_etapa11():
    return MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11


def montar_mensagem_midia_etapa11():
    return MENSAGEM_MIDIA_ETAPA11


def montar_mensagem_financeiro_etapa11():
    return MENSAGEM_FINANCEIRO_ETAPA11


def montar_mensagem_contexto_invalido_etapa11():
    return MENSAGEM_CONTEXTO_INVALIDO_ETAPA11


def montar_botoes_etapa11():
    return (BOTAO_ETAPA11_INICIAR_TRIAGEM,)
