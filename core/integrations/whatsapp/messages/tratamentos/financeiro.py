"""Esclarece a cortesia na orientação financeira, sem repeti-la na pergunta."""

from .composicao import compor_tratamento


MENSAGEM_TRATAMENTO_FINANCEIRO = (
    "Olha, demais informações como valores de investimento são *exclusivas* para cada aluno e "
    "só são possíveis de determinar após a "
    "sua *experiência Supera* por cortesia da unidade.\n\n"
)
PONTE_TRATAMENTO_FINANCEIRO = "Vamos lá:\n\n"


def montar_mensagem_tratamento_financeiro(mensagem_repeticao):
    return compor_tratamento(
        MENSAGEM_TRATAMENTO_FINANCEIRO,
        mensagem_repeticao,
        ponte=PONTE_TRATAMENTO_FINANCEIRO,
    )
