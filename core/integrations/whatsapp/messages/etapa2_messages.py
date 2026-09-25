"""Etapa 2: apresentação, repetição e tratamentos compostos."""

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
MENSAGEM_PADRAO_ETAPA2 = (
    "Prazer, {nome_titular}! ☺️\n\n"
    "O Supera é um curso de *estimulação cognitiva* que trabalha habilidades "
    "cognitivas e socioemocionais por meio de atividades que estimulam atenção, "
    "concentração, memória, raciocínio e outras funções importantes para o dia a "
    "dia.\n\n"
    "Para eu entender melhor como podemos ajudar, me conta, *esse atendimento é "
    "para você ou para um dependente?*"
)

### REPETIÇÃO DA PERGUNTA, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_ETAPA2 = (
    "Me diz, *esse atendimento é para você ou para um dependente*?"
)

ORIENTACAO_CONTEXTO_ETAPA2 = (
    "Olha, não consegui entender, me diz, *esse atendimento é para você ou para um dependente*? "
)


def montar_mensagem_etapa2(nome_titular, *, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_ETAPA2 if repeticao else MENSAGEM_PADRAO_ETAPA2
    return mensagem.format(nome_titular=nome_titular)


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO, SEM A MENSAGEM INICIAL
def montar_mensagem_financeiro_etapa2():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_ETAPA2)


def montar_mensagem_midia_etapa2():
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_ETAPA2, aceita_botoes=True
    )


def montar_mensagem_reforco_escolar_etapa2():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_ETAPA2)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_etapa2():
    return ORIENTACAO_CONTEXTO_ETAPA2


BOTAO_ETAPA2_PARA_MIM = "Para mim"


BOTAO_ETAPA2_OUTRA_PESSOA = "Para um dependente"


BOTOES_ETAPA2 = (
    BOTAO_ETAPA2_PARA_MIM,
    BOTAO_ETAPA2_OUTRA_PESSOA,
)


def montar_botoes_etapa2():
    return BOTOES_ETAPA2
