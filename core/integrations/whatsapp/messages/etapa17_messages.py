# ETAPA 17 - NOTA DA PESQUISA DE SATISFACAO

OPCOES_SATISFACAO_ETAPA17 = (
    (5, "Excelente"),
    (4, "Muito bom"),
    (3, "Regular"),
    (2, "Ruim"),
    (1, "Muito ruim"),
)

MENSAGEM_ETAPA17 = (
    "Maravilha {nome}! 😊\n\n"
    "Antes de finalizarmos, qual seu grau de satisfação com o nosso "
    "atendimento?"
)

MENSAGEM_CONTEXTO_INVALIDO_ETAPA17 = (
    "Desculpe, não entendi. Sendo 5 excelente e 1 muito ruim, qual o seu "
    "grau de satisfação?"
)


def montar_mensagem_etapa17(nome):
    return MENSAGEM_ETAPA17.format(nome=nome)


def montar_mensagem_contexto_invalido_etapa17():
    return MENSAGEM_CONTEXTO_INVALIDO_ETAPA17


def montar_opcoes_satisfacao_etapa17():
    return [
        (nota, f"{nota} - {descricao}")
        for nota, descricao in OPCOES_SATISFACAO_ETAPA17
    ]
