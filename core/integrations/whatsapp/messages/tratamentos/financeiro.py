"""Esclarece a cortesia na orientação financeira, sem repeti-la na pergunta."""

from .composicao import compor_tratamento


MENSAGEM_TRATAMENTO_FINANCEIRO = (
    "Olha, demais informações, como valores de investimento, só são definidas "
    "de acordo com as necessidades de cada aluno e após a análise da "
    "experiência Supera oferecida por cortesia da unidade.\n\n"
)


def montar_mensagem_tratamento_financeiro(mensagem_repeticao):
    return compor_tratamento(
        MENSAGEM_TRATAMENTO_FINANCEIRO,
        mensagem_repeticao,
    )
