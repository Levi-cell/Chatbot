MENSAGEM_MIDIA_INICIO = (
    "{saudacao}! Seja bem vindo (a), sou a Su, atendente virtual do Supera! ☺️\n"
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_MIDIA_ETAPA_1 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_MIDIA_ETAPA_GENERICA = (
    "Recebi uma mídia, mas nesta etapa eu preciso que você responda por texto "
    "ou use os botões disponíveis.\n\n"
    "Envie uma mensagem de texto para continuarmos."
)

MENSAGEM_FINANCEIRO_INICIO = (
    "{saudacao}! Seja bem vindo (a), sou a Su, atendente virtual do Supera! ☺️\n"
    "Olha demais informações como valores são apresentados no atendimento "
    "presencial após sua aula gratuita.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_FINANCEIRO_ETAPA_1 = (
    "Olha demais informações como valores são apresentados no atendimento "
    "presencial após sua aula gratuita.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_FINANCEIRO_ETAPA_GENERICA = (
    "Demais informações como valores são apresentados no atendimento presencial "
    "após sua aula gratuita.\n"
    "Vamos continuar seu atendimento."
)

MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1 = (
    "Olha sua mensagem parece estar fora do contexto e também não aceitamos "
    "nomes e apelidos pejorativos.\n"
    "Me diz, qual o seu nome?"
)

MENSAGEM_CONTEXTO_GENERICA = (
    "Olha sua mensagem parece estar fora do contexto desta etapa.\n"
    "Vamos continuar seu atendimento."
)


def montar_mensagem_tipo_nao_suportado(id_etapa, conversa_nova, saudacao=None):
    if conversa_nova:
        return MENSAGEM_MIDIA_INICIO.format(saudacao=saudacao)

    if id_etapa == 1:
        return MENSAGEM_MIDIA_ETAPA_1

    return MENSAGEM_MIDIA_ETAPA_GENERICA


def montar_mensagem_financeira(id_etapa, conversa_nova, saudacao=None):
    if conversa_nova:
        return MENSAGEM_FINANCEIRO_INICIO.format(saudacao=saudacao)

    if id_etapa == 1:
        return MENSAGEM_FINANCEIRO_ETAPA_1

    return MENSAGEM_FINANCEIRO_ETAPA_GENERICA


def montar_mensagem_contexto_nome_invalido(id_etapa):
    if id_etapa == 1:
        return MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1

    return MENSAGEM_CONTEXTO_GENERICA
