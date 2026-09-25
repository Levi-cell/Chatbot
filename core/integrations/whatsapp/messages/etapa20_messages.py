"""Etapa 20: apresentação, repetição e tratamentos compostos."""

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
MENSAGEM_PADRAO_ETAPA20 = (
    "Você tem algum comentário ou sugestão para melhorar nosso atendimento? "
    "Seu feedback é muito importante para nós! 😊"
)

### REPETIÇÃO DA PERGUNTA, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA20 = (
    "Você gostaria de deixar um comentário ou sugestão sobre nosso atendimento?"
)

ORIENTACAO_CONTEXTO_ETAPA20 = (
    "Olha, não consegui entender. Deseja fazer algum comentário sobre nosso atendimento?"
)


def montar_mensagem_etapa20(*, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_ETAPA20 if repeticao else MENSAGEM_PADRAO_ETAPA20
    return mensagem


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO, SEM A MENSAGEM INICIAL
def montar_mensagem_financeiro_etapa20():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA20)


def montar_mensagem_midia_etapa20():
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_ETAPA20, aceita_botoes=True
    )


def montar_mensagem_reforco_escolar_etapa20():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA20)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_invalido_etapa20():
    return ORIENTACAO_CONTEXTO_ETAPA20


TEXTO_BOTAO_COMENTAR_ETAPA20 = "Sim, quero comentar"


TEXTO_BOTAO_SEM_COMENTARIO_ETAPA20 = "Prefiro não comentar"


def montar_botoes_etapa20():
    return [
        TEXTO_BOTAO_COMENTAR_ETAPA20,
        TEXTO_BOTAO_SEM_COMENTARIO_ETAPA20,
    ]
