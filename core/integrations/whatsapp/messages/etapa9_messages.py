"""Etapa 9: retomada da oferta, sem acumular saudações."""

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


### PERGUNTAS REUTILIZADAS NA INICIAL E NOS TRATAMENTOS, POR PARTICIPANTE
MENSAGEM_REPETICAO_CLIENTE = (
    "Vamos continuar com a reserva da sua *experiência Supera gratuita*? ☺️"
)

MENSAGEM_REPETICAO_DEPENDENTE = (
    "Vamos continuar com a reserva da *experiência Supera gratuita* de "
    "{nome_dependente}? ☺️"
)


### MENSAGEM INICIAL DA ETAPA: SAUDAÇÃO PRÓPRIA + PERGUNTA
def montar_mensagem_retorno_cliente_etapa9(
    nome_titular, *, incluir_saudacao=True, repeticao=False
):
    return _montar_retorno(
        MENSAGEM_REPETICAO_CLIENTE, nome_titular, incluir_saudacao and not repeticao
    )


def montar_mensagem_retorno_dependente_etapa9(
    nome_titular, nome_dependente, *, incluir_saudacao=True, repeticao=False
):
    mensagem = MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    return _montar_retorno(mensagem, nome_titular, incluir_saudacao and not repeticao)


# Com saudação externa de inatividade ou follow-up, não somar esta abertura.
def _montar_retorno(mensagem, nome_titular, incluir_saudacao):
    if incluir_saudacao:
        return compor_mensagem_inicial(
            f"Que bom ver você aqui novamente, {nome_titular}!", mensagem
        )
    return mensagem


### TRATAMENTOS DO TITULAR: ORIENTAÇÃO + PERGUNTA, SEM SAUDAÇÃO PRÓPRIA
def montar_mensagem_retorno_cliente_financeiro_etapa9():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_CLIENTE)


def montar_mensagem_retorno_cliente_midia_etapa9():
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_CLIENTE, aceita_botoes=True
    )


def montar_mensagem_retorno_cliente_reforco_escolar_etapa9():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_CLIENTE)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_retorno_cliente_contexto_invalido_etapa9():
    return (
        "Olha, não consegui entender, deseja continuar com a reserva "
        "da sua *experiência Supera gratuita*?"

    )


### TRATAMENTOS DO DEPENDENTE: PRESERVAR QUEM PARTICIPARÁ DA EXPERIÊNCIA
def montar_mensagem_retorno_dependente_financeiro_etapa9(nome_dependente):
    return montar_mensagem_tratamento_financeiro(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


def montar_mensagem_retorno_dependente_midia_etapa9(nome_dependente):
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente),
        aceita_botoes=True,
    )


def montar_mensagem_retorno_dependente_reforco_escolar_etapa9(nome_dependente):
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_retorno_dependente_contexto_invalido_etapa9(nome_dependente):
    return (
        "Olha, não consegui entender, deseja continuar com a reserva "
        f"da *experiência Supera gratuita* de {nome_dependente}? "

    )


# BOTOES DA ETAPA 9

BOTAO_ETAPA9_QUERO_AGENDAR = "Quero reservar"
BOTAO_ETAPA9_TALVEZ_MAIS_TARDE = "Talvez mais tarde"

BOTOES_ETAPA9 = (
    BOTAO_ETAPA9_QUERO_AGENDAR,
    BOTAO_ETAPA9_TALVEZ_MAIS_TARDE,
)


def montar_botoes_etapa9():
    return BOTOES_ETAPA9
