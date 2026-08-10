# ETAPA 21 - COMENTARIO DA PESQUISA DE SATISFACAO

MENSAGEM_SOLICITACAO_COMENTARIO_ETAPA21 = (
    "Deixa aqui a baixo seu comentário para melhorar nosso atendimento."
)

MENSAGEM_ETAPA21 = (
    "Perfeito! 😊\n"
    f"{MENSAGEM_SOLICITACAO_COMENTARIO_ETAPA21}"
)

MENSAGEM_MIDIA_ETAPA21 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_SOLICITACAO_COMENTARIO_ETAPA21}"
)

MENSAGEM_CONTEXTO_INVALIDO_ETAPA21 = (
    "Desculpe, não consegui entender seu comentário.\n\n"
    "Mas bora lá:\n\n"
    f"{MENSAGEM_SOLICITACAO_COMENTARIO_ETAPA21}"
)


def montar_mensagem_etapa21():
    return MENSAGEM_ETAPA21


def montar_mensagem_midia_etapa21():
    return MENSAGEM_MIDIA_ETAPA21


def montar_mensagem_contexto_invalido_etapa21():
    return MENSAGEM_CONTEXTO_INVALIDO_ETAPA21
