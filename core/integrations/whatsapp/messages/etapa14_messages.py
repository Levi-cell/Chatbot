from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)


# ETAPA 14 - TRIAGEM, PERGUNTA 3

CABECALHO_ETAPA14 = "Pergunta 3"
ID_ETAPA14 = 14
PREFIXO_CONTEXTO_INVALIDO = "Não consegui entender sua resposta.\n\n"


def montar_cabecalho_etapa14():
    return CABECALHO_ETAPA14


def montar_mensagem_cliente_etapa14():
    return montar_pergunta_triagem(
        ID_ETAPA14,
        faixa_etaria=FAIXA_ETARIA_ADULTA,
    )


def montar_mensagem_dependente_etapa14(nome, idade_dependente):
    return montar_pergunta_triagem(
        ID_ETAPA14,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
        nome_pessoa=nome,
    )


def montar_mensagem_cliente_contexto_invalido_etapa14():
    return PREFIXO_CONTEXTO_INVALIDO + montar_mensagem_cliente_etapa14()


def montar_mensagem_dependente_contexto_invalido_etapa14(
    nome,
    idade_dependente,
):
    return (
        PREFIXO_CONTEXTO_INVALIDO
        + montar_mensagem_dependente_etapa14(nome, idade_dependente)
    )
