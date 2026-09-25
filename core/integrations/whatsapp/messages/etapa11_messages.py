"""Etapa 11: introdução à triagem do titular ou do dependente identificado."""

from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


### MENSAGENS INICIAIS: APRESENTAR A TRIAGEM DA PESSOA ATENDIDA
MENSAGEM_PADRAO_CLIENTE_ETAPA11 = (
    "Certo, olha, antes de prosseguir com sua reserva, vamos iniciar uma "
    "*triagem com 6 perguntas rápidas* para entender melhor como está a saúde "
    "do seu cérebro. 🔎🧠\n\n"
    "Dessa forma podemos preparar uma experiência personalizada! ☺️"
)
MENSAGEM_PADRAO_DEPENDENTE_ETAPA11 = (
    "Certo, olha, antes de prosseguir com sua reserva, vamos iniciar uma "
    "*triagem com 6 perguntas rápidas* para entender melhor como está a saúde "
    "do cérebro de {nome_dependente}. 🔎🧠\n\n"
    "Dessa forma podemos preparar uma experiência personalizada! ☺️"
)

### REPETIÇÃO DA PERGUNTA, SEM REAPRESENTAR A ABERTURA
MENSAGEM_REPETICAO_CLIENTE_ETAPA11 = (
    "Vamos iniciar sua *triagem*? Ela serve para entender como está a saúde "
    "do seu cérebro. 🔎🧠"
)
MENSAGEM_REPETICAO_DEPENDENTE_ETAPA11 = (
    "Vamos iniciar a *triagem* de {nome_dependente}? Ela serve para entender como está "
    "a saúde do cérebro de {nome_dependente}. 🔎🧠"
)

### CONTEXTO INVÁLIDO: MENSAGEM COMPLETA, SEM CONCATENAR A REPETIÇÃO
ORIENTACAO_CONTEXTO_CLIENTE_ETAPA11 = (
    "Olha, não consegui entender, vamos iniciar sua *triagem*? "
    "Ela serve para entender como está a saúde do seu cérebro. 🔎🧠"
)
ORIENTACAO_CONTEXTO_DEPENDENTE_ETAPA11 = (
    "Olha, não consegui entender, vamos iniciar a *triagem* de {nome_dependente}? "
    "Ela serve para entender como está a saúde do cérebro de {nome_dependente}. 🔎🧠"
)


def montar_mensagem_triagem_cognitiva_etapa11(
    *, status_dependente=False, nome_dependente=None, repeticao=False
):
    return _selecionar_mensagem(
        (
            MENSAGEM_REPETICAO_CLIENTE_ETAPA11
            if repeticao
            else MENSAGEM_PADRAO_CLIENTE_ETAPA11
        ),
        (
            MENSAGEM_REPETICAO_DEPENDENTE_ETAPA11
            if repeticao
            else MENSAGEM_PADRAO_DEPENDENTE_ETAPA11
        ),
        status_dependente=status_dependente,
        nome_dependente=nome_dependente,
    )


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO, SEM A MENSAGEM INICIAL
def montar_mensagem_financeiro_etapa11(
    *, status_dependente=False, nome_dependente=None
):
    return montar_mensagem_tratamento_financeiro(
        montar_mensagem_triagem_cognitiva_etapa11(
            status_dependente=status_dependente,
            nome_dependente=nome_dependente,
            repeticao=True,
        )
    )


def montar_mensagem_midia_etapa11(*, status_dependente=False, nome_dependente=None):
    return montar_mensagem_tratamento_midia(
        montar_mensagem_triagem_cognitiva_etapa11(
            status_dependente=status_dependente,
            nome_dependente=nome_dependente,
            repeticao=True,
        ),
        aceita_botoes=True,
    )


def montar_mensagem_reforco_escolar_etapa11(
    *, status_dependente=False, nome_dependente=None
):
    return montar_mensagem_tratamento_reforco_escolar(
        montar_mensagem_triagem_cognitiva_etapa11(
            status_dependente=status_dependente,
            nome_dependente=nome_dependente,
            repeticao=True,
        )
    )


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_invalido_etapa11(
    *, status_dependente=False, nome_dependente=None
):
    return _selecionar_mensagem(
        ORIENTACAO_CONTEXTO_CLIENTE_ETAPA11,
        ORIENTACAO_CONTEXTO_DEPENDENTE_ETAPA11,
        status_dependente=status_dependente,
        nome_dependente=nome_dependente,
    )


BOTAO_ETAPA11_INICIAR_TRIAGEM = "Começar triagem"


def montar_botoes_etapa11():
    return (BOTAO_ETAPA11_INICIAR_TRIAGEM,)


# Formata a rota recebida do fluxo; dependente sem nome não vira titular.
def _selecionar_mensagem(titular, dependente, *, status_dependente, nome_dependente):
    if not isinstance(status_dependente, bool):
        raise ValueError("Destino de atendimento inválido para apresentar a triagem")
    if not status_dependente:
        return titular
    if not isinstance(nome_dependente, str) or not nome_dependente.strip():
        raise ValueError("Nome do dependente ausente para apresentar a triagem")
    return dependente.format(nome_dependente=nome_dependente.strip())
