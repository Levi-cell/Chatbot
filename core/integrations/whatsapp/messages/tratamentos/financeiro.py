"""Orientação financeira compartilhada; a experiência oferecida é gratuita."""

from .composicao import compor_tratamento


MENSAGEM_TRATAMENTO_FINANCEIRO = (
    "Olha, demais informações como valores de investimento são *exclusivas* para cada aluno e"
    "só são possíveis de determinar após a"
    "sua *experiência supera gratuita* na unidade."
)


def montar_mensagem_tratamento_financeiro(mensagem_repeticao):
    return compor_tratamento(
        MENSAGEM_TRATAMENTO_FINANCEIRO,
        mensagem_repeticao,
        ponte="Mas bora lá:",
    )
