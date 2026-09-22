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


### MENSAGEM COMPLETA PARA A ENTRADA NA ETAPA
MENSAGEM_PADRAO_ETAPA4 = (
    "Certo, agora me diz, qual é a sua *profissão*? "
)

### REPETIÇÃO DA PERGUNTA, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA4 = "Me diz, qual é a sua profissão?"

ORIENTACAO_CONTEXTO_ETAPA4 = (
    "Olha, não consegui entender. Me conta, com o que você "
    "trabalha hoje?"
)


def montar_mensagem_etapa4(*, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_ETAPA4 if repeticao else MENSAGEM_PADRAO_ETAPA4
    return mensagem


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
