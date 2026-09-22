"""Orientação financeira compartilhada; a experiência oferecida é gratuita."""

from .composicao import compor_tratamento


MENSAGEM_TRATAMENTO_FINANCEIRO = (
    "Olha, os valores de investimento são definidos após a "
    "*experiência Supera gratuita* na unidade. Assim, nossa equipe poderá "
    "orientar você sobre a opção mais adequada. ☺️"
)


def montar_mensagem_tratamento_financeiro(mensagem_repeticao):
    return compor_tratamento(
        MENSAGEM_TRATAMENTO_FINANCEIRO,
        mensagem_repeticao,
        ponte="Mas bora lá:",
    )
