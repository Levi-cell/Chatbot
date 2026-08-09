### MENSAGENS EXCLUSIVA PARA DEPENDENTE

### MENSAGEM DE INICIO PERGUNTANDO O NOME

MENSAGEM_ETAPA5 = (
    "Certo, agora me diz, qual o primeiro nome da pessoa que receberá o atendimento?"
)


def montar_mensagem_etapa5():
    return MENSAGEM_ETAPA5


### CLIENTE RESPONDE AO NOME DA PESSOA COM MIDIA

MENSAGEM_MIDIA_ETAPA5 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o primeiro nome da pessoa?"
)


def montar_mensagem_midia_etapa5():
    return MENSAGEM_MIDIA_ETAPA5


### CLIENTE RESPONDE AO NOME DA PESSOA COM FINANCEIRO

MENSAGEM_FINANCEIRO_ETAPA5 = (
    "Olha demais informações como valores de investimento são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Fala para mim, qual o primeiro nome da pessoa?"
)


def montar_mensagem_financeiro_etapa5():
    return MENSAGEM_FINANCEIRO_ETAPA5


### CLIENTE RESPONDE O NOME DA PESSOA COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA5 = (
    "Não consegui entender o nome da pessoa. Me fala só o primeiro nome dela, "
    "exemplo: Pedro"
)


def montar_mensagem_contexto_nome_invalido_etapa5():
    return MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA5
