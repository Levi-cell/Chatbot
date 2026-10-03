"""Etapa 21: avaliação do atendimento, sem confundir nota com aceite."""

from core.integrations.whatsapp.messages.tratamentos.composicao import (
    compor_mensagem_inicial,
)


OPCOES_SATISFACAO_ETAPA21 = (
    (5, "Excelente"),
    (4, "Muito bom"),
    (3, "Regular"),
    (2, "Ruim"),
    (1, "Muito ruim"),
)

### PERGUNTA DE SATISFAÇÃO, REUTILIZADA NA INICIAL E NA REPETIÇÃO
MENSAGEM_REPETICAO_ETAPA21 = (
    "Antes de finalizarmos, qual seu grau de satisfação com o nosso atendimento?"
)


### MENSAGEM INICIAL: ACOLHIMENTO + PERGUNTA; REPETIÇÃO SEM NOVA CELEBRAÇÃO
APRESENTACAO_ETAPA21 = "Maravilha, {nome_titular}! 😊\n\n"


def montar_mensagem_etapa21(nome_titular, *, repeticao=False):
    if repeticao:
        return MENSAGEM_REPETICAO_ETAPA21
    return compor_mensagem_inicial(
        APRESENTACAO_ETAPA21.format(nome_titular=nome_titular),
        MENSAGEM_REPETICAO_ETAPA21,
    )


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_invalido_etapa21():
    return (
        "Olha, não consegui identificar sua avaliação do atendimento. "
        "Escolha uma nota de 1 (muito ruim) a 5 (excelente)."
    )


def montar_opcoes_satisfacao_etapa21():
    return [
        (nota, f"{nota} - {descricao}") for nota, descricao in OPCOES_SATISFACAO_ETAPA21
    ]
