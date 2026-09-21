from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_financeiro,
    montar_mensagem_tratamento_reforco_escolar,
)


# ETAPA 20 - DECISAO SOBRE O COMENTARIO DA PESQUISA DE SATISFACAO

TEXTO_BOTAO_COMENTAR_ETAPA20 = "Sim, quero comentar"
TEXTO_BOTAO_SEM_COMENTARIO_ETAPA20 = "Prefiro não comentar"

MENSAGEM_ETAPA20 = (
    "Você tem algum comentário ou sugestão para melhorar nosso atendimento?\n"
    "Seu feedback é muito importante para nós! 😊"
)

MENSAGEM_MIDIA_ETAPA20 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_ETAPA20}"
)

MENSAGEM_FINANCEIRO_ETAPA20 = montar_mensagem_tratamento_financeiro(
    MENSAGEM_ETAPA20,
)

MENSAGEM_CONTEXTO_INVALIDO_ETAPA20 = (
    "Desculpe, não entendi.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_ETAPA20}"
)


def montar_mensagem_etapa20():
    return MENSAGEM_ETAPA20


def montar_mensagem_midia_etapa20():
    return MENSAGEM_MIDIA_ETAPA20


def montar_mensagem_financeiro_etapa20():
    return MENSAGEM_FINANCEIRO_ETAPA20


def montar_mensagem_reforco_escolar_etapa20():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_ETAPA20,
    )


def montar_mensagem_contexto_invalido_etapa20():
    return MENSAGEM_CONTEXTO_INVALIDO_ETAPA20


def montar_botoes_etapa20():
    return [
        TEXTO_BOTAO_COMENTAR_ETAPA20,
        TEXTO_BOTAO_SEM_COMENTARIO_ETAPA20,
    ]
