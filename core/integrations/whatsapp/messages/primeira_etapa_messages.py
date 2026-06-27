### INICIO NORMAL

MENSAGEM_ETAPA_1 = (
    "{saudacao}! Seja bem vindo (a), sou a Su, atendente virtual do Supera! ☺️\n"
    "Como você se chama?"
)

def montar_mensagem_etapa_1(saudacao):
    return MENSAGEM_ETAPA_1.format(saudacao=saudacao)





### INICIO PORÉM CLIENTE INICIA COM MIDA

MENSAGEM_MIDIA_INICIO = (
    "{saudacao}! Seja bem vindo (a), sou a Su, atendente virtual do Supera! ☺️\n"
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_midia_inicio(saudacao):
    return MENSAGEM_MIDIA_INICIO.format(saudacao=saudacao)





### INICIO PORÈM CLIENTE INICIA COM PERGUNTA FINANCEIRA

MENSAGEM_FINANCEIRO_INICIO = (
    "{saudacao}! Seja bem vindo (a), sou a Su, atendente virtual do Supera! ☺️\n"
    "Olha demais informações como valores são apresentadas no atendimento "
    "presencial após sua aula gratuita.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_financeiro_inicio(saudacao):
    return MENSAGEM_FINANCEIRO_INICIO.format(saudacao=saudacao)




### CLIENTE RESPONDE AO NOME COM MIDIA

MENSAGEM_MIDIA_ETAPA_1 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_midia_etapa_1():
    return MENSAGEM_MIDIA_ETAPA_1



### CLIENTE RESPONDE AO NOME COM FINANCEIRO

MENSAGEM_FINANCEIRO_ETAPA_1 = (
    "Olha demais informações como valores são apresentadas no atendimento "
    "presencial após sua aula gratuita.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_financeiro_etapa_1():
    return MENSAGEM_FINANCEIRO_ETAPA_1


### CLIENTE RESPONDE AO NOME COM CONTEXTO INVALIDO

MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1 = (
    "Não consegui entender o seu nome. Me fala só seu primeiro nome, "
    "exemplo: Pedro"
)

def montar_mensagem_contexto_nome_invalido_etapa_1():
    return MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1
