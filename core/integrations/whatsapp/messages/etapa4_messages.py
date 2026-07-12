### ENTRADA NA ETAPA 4 - CLIENTE

MENSAGEM_IDADE_ETAPA4 = (
    "Certo, agora me fala, qual é a sua idade?"
)


def montar_mensagem_idade_etapa4():
    return MENSAGEM_IDADE_ETAPA4


### ENTRADA NA ETAPA 4 - DEPENDENTE

MENSAGEM_IDADE_DEPENDENTE_ETAPA4 = (
    "Certo, agora me fala, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa4(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA4.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM MÍDIA

MENSAGEM_IDADE_ETAPA4_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa4_midia():
    return MENSAGEM_IDADE_ETAPA4_MIDIA


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MÍDIA

MENSAGEM_IDADE_DEPENDENTE_ETAPA4_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa4_midia(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA4_MIDIA.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_ETAPA4_FINANCEIRO = (
    "Olha, demais informações como valores são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa4_financeiro():
    return MENSAGEM_IDADE_ETAPA4_FINANCEIRO


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_DEPENDENTE_ETAPA4_FINANCEIRO = (
    "Olha, demais informações como valores são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa4_financeiro(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA4_FINANCEIRO.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA4 = (
    "Não consegui entender a sua idade. Digite apenas o número, exemplo: 25.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_contexto_idade_invalida_etapa4():
    return MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA4


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA4 = (
    "Não consegui entender a idade de {nome}. Digite apenas o número, "
    "exemplo: 10.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_contexto_idade_dependente_invalida_etapa4(nome):
    return MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA4.format(
        nome=nome,
    )


### CLIENTE COM MENOS DE 18 ANOS

MENSAGEM_CLIENTE_MENOR_18_ETAPA4 = (
    "Como você tem menos de 18 anos, este atendimento precisa ser realizado "
    "por um adulto responsável.\n\n"
    "Peça a um adulto para retornar nosso atendimento.\n"
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_cliente_menor_18_etapa4():
    return MENSAGEM_CLIENTE_MENOR_18_ETAPA4


### DEPENDENTE ABAIXO DA IDADE MINIMA DA UNIDADE

MENSAGEM_DEPENDENTE_MENOR_5_ETAPA4 = (
    "No momento, esta unidade do Supera realiza treinamentos com crianças a "
    "partir de {idade_minima} anos. Quando {nome} completar {idade_minima} "
    "anos, você poderá entrar em contato "
    "novamente.\n\n"
    "Um abraço e até logo! 👋☺️"

)


def montar_mensagem_dependente_menor_5_etapa4(
    nome,
    idade_minima=5,
):
    return MENSAGEM_DEPENDENTE_MENOR_5_ETAPA4.format(
        nome=nome,
        idade_minima=idade_minima,
    )


### CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS

MENSAGEM_IDADE_ACIMA_99_ETAPA4 = (
    "Entendi. Olha, para idades muito avançadas, é melhor falar com nossa "
    "consultora especializada. Vou te passar o contato dela para continuar "
    "o atendimento, tudo bem?\n\n"
    "Basta clicar no botão abaixo."
)

BOTAO_FALAR_COM_CONSULTORA_ETAPA4 = "Falar com Consultora"


def montar_mensagem_idade_acima_99_etapa4():
    return MENSAGEM_IDADE_ACIMA_99_ETAPA4


def montar_botao_idade_acima_99_etapa4():
    return BOTAO_FALAR_COM_CONSULTORA_ETAPA4
