from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA1_BOAS_VINDAS,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_reforco_escolar,
)


### INICIO NORMAL

MENSAGEM_ETAPA1 = (
    "{saudacao}! Sou {artigo_agente} {nome_agente}, "
    "atendente virtual do {nome_unidade}! ☺️\n"
    "Como você se chama?"
)

def montar_mensagem_etapa1(saudacao, nome_unidade, nome_agente, genero):
    return montar_texto_com_rodape(
        MENSAGEM_ETAPA1.format(
            **_montar_contexto_apresentacao(
                saudacao,
                nome_unidade,
                nome_agente,
                genero,
            )
        ),
        RODAPE_ETAPA1_BOAS_VINDAS,
    )





### INICIO PORÉM CLIENTE INICIA COM MIDA

MENSAGEM_MIDIA_INICIO = (
    "{saudacao}! Sou {artigo_agente} {nome_agente}, "
    "atendente virtual do {nome_unidade}! ☺️\n"
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_midia_inicio(
    saudacao,
    nome_unidade,
    nome_agente,
    genero,
):
    return montar_texto_com_rodape(
        MENSAGEM_MIDIA_INICIO.format(
            **_montar_contexto_apresentacao(
                saudacao,
                nome_unidade,
                nome_agente,
                genero,
            )
        ),
        RODAPE_ETAPA1_BOAS_VINDAS,
    )





### INICIO PORÈM CLIENTE INICIA COM PERGUNTA FINANCEIRA

MENSAGEM_FINANCEIRO_INICIO = (
    "{saudacao}! Sou {artigo_agente} {nome_agente}, "
    "atendente virtual do {nome_unidade}! ☺️\n"
    "Olha demais informações como valores de investimento são apresentadas no atendimento "
    "presencial após sua aula *gratuita*.\n"
    "Me diz, qual o seu primeiro nome?"
)

# mensagem_final = MENSAGEM_FINANCEIRO_INICIO + Midia.santo_andre (Ideia futura)

def montar_mensagem_financeiro_inicio(
    saudacao,
    nome_unidade,
    nome_agente,
    genero,
):
    return montar_texto_com_rodape(
        MENSAGEM_FINANCEIRO_INICIO.format(
            **_montar_contexto_apresentacao(
                saudacao,
                nome_unidade,
                nome_agente,
                genero,
            )
        ),
        RODAPE_ETAPA1_BOAS_VINDAS,
    )

### CLIENTE RESPONDE AO NOME COM MIDIA

MENSAGEM_MIDIA_ETAPA1 = (
    "Olha não reconhecemos ainda mensagem com mídia, apenas texto.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_midia_etapa1():
    return MENSAGEM_MIDIA_ETAPA1



### CLIENTE RESPONDE AO NOME COM FINANCEIRO

MENSAGEM_FINANCEIRO_ETAPA1 = (
    "Olha demais informações como valores de investimento são apresentadas no atendimento "
    "presencial após sua aula *gratuita*.\n"
    "Me diz, qual o seu primeiro nome?"
)

def montar_mensagem_financeiro_etapa1():
    return MENSAGEM_FINANCEIRO_ETAPA1


### CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR

MENSAGEM_RETOMADA_ETAPA1 = "Me diz, qual o seu primeiro nome?"


def montar_mensagem_reforco_escolar_inicio(
    saudacao,
    nome_unidade,
    nome_agente,
    genero,
):
    apresentacao = (
        "{saudacao}! Sou {artigo_agente} {nome_agente}, "
        "atendente virtual do {nome_unidade}! ☺️\n"
    ).format(
        **_montar_contexto_apresentacao(
            saudacao,
            nome_unidade,
            nome_agente,
            genero,
        )
    )
    mensagem = (
        f"{apresentacao}"
        f"{montar_mensagem_tratamento_reforco_escolar(MENSAGEM_RETOMADA_ETAPA1)}"
    )
    return montar_texto_com_rodape(
        mensagem,
        RODAPE_ETAPA1_BOAS_VINDAS,
    )


def montar_mensagem_reforco_escolar_etapa1():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_ETAPA1,
    )


### CLIENTE RESPONDE AO NOME COM CONTEXTO INVALIDO

MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA1 = (
    "Não consegui entender o seu nome. Me fala só seu primeiro nome, "
    "exemplo: Pedro"
)

def montar_mensagem_contexto_nome_invalido_etapa1():
    return MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA1


def _montar_contexto_apresentacao(
    saudacao,
    nome_unidade,
    nome_agente,
    genero,
):
    """Valida e formata os dados editoriais da apresentação inicial."""
    saudacao = str(saudacao or "").strip()
    nome_unidade = str(nome_unidade or "").strip()
    nome_agente = str(nome_agente or "").strip()
    genero = str(genero or "").strip()

    if not saudacao or not nome_unidade or not nome_agente:
        raise ValueError("Dados obrigatorios da apresentacao inicial ausentes")

    artigo_agente = {
        "masculino": "o",
        "feminino": "a",
    }.get(genero)
    if artigo_agente is None:
        raise ValueError(f"Genero de agente invalido: {genero!r}")

    return {
        "saudacao": saudacao,
        "nome_unidade": nome_unidade,
        "nome_agente": nome_agente,
        "artigo_agente": artigo_agente,
    }
