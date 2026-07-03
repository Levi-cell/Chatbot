# ENTRADA NA ETAPA 5 - CLIENTE

MENSAGEM_OFERTA_CLIENTE_ETAPA5 = (
    "Que maravilha, {nome}! 🥰\n\n"
    "Gostaria de te oferecer uma aula experimental + avaliação cognitiva "
    "*gratuita*. Elas servem para que possamos saber como anda a saúde do "
    "seu cérebro e para que você possa nos conhecer. 😄\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_cliente_etapa5(nome):
    return MENSAGEM_OFERTA_CLIENTE_ETAPA5.format(nome=nome)


# ENTRADA NA ETAPA 5 - DEPENDENTE

MENSAGEM_OFERTA_DEPENDENTE_ETAPA5 = (
    "Que maravilha! 🥰\n\n"
    "Gostaria de oferecer uma aula experimental + avaliação cognitiva "
    "*gratuita* para {nome}. Elas servem para que possamos saber como anda "
    "a saúde do cérebro de {nome} e para que vocês possam nos conhecer. 😄\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_dependente_etapa5(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_ETAPA5.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM MÍDIA

MENSAGEM_OFERTA_CLIENTE_MIDIA_ETAPA5 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá, quero te oferecer uma aula experimental + avaliação "
    "cognitiva *gratuita*. Elas servem para que possamos saber como anda a "
    "saúde do seu cérebro e para que você possa nos conhecer. 😄\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_cliente_midia_etapa5():
    return MENSAGEM_OFERTA_CLIENTE_MIDIA_ETAPA5


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM MÍDIA

MENSAGEM_OFERTA_DEPENDENTE_MIDIA_ETAPA5 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá, quero oferecer uma aula experimental + avaliação "
    "cognitiva *gratuita* para {nome}. Elas servem para que possamos saber "
    "como anda a saúde do cérebro de {nome} e para que vocês possam nos "
    "conhecer. 😄\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_dependente_midia_etapa5(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_MIDIA_ETAPA5.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM PERGUNTA FINANCEIRA

MENSAGEM_OFERTA_CLIENTE_FINANCEIRO_ETAPA5 = (
    "Olha, demais informações, como valores, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Mas bora lá, quero te oferecer uma aula experimental + avaliação "
    "cognitiva *gratuita*. Elas servem para que possamos saber como anda a "
    "saúde do seu cérebro e para que você possa nos conhecer. 😄\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_cliente_financeiro_etapa5():
    return MENSAGEM_OFERTA_CLIENTE_FINANCEIRO_ETAPA5


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_OFERTA_DEPENDENTE_FINANCEIRO_ETAPA5 = (
    "Olha, demais informações, como valores, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Mas bora lá, quero oferecer uma aula experimental + avaliação "
    "cognitiva *gratuita* para {nome}. Elas servem para que possamos saber "
    "como anda a saúde do cérebro de {nome} e para que vocês possam nos "
    "conhecer. 😄\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_dependente_financeiro_etapa5(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_FINANCEIRO_ETAPA5.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_OFERTA_CLIENTE_CONTEXTO_INVALIDO_ETAPA5 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Mas bora lá, quero te oferecer uma aula experimental + avaliação "
    "cognitiva *gratuita*. Elas servem para que possamos saber como anda a "
    "saúde do seu cérebro e para que você possa nos conhecer. 😄\n\n"
    "Selecione uma das opções abaixo."
)


def montar_mensagem_oferta_cliente_contexto_invalido_etapa5():
    return MENSAGEM_OFERTA_CLIENTE_CONTEXTO_INVALIDO_ETAPA5


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_OFERTA_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA5 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Mas bora lá, quero oferecer uma aula experimental + avaliação "
    "cognitiva *gratuita* para {nome}. Elas servem para que possamos saber "
    "como anda a saúde do cérebro de {nome} e para que vocês possam nos "
    "conhecer. 😄\n\n"
    "Selecione uma das opções abaixo."
)


def montar_mensagem_oferta_dependente_contexto_invalido_etapa5(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA5.format(
        nome=nome,
    )


# BOTOES DA ETAPA 5

BOTAO_ETAPA5_QUERO_AGENDAR = "Quero agendar"
BOTAO_ETAPA5_TALVEZ_MAIS_TARDE = "Talvez mais tarde"

BOTOES_ETAPA5 = (
    BOTAO_ETAPA5_QUERO_AGENDAR,
    BOTAO_ETAPA5_TALVEZ_MAIS_TARDE,
)


def montar_botoes_etapa5():
    return BOTOES_ETAPA5
