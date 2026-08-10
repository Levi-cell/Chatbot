from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_reforco_escolar,
)


### ENTRADA NA ETAPA 6 - CLIENTE

MENSAGEM_IDADE_ETAPA6 = (
    "Certo, agora me fala, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6():
    return MENSAGEM_IDADE_ETAPA6


### ENTRADA NA ETAPA 6 - DEPENDENTE

MENSAGEM_IDADE_DEPENDENTE_ETAPA6 = (
    "Certo, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM MÍDIA

MENSAGEM_IDADE_ETAPA6_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6_midia():
    return MENSAGEM_IDADE_ETAPA6_MIDIA


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MÍDIA

MENSAGEM_IDADE_DEPENDENTE_ETAPA6_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6_midia(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6_MIDIA.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_ETAPA6_FINANCEIRO = (
    "Olha, demais informações como valores de investimento são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6_financeiro():
    return MENSAGEM_IDADE_ETAPA6_FINANCEIRO


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_DEPENDENTE_ETAPA6_FINANCEIRO = (
    "Olha, demais informações como valores de investimento são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6_financeiro(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6_FINANCEIRO.format(nome=nome)


### CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR

MENSAGEM_RETOMADA_IDADE_ETAPA6 = "Me diz, qual é a sua idade?"
MENSAGEM_RETOMADA_IDADE_DEPENDENTE_ETAPA6 = (
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_etapa6_reforco_escolar():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_IDADE_ETAPA6,
    )


def montar_mensagem_idade_dependente_etapa6_reforco_escolar(nome):
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_IDADE_DEPENDENTE_ETAPA6.format(nome=nome),
    )


### CLIENTE RESPONDE À IDADE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA6 = (
    "Não consegui entender a sua idade. Digite apenas o número, exemplo: 25.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_contexto_idade_invalida_etapa6():
    return MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA6


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA6 = (
    "Não consegui entender a idade de {nome}. Digite apenas o número, "
    "exemplo: 10.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_contexto_idade_dependente_invalida_etapa6(nome):
    return MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA6.format(
        nome=nome,
    )


### CLIENTE COM MENOS DE 18 ANOS

MENSAGEM_CLIENTE_MENOR_18_ETAPA6 = (
    "Como você tem menos de 18 anos, este atendimento precisa ser realizado "
    "por um adulto responsável.\n\n"
    "Peça a um adulto para retornar nosso atendimento.\n"
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_cliente_menor_18_etapa6():
    return MENSAGEM_CLIENTE_MENOR_18_ETAPA6


### DEPENDENTE ABAIXO DA IDADE MINIMA DA UNIDADE

MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6 = (
    "No momento, esta unidade do Supera realiza treinamentos com crianças a "
    "partir de {idade_minima} anos. Quando {nome} completar {idade_minima} "
    "anos, você poderá entrar em contato "
    "novamente.\n\n"
    "Um abraço e até logo! 👋☺️"

)


def montar_mensagem_dependente_menor_5_etapa6(
    nome,
    idade_minima=5,
):
    return MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6.format(
        nome=nome,
        idade_minima=idade_minima,
    )


### CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS

MENSAGEM_IDADE_ACIMA_99_ETAPA6 = (
    "Entendi. Olha, para idades muito avançadas, é melhor falar com nossa "
    "consultora especializada. Vou te passar o contato dela para continuar "
    "o atendimento, tudo bem?\n\n"
    "Basta clicar no botão abaixo."
)

BOTAO_FALAR_COM_CONSULTORA_ETAPA6 = "Falar com Consultora"


def montar_mensagem_idade_acima_99_etapa6():
    return MENSAGEM_IDADE_ACIMA_99_ETAPA6


def montar_botao_idade_acima_99_etapa6():
    return BOTAO_FALAR_COM_CONSULTORA_ETAPA6
