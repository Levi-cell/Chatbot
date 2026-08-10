from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)


# ETAPA 16 - TRIAGEM, PERGUNTA 5

CABECALHO_ETAPA16 = "Pergunta 5"
ID_ETAPA16 = 16
PREFIXO_CONTEXTO_INVALIDO = "Não consegui entender sua resposta.\n\n"


def montar_cabecalho_etapa16():
    return CABECALHO_ETAPA16


def montar_mensagem_cliente_etapa16():
    return montar_pergunta_triagem(
        ID_ETAPA16,
        faixa_etaria=FAIXA_ETARIA_ADULTA,
    )


def montar_mensagem_dependente_etapa16(nome, idade_dependente):
    return montar_pergunta_triagem(
        ID_ETAPA16,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
        nome_pessoa=nome,
    )


def montar_mensagem_cliente_contexto_invalido_etapa16():
    return PREFIXO_CONTEXTO_INVALIDO + montar_mensagem_cliente_etapa16()


def montar_mensagem_dependente_contexto_invalido_etapa16(
    nome,
    idade_dependente,
):
    return (
        PREFIXO_CONTEXTO_INVALIDO
        + montar_mensagem_dependente_etapa16(nome, idade_dependente)
    )
