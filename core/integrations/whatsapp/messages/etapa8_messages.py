# ENTRADA NA ETAPA 8

MENSAGEM_PERGUNTA_EMAIL_ETAPA8 = "Qual o seu melhor email?"


def montar_mensagem_email_etapa8():
    return MENSAGEM_PERGUNTA_EMAIL_ETAPA8


# CLIENTE RESPONDE AO EMAIL COM MIDIA

MENSAGEM_PERGUNTA_EMAIL_ETAPA8_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Me diz, qual o seu melhor email?"
)


def montar_mensagem_email_etapa8_midia():
    return MENSAGEM_PERGUNTA_EMAIL_ETAPA8_MIDIA


# CLIENTE RESPONDE AO EMAIL COM PERGUNTA FINANCEIRA

MENSAGEM_PERGUNTA_EMAIL_ETAPA8_FINANCEIRO = (
    "Olha, demais informações, como valores, são apresentadas no atendimento "
    "presencial após sua aula *gratuita*.\n\n"
    "Me diz, qual o seu melhor email?"
)


def montar_mensagem_email_etapa8_financeiro():
    return MENSAGEM_PERGUNTA_EMAIL_ETAPA8_FINANCEIRO


# CLIENTE RESPONDE COM EMAIL FORA DO CONTEXTO

MENSAGEM_CONTEXTO_EMAIL_INVALIDO_ETAPA8 = (
    "Não consegui identificar um email válido.\n\n"
    "Me diz, qual o seu melhor email?\n"
    "Digite o email completo, por exemplo: nome@gmail.com"
)


def montar_mensagem_contexto_email_invalido_etapa8():
    return MENSAGEM_CONTEXTO_EMAIL_INVALIDO_ETAPA8
