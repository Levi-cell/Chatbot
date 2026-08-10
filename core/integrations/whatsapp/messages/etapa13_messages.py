from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)


# ETAPA 13 - TRIAGEM, PERGUNTA 2

CABECALHO_ETAPA13 = "Pergunta 2"
ID_ETAPA13 = 13
PREFIXO_CONTEXTO_INVALIDO = "Não consegui entender sua resposta.\n\n"


def montar_cabecalho_etapa13():
    return CABECALHO_ETAPA13


def montar_mensagem_cliente_etapa13():
    return montar_pergunta_triagem(
        ID_ETAPA13,
        faixa_etaria=FAIXA_ETARIA_ADULTA,
    )


def montar_mensagem_dependente_etapa13(nome, idade_dependente):
    return montar_pergunta_triagem(
        ID_ETAPA13,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
        nome_pessoa=nome,
    )


def montar_mensagem_cliente_contexto_invalido_etapa13():
    return PREFIXO_CONTEXTO_INVALIDO + montar_mensagem_cliente_etapa13()


def montar_mensagem_dependente_contexto_invalido_etapa13(
    nome,
    idade_dependente,
):
    return (
        PREFIXO_CONTEXTO_INVALIDO
        + montar_mensagem_dependente_etapa13(nome, idade_dependente)
    )
