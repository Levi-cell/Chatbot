from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_TRATAMENTO_TEXTO,
    montar_texto_com_rodape,
)


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
    return montar_texto_com_rodape(
        MENSAGEM_IDADE_ETAPA4_MIDIA,
        RODAPE_TRATAMENTO_TEXTO,
    )


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MÍDIA

MENSAGEM_IDADE_DEPENDENTE_ETAPA4_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa4_midia(nome):
    return montar_texto_com_rodape(
        MENSAGEM_IDADE_DEPENDENTE_ETAPA4_MIDIA.format(nome=nome),
        RODAPE_TRATAMENTO_TEXTO,
    )


### CLIENTE RESPONDE À IDADE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_ETAPA4_FINANCEIRO = (
    "Olha, demais informações como valores são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa4_financeiro():
    return montar_texto_com_rodape(
        MENSAGEM_IDADE_ETAPA4_FINANCEIRO,
        RODAPE_TRATAMENTO_TEXTO,
    )


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_DEPENDENTE_ETAPA4_FINANCEIRO = (
    "Olha, demais informações como valores são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa4_financeiro(nome):
    return montar_texto_com_rodape(
        MENSAGEM_IDADE_DEPENDENTE_ETAPA4_FINANCEIRO.format(nome=nome),
        RODAPE_TRATAMENTO_TEXTO,
    )


### CLIENTE RESPONDE À IDADE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA4 = (
    "Não consegui entender a sua idade. Digite apenas o número, exemplo: 25.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_contexto_idade_invalida_etapa4():
    return montar_texto_com_rodape(
        MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA4,
        RODAPE_TRATAMENTO_TEXTO,
    )


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA4 = (
    "Não consegui entender a idade de {nome}. Digite apenas o número, "
    "exemplo: 10.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_contexto_idade_dependente_invalida_etapa4(nome):
    return montar_texto_com_rodape(
        MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA4.format(
            nome=nome,
        ),
        RODAPE_TRATAMENTO_TEXTO,
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


### DEPENDENTE COM MENOS DE 5 ANOS

MENSAGEM_DEPENDENTE_MENOR_5_ETAPA4 = (
    "No momento, o Supera realiza treinamentos com crianças a partir de 5 "
    "anos. Quando {nome} completar 5 anos, você poderá entrar em contato "
    "novamente.\n\n"
    "Um abraço e até logo! 👋☺️"

)


def montar_mensagem_dependente_menor_5_etapa4(nome):
    return MENSAGEM_DEPENDENTE_MENOR_5_ETAPA4.format(nome=nome)


### CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS

MENSAGEM_IDADE_ACIMA_99_ETAPA4 = (
    "Entre em contato com o número {numero_comercial} para continuar "
    "seu atendimento personalizado."
)


def montar_mensagem_idade_acima_99_etapa4(numero_comercial):
    numero = str(numero_comercial or "").strip()

    if not numero:
        raise ValueError("Número comercial da unidade não configurado")

    return MENSAGEM_IDADE_ACIMA_99_ETAPA4.format(
        numero_comercial=numero,
    )
