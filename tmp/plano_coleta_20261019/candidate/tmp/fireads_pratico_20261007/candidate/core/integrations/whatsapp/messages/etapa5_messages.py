"""Etapa 5: apresentação, repetição e tratamentos compostos."""

from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


### MENSAGEM COMPLETA PARA A ENTRADA NA ETAPA
MENSAGEM_PADRAO_ETAPA5 = (

    "Certo, qual é o *nome* do dependente?"
)

### REPETIÇÃO DA PERGUNTA, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA5 = "Me diz, qual o nome da pessoa?"

ORIENTACAO_CONTEXTO_ETAPA5 = (
    "Olha, não consegui entender, digite só o primeiro "
    "nome, por exemplo: Pedro."
)


def montar_mensagem_etapa5(*, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_ETAPA5 if repeticao else MENSAGEM_PADRAO_ETAPA5
    return mensagem


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO, SEM A MENSAGEM INICIAL
def montar_mensagem_financeiro_etapa5():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA5)


def montar_mensagem_midia_etapa5():
    return montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_ETAPA5)


def montar_mensagem_reforco_escolar_etapa5():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA5)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_nome_invalido_etapa5():
    return ORIENTACAO_CONTEXTO_ETAPA5
