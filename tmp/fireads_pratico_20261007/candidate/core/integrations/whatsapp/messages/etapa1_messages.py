"""Etapa 1: único ponto com tratamentos de primeiro contato."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA1_BOAS_VINDAS,
    montar_texto_com_rodape,
)

from core.integrations.whatsapp.messages.tratamentos.composicao import (
    compor_mensagem_inicial,
)
from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


### APRESENTAÇÃO EXCLUSIVA DO PRIMEIRO CONTATO
APRESENTACAO_ETAPA1 = (
    # A separação completa fica no texto; o compositor apenas concatena.
    "{saudacao}! Sou {artigo_agente} {nome_agente}, assistente do {nome_unidade}! ☺️\n\n"
)

### PERGUNTA QUE COMPLETA A MENSAGEM INICIAL
MENSAGEM_PADRAO_ETAPA1 = "Como você se chama?"

### PERGUNTA RETOMADA NOS TRATAMENTOS E NO FOLLOW-UP, SEM APRESENTAÇÃO
MENSAGEM_REPETICAO_ETAPA1 = "Me diz, qual o seu primeiro nome?"


### ABERTURA EXPLICATIVA: PEDIDO DE INFORMAÇÕES NO PRIMEIRO CONTATO
# Mensagem completa: a própria orientação já pede o nome. Não concatenar
# apresentação padrão, repetição ou rodapé à versão aprovada desta abertura.
MENSAGEM_INFORMACOES_INICIO_ETAPA1 = (
    "{saudacao}! Sou {artigo_agente} {nome_agente}, assistente do {nome_unidade}! ☺️\n\n"
    "Para eu te orientar melhor e passar mais detalhes poderia me falar seu nome?"
)


def montar_mensagem_informacoes_inicio(saudacao, nome_unidade, nome_agente, genero):
    return MENSAGEM_INFORMACOES_INICIO_ETAPA1.format(
        **_montar_contexto_apresentacao(saudacao, nome_unidade, nome_agente, genero)
    )


# APRESENTAÇÃO NORMAL OU REAPRESENTAÇÃO APÓS FOLLOW-UP
def montar_mensagem_etapa1(
    saudacao, nome_unidade, nome_agente, genero, *, repeticao=False
):
    if repeticao:
        return MENSAGEM_REPETICAO_ETAPA1
    return _montar_inicio(
        saudacao, nome_unidade, nome_agente, genero, MENSAGEM_PADRAO_ETAPA1
    )


# PRIMEIRO CONTATO COM TRATAMENTO


def montar_mensagem_midia_inicio(saudacao, nome_unidade, nome_agente, genero):
    mensagem = montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_ETAPA1)
    return _montar_inicio(saudacao, nome_unidade, nome_agente, genero, mensagem)


def montar_mensagem_financeiro_inicio(saudacao, nome_unidade, nome_agente, genero):
    mensagem = montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA1)
    return _montar_inicio(saudacao, nome_unidade, nome_agente, genero, mensagem)


def montar_mensagem_reforco_escolar_inicio(saudacao, nome_unidade, nome_agente, genero):
    mensagem = montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA1)
    return _montar_inicio(saudacao, nome_unidade, nome_agente, genero, mensagem)


# TRATAMENTOS APÓS A APRESENTAÇÃO


def montar_mensagem_midia_etapa1():
    return montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_ETAPA1)


def montar_mensagem_financeiro_etapa1():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA1)


def montar_mensagem_reforco_escolar_etapa1():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA1)


### EXCEÇÃO DE CONTEXTO: A ORIENTAÇÃO JÁ PEDE O NOME, SEM OUTRA PERGUNTA
def montar_mensagem_contexto_nome_invalido_etapa1():
    """Exceção: esta orientação já contém o pedido do primeiro nome."""
    return (
        "Olha, não consegui entender, "
        "digite só seu primeiro nome, por exemplo: Pedro."
    )


# Na abertura, o conteúdo pode ser a pergunta pura ou tratamento + pergunta.
# A apresentação é acrescentada uma única vez, somente nesse primeiro contato.
def _montar_inicio(saudacao, nome_unidade, nome_agente, genero, mensagem):
    apresentacao = APRESENTACAO_ETAPA1.format(
        **_montar_contexto_apresentacao(saudacao, nome_unidade, nome_agente, genero)
    )
    return montar_texto_com_rodape(
        compor_mensagem_inicial(apresentacao, mensagem),
        RODAPE_ETAPA1_BOAS_VINDAS,
    )


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
