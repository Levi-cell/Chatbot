"""Etapa 10: apresentação, repetição e tratamentos compostos."""

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
MENSAGEM_PADRAO_ETAPA10 = (
    "Certo, para fazer *sua reserva*, me diz, qual é o seu melhor email? ☺️"
)

### REPETIÇÃO DA PERGUNTA, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA10 = "Me diz novamente, qual é o seu melhor email?"



ORIENTACAO_CONTEXTO_ETAPA10 = (
    "Olha, não consegui identificar um email válido. Digite o email "
    "completo, por exemplo: nome@gmail.com."
)


def montar_mensagem_email_etapa10(*, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_ETAPA10 if repeticao else MENSAGEM_PADRAO_ETAPA10
    return mensagem


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO, SEM A MENSAGEM INICIAL
def montar_mensagem_email_etapa10_financeiro():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA10)


def montar_mensagem_email_etapa10_midia():
    return montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_ETAPA10)


def montar_mensagem_email_etapa10_reforco_escolar():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA10)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_email_invalido_etapa10():
    return ORIENTACAO_CONTEXTO_ETAPA10
