from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_financeiro,
    montar_mensagem_tratamento_reforco_escolar,
)


# ENTRADA NA ETAPA 10

MENSAGEM_PERGUNTA_EMAIL_ETAPA10 = "Certo, para fazer *sua reserva*, me diz, qual é o seu melhor email? ☺️"


def montar_mensagem_email_etapa10():
    return MENSAGEM_PERGUNTA_EMAIL_ETAPA10


# CLIENTE RESPONDE AO EMAIL COM MIDIA

MENSAGEM_PERGUNTA_EMAIL_ETAPA10_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Me diz, qual o seu melhor email?"
)


def montar_mensagem_email_etapa10_midia():
    return MENSAGEM_PERGUNTA_EMAIL_ETAPA10_MIDIA


# CLIENTE RESPONDE AO EMAIL COM PERGUNTA FINANCEIRA

MENSAGEM_PERGUNTA_EMAIL_ETAPA10_FINANCEIRO = montar_mensagem_tratamento_financeiro(
    "Me diz, qual o seu melhor email?"
)


def montar_mensagem_email_etapa10_financeiro():
    return MENSAGEM_PERGUNTA_EMAIL_ETAPA10_FINANCEIRO


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR

MENSAGEM_RETOMADA_EMAIL_ETAPA10 = "Me diz, qual o seu melhor email?"


def montar_mensagem_email_etapa10_reforco_escolar():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_EMAIL_ETAPA10,
    )


# CLIENTE RESPONDE COM EMAIL FORA DO CONTEXTO

MENSAGEM_CONTEXTO_EMAIL_INVALIDO_ETAPA10 = (
    "Não consegui identificar um email válido.\n\n"
    "Me diz, qual o seu melhor email?\n"
    "Digite o email completo, por exemplo: nome@gmail.com"
)


def montar_mensagem_contexto_email_invalido_etapa10():
    return MENSAGEM_CONTEXTO_EMAIL_INVALIDO_ETAPA10
