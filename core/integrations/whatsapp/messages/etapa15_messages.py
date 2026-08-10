from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)


# ETAPA 15 - TRIAGEM, PERGUNTA 4

CABECALHO_ETAPA15 = "Pergunta 4"
ID_ETAPA15 = 15
PREFIXO_CONTEXTO_INVALIDO = "Não consegui entender sua resposta.\n\n"


def montar_cabecalho_etapa15():
    return CABECALHO_ETAPA15


def montar_mensagem_cliente_etapa15():
    return montar_pergunta_triagem(
        ID_ETAPA15,
        faixa_etaria=FAIXA_ETARIA_ADULTA,
    )


def montar_mensagem_dependente_etapa15(nome, idade_dependente):
    return montar_pergunta_triagem(
        ID_ETAPA15,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
        nome_pessoa=nome,
    )


def montar_mensagem_cliente_contexto_invalido_etapa15():
    return PREFIXO_CONTEXTO_INVALIDO + montar_mensagem_cliente_etapa15()


def montar_mensagem_dependente_contexto_invalido_etapa15(
    nome,
    idade_dependente,
):
    return (
        PREFIXO_CONTEXTO_INVALIDO
        + montar_mensagem_dependente_etapa15(nome, idade_dependente)
    )
