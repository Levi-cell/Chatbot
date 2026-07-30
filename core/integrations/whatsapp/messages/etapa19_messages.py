# ETAPA 19 - DECISAO SOBRE O COMENTARIO DA PESQUISA DE SATISFACAO

TEXTO_BOTAO_COMENTAR_ETAPA19 = "Sim, quero comentar"
TEXTO_BOTAO_SEM_COMENTARIO_ETAPA19 = "Prefiro não comentar"

MENSAGEM_ETAPA19 = (
    "Você tem algum comentário ou sugestão para melhorar nosso atendimento?\n"
    "Seu feedback é muito importante para nós! 😊"
)

MENSAGEM_MIDIA_ETAPA19 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_ETAPA19}"
)

MENSAGEM_FINANCEIRO_ETAPA19 = (
    "Olha, demais informações, como valores, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_ETAPA19}"
)

MENSAGEM_CONTEXTO_INVALIDO_ETAPA19 = (
    "Desculpe, não entendi.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_ETAPA19}"
)


def montar_mensagem_etapa19():
    return MENSAGEM_ETAPA19


def montar_mensagem_midia_etapa19():
    return MENSAGEM_MIDIA_ETAPA19


def montar_mensagem_financeiro_etapa19():
    return MENSAGEM_FINANCEIRO_ETAPA19


def montar_mensagem_contexto_invalido_etapa19():
    return MENSAGEM_CONTEXTO_INVALIDO_ETAPA19


def montar_botoes_etapa19():
    return [
        TEXTO_BOTAO_COMENTAR_ETAPA19,
        TEXTO_BOTAO_SEM_COMENTARIO_ETAPA19,
    ]
