"""Etapa 4: apresentação, repetição e tratamentos compostos."""

from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


### MENSAGEM INICIAL DO TITULAR: EXPLICAÇÃO + PERGUNTA DA PROFISSÃO
MENSAGEM_PADRAO_TITULAR_ETAPA4 = (
    "Olha, antes de continuar, vou precisar fazer algumas perguntas para "
    "conhecer melhor seu perfil. Me diz, qual a sua *profissão*?"
)

### MENSAGEM INICIAL DO DEPENDENTE: A PROFISSÃO CONTINUA SENDO DO TITULAR
MENSAGEM_PADRAO_DEPENDENTE_ETAPA4 = (
    "Olha, antes de continuar, vou precisar fazer algumas perguntas para "
    "conhecer melhor o seu perfil e o perfil da outra pessoa. Me diz, qual a sua *profissão* hoje?"
)

### REPETIÇÃO COMUM ÀS DUAS ROTAS, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA4 = "Me diz, qual a sua *profissão* hoje?"

ORIENTACAO_CONTEXTO_ETAPA4 = (
    "Olha, não consegui entender. Me conta, com o que você "
    "trabalha hoje?"
)


def montar_mensagem_etapa4(*, status_dependente=False, repeticao=False):
    if repeticao:
        return MENSAGEM_REPETICAO_ETAPA4
    return (
        MENSAGEM_PADRAO_DEPENDENTE_ETAPA4
        if status_dependente
        else MENSAGEM_PADRAO_TITULAR_ETAPA4
    )


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO, SEM A MENSAGEM INICIAL
def montar_mensagem_financeiro_etapa4():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA4)


def montar_mensagem_midia_etapa4():
    return montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_ETAPA4)


def montar_mensagem_reforco_escolar_etapa4():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA4)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_profissao_invalida_etapa4():
    return ORIENTACAO_CONTEXTO_ETAPA4
