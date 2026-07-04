from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA1_SAUDACAO,
    RODAPE_ETAPA1_BOAS_VINDAS,
    RODAPE_TRATAMENTO_TEXTO,
    montar_texto_com_cabecalho_e_rodape,
    montar_texto_com_rodape,
)


### INICIO NORMAL

MENSAGEM_ETAPA1 = (
    "{saudacao}! Sou a Suh, atendente virtual do Supera! ☺️\n"
    "Como você se chama?"
)

def montar_mensagem_etapa1(saudacao):
    return montar_texto_com_cabecalho_e_rodape(
        MENSAGEM_ETAPA1.format(saudacao=saudacao),
        CABECALHO_ETAPA1_SAUDACAO,
        RODAPE_ETAPA1_BOAS_VINDAS,
    )





### INICIO PORÉM CLIENTE INICIA COM MIDA

MENSAGEM_MIDIA_INICIO = (
    "{saudacao}! Sou a Suh, atendente virtual do Supera! ☺️\n"
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_midia_inicio(saudacao):
    return montar_texto_com_cabecalho_e_rodape(
        MENSAGEM_MIDIA_INICIO.format(saudacao=saudacao),
        CABECALHO_ETAPA1_SAUDACAO,
        RODAPE_ETAPA1_BOAS_VINDAS,
    )





### INICIO PORÈM CLIENTE INICIA COM PERGUNTA FINANCEIRA

MENSAGEM_FINANCEIRO_INICIO = (
    "{saudacao}! Sou a Suh, atendente virtual do Supera! ☺️\n"
    "Olha demais informações como valores são apresentadas no atendimento "
    "presencial após sua aula *gratuita*.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_financeiro_inicio(saudacao):
    return montar_texto_com_cabecalho_e_rodape(
        MENSAGEM_FINANCEIRO_INICIO.format(saudacao=saudacao),
        CABECALHO_ETAPA1_SAUDACAO,
        RODAPE_ETAPA1_BOAS_VINDAS,
    )

### CLIENTE RESPONDE AO NOME COM MIDIA

MENSAGEM_MIDIA_ETAPA1 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_midia_etapa1():
    return montar_texto_com_rodape(
        MENSAGEM_MIDIA_ETAPA1,
        RODAPE_TRATAMENTO_TEXTO,
    )



### CLIENTE RESPONDE AO NOME COM FINANCEIRO

MENSAGEM_FINANCEIRO_ETAPA1 = (
    "Olha demais informações como valores são apresentadas no atendimento "
    "presencial após sua aula *gratuita*.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_financeiro_etapa1():
    return montar_texto_com_rodape(
        MENSAGEM_FINANCEIRO_ETAPA1,
        RODAPE_TRATAMENTO_TEXTO,
    )


### CLIENTE RESPONDE AO NOME COM CONTEXTO INVALIDO

MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA1 = (
    "Não consegui entender o seu nome. Me fala só seu primeiro nome, "
    "exemplo: Pedro"
)

def montar_mensagem_contexto_nome_invalido_etapa1():
    return montar_texto_com_rodape(
        MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA1,
        RODAPE_TRATAMENTO_TEXTO,
    )
