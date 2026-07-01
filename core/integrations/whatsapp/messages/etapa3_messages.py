### MENSAGENS EXCLUSIVA PARA DEPENDENTE

### MENSAGEM DE INICIO PERGUNTANDO O NOME

MENSAGEM_ETAPA3 = (
    "Qual o primeiro nome da pessoa?"
)


def montar_mensagem_etapa3():
    return MENSAGEM_ETAPA3


### CLIENTE RESPONDE AO NOME DA PESSOA COM MIDIA

MENSAGEM_MIDIA_ETAPA3 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o primeiro nome da pessoa?"
)


def montar_mensagem_midia_etapa3():
    return MENSAGEM_MIDIA_ETAPA3


### CLIENTE RESPONDE AO NOME DA PESSOA COM FINANCEIRO

MENSAGEM_FINANCEIRO_ETAPA3 = (
    "Olha demais informações como valores são apresentadas no atendimento "
    "presencial após a aula gratuita.\n"
    "Fala para mim, qual o primeiro nome da pessoa?"
)


def montar_mensagem_financeiro_etapa3():
    return MENSAGEM_FINANCEIRO_ETAPA3


### CLIENTE RESPONDE O NOME DA PESSOA COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA3 = (
    "Não consegui entender o nome da pessoa. Me fala só o primeiro nome dela, "
    "exemplo: Pedro"
)


def montar_mensagem_contexto_nome_invalido_etapa3():
    return MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA3
