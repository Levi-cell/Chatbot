"""Etapa 19: avaliação do atendimento, sem confundir nota com aceite."""

from core.integrations.whatsapp.messages.tratamentos.composicao import (
    compor_mensagem_inicial,
)


OPCOES_SATISFACAO_ETAPA19 = (
    (5, "Excelente"),
    (4, "Muito bom"),
    (3, "Regular"),
    (2, "Ruim"),
    (1, "Muito ruim"),
)

### PERGUNTA DE SATISFAÇÃO, REUTILIZADA NA INICIAL E NA REPETIÇÃO
MENSAGEM_REPETICAO_ETAPA19 = (
    "Antes de finalizarmos, qual seu grau de satisfação com o nosso atendimento?"
)


### MENSAGEM INICIAL: ACOLHIMENTO + PERGUNTA; REPETIÇÃO SEM NOVA CELEBRAÇÃO
def montar_mensagem_etapa19(nome_titular, *, repeticao=False):
    if repeticao:
        return MENSAGEM_REPETICAO_ETAPA19
    return compor_mensagem_inicial(
        f"Maravilha, {nome_titular}! 😊", MENSAGEM_REPETICAO_ETAPA19
    )


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_invalido_etapa19():
    return (
        "Olha, não consegui identificar sua avaliação do atendimento. "
        "Escolha uma nota de 1 (muito ruim) a 5 (excelente)."
    )


def montar_opcoes_satisfacao_etapa19():
    return [
        (nota, f"{nota} - {descricao}") for nota, descricao in OPCOES_SATISFACAO_ETAPA19
    ]
