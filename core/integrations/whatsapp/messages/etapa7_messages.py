"""Etapa 7: presente, oferta e pergunta de reserva por participante."""

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

### APRESENTAÇÃO INICIAL DO TITULAR

APRESENTACAO_TITULAR = (
    "Maravilha, {nome_titular}! ☺️ "
    "Queremos te presentear com uma *demonstração prática gratuita* na nossa "
    "unidade!\n"
    "Você também participará de uma avaliação cognitiva para conhecer melhor suas "
    "habilidades de memória, atenção, concentração e raciocínio lógico.\n"
)

### É USADA NA APRESENTAÇÃO E NA REPETIÇÃO

MENSAGEM_REPETICAO_TITULAR = (
    "Vamos reservar o melhor dia e horário para sua *experiência Supera exclusiva*? 🧡"
)

### AQUI FAZEMOS A MENSAGEM INICIAL

MENSAGEM_PADRAO_TITULAR = compor_mensagem_inicial(
    APRESENTACAO_TITULAR, MENSAGEM_REPETICAO_TITULAR
)


### APRESENTAÇÃO INICIAL DO DEPENDENTE
APRESENTACAO_DEPENDENTE = (
    "Maravilha, {nome_titular}! ☺️ "
    "Queremos presentear {nome_dependente} com uma *demonstração prática gratuita* na "
    "nossa unidade!\n"
    "{nome_dependente} também participará de uma avaliação cognitiva para conhecer melhor as "
    "habilidades de memória, atenção, concentração e raciocínio lógico.\n"
)

### TRECHO DO DEPENDENTE USADO NA INICIAL E NA REPETIÇÃO
MENSAGEM_REPETICAO_DEPENDENTE = (
    "Vamos reservar o melhor dia e horário para a *experiência Supera exclusiva* de"
    " {nome_dependente}? 🧡"
)

### MENSAGEM INICIAL DO DEPENDENTE: APRESENTAÇÃO + REPETIÇÃO
MENSAGEM_PADRAO_DEPENDENTE = compor_mensagem_inicial(
    APRESENTACAO_DEPENDENTE, MENSAGEM_REPETICAO_DEPENDENTE
)


def montar_mensagem_oferta_cliente_etapa7(nome_titular, *, repeticao=False):
    if repeticao:
        return MENSAGEM_REPETICAO_TITULAR
    return MENSAGEM_PADRAO_TITULAR.format(
        nome_titular=_validar_nome_oferta(nome_titular, "nome_titular")
    )



### AQUI É UM EXEMPLO ONDE USAMOS APENAS A MENSAGEM DE REPETIÇÃO PRO TRATAMENTO
def montar_mensagem_oferta_cliente_financeiro_etapa7():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_TITULAR)


def montar_mensagem_oferta_cliente_midia_etapa7():
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_TITULAR, aceita_botoes=True
    )


def montar_mensagem_oferta_cliente_reforco_escolar_etapa7():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_TITULAR)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_oferta_cliente_contexto_invalido_etapa7():
    return (
        "Olha, não consegui entender, me diz, você quer"
        " reservar o melhor dia e horário para sua *experiência Supera gratuita*? 🧡"
    )


def montar_mensagem_oferta_dependente_etapa7(
    nome_titular, nome_dependente, *, repeticao=False
):
    nome_dependente = _validar_nome_oferta(nome_dependente, "nome_dependente")
    if repeticao:
        return MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    return MENSAGEM_PADRAO_DEPENDENTE.format(
        nome_titular=_validar_nome_oferta(nome_titular, "nome_titular"),
        nome_dependente=nome_dependente,
    )


def _validar_nome_oferta(valor, campo):
    """Impede saudar o participante errado ou mostrar um nome ausente na oferta."""
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"Nome ausente para apresentar a oferta: {campo}")
    return valor.strip()


### TRATAMENTOS DO DEPENDENTE: USAR SÓ A REPETIÇÃO, SEM A APRESENTAÇÃO
def montar_mensagem_oferta_dependente_financeiro_etapa7(nome_dependente):
    return montar_mensagem_tratamento_financeiro(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


def montar_mensagem_oferta_dependente_midia_etapa7(nome_dependente):
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente),
        aceita_botoes=True,
    )


def montar_mensagem_oferta_dependente_reforco_escolar_etapa7(nome_dependente):
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_oferta_dependente_contexto_invalido_etapa7(nome_dependente):
    return (
        "Olha, não consegui entender, me diz, "
        "você quer reservar o melhor dia e horário para a *experiência Supera gratuita* de"
        f" {nome_dependente}? 🧡"
    )


# BOTOES DA ETAPA 7

BOTAO_ETAPA7_QUERO_AGENDAR = "Quero reservar"
BOTAO_ETAPA7_TALVEZ_MAIS_TARDE = "Talvez mais tarde"

BOTOES_ETAPA7 = (
    BOTAO_ETAPA7_QUERO_AGENDAR,
    BOTAO_ETAPA7_TALVEZ_MAIS_TARDE,
)


def montar_botoes_etapa7():
    return BOTOES_ETAPA7
