"""Etapa 22: apresentação, repetição e tratamentos compostos."""

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
MENSAGEM_PADRAO_ETAPA22 = (
    "Você tem algum comentário ou sugestão para melhorar nosso atendimento?\n"
    "Seu feedback é muito importante para nós! 😊"
)

### REPETIÇÃO DA PERGUNTA, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA22 = (
    "Você gostaria de deixar um comentário ou sugestão sobre nosso atendimento?"
)

ORIENTACAO_CONTEXTO_ETAPA22 = (
    "Olha, não consegui entender. Deseja fazer algum comentário sobre nosso atendimento?"
)


def montar_mensagem_etapa22(*, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_ETAPA22 if repeticao else MENSAGEM_PADRAO_ETAPA22
    return mensagem


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO, SEM A MENSAGEM INICIAL
def montar_mensagem_financeiro_etapa22():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA22)


def montar_mensagem_midia_etapa22():
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_ETAPA22, aceita_botoes=True
    )


def montar_mensagem_reforco_escolar_etapa22():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA22)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_invalido_etapa22():
    return ORIENTACAO_CONTEXTO_ETAPA22


TEXTO_BOTAO_COMENTAR_ETAPA22 = "Sim, quero comentar"


TEXTO_BOTAO_SEM_COMENTARIO_ETAPA22 = "Prefiro não comentar"


def montar_botoes_etapa22():
    return [
        TEXTO_BOTAO_COMENTAR_ETAPA22,
        TEXTO_BOTAO_SEM_COMENTARIO_ETAPA22,
    ]
