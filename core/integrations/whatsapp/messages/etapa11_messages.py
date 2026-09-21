from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_financeiro,
    montar_mensagem_tratamento_reforco_escolar,
)


# ENTRADA NA ETAPA 11

MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11 = (
    "Antes de escolher o melhor dia e horário para a *experiência Supera gratuita*, vamos "
    "fazer uma triagem com *6 perguntas rápidas* sobre quem participará. Leva "
    "poucos minutos e nos ajuda a preparar um atendimento personalizado. Podemos "
    "começar? ☺️"
)


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM COM MÍDIA

MENSAGEM_MIDIA_ETAPA11 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11}"
)


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM COM PERGUNTA FINANCEIRA

MENSAGEM_FINANCEIRO_ETAPA11 = montar_mensagem_tratamento_financeiro(
    "Vamos começar as *6 perguntas rápidas* sobre quem participará? ☺️"
)


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM FORA DO CONTEXTO

MENSAGEM_CONTEXTO_INVALIDO_ETAPA11 = (
    "Desculpe, não entendi.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11}"
)


BOTAO_ETAPA11_INICIAR_TRIAGEM = "Começar triagem"


def montar_mensagem_triagem_cognitiva_etapa11():
    return MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11


def montar_mensagem_midia_etapa11():
    return MENSAGEM_MIDIA_ETAPA11


def montar_mensagem_financeiro_etapa11():
    return MENSAGEM_FINANCEIRO_ETAPA11


def montar_mensagem_reforco_escolar_etapa11():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_TRIAGEM_COGNITIVA_ETAPA11,
    )


def montar_mensagem_contexto_invalido_etapa11():
    return MENSAGEM_CONTEXTO_INVALIDO_ETAPA11


def montar_botoes_etapa11():
    return (BOTAO_ETAPA11_INICIAR_TRIAGEM,)
