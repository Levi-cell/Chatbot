# ETAPA 20 - COMENTARIO DA PESQUISA DE SATISFACAO

MENSAGEM_ETAPA20 = (
    "Perfeito! 😊\n"
    "Agora escreva seu comentário ou sugestão para melhorar nosso atendimento."
)

MENSAGEM_MIDIA_ETAPA20 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_ETAPA20}"
)

MENSAGEM_CONTEXTO_INVALIDO_ETAPA20 = (
    "Desculpe, não consegui entender seu comentário.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_ETAPA20}"
)


def montar_mensagem_etapa20():
    return MENSAGEM_ETAPA20


def montar_mensagem_midia_etapa20():
    return MENSAGEM_MIDIA_ETAPA20


def montar_mensagem_contexto_invalido_etapa20():
    return MENSAGEM_CONTEXTO_INVALIDO_ETAPA20
