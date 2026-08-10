from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)


# ETAPA 12 - TRIAGEM, PERGUNTA 1

CABECALHO_ETAPA12 = "Pergunta 1"
ID_ETAPA12 = 12
PREFIXO_CONTEXTO_INVALIDO_CLIENTE = (
    "Não consegui entender sua resposta, mas me diz:\n\n"
)
PREFIXO_CONTEXTO_INVALIDO_DEPENDENTE = (
    "Não consegui entender sua resposta.\n\n"
)


def montar_cabecalho_etapa12():
    return CABECALHO_ETAPA12


def montar_mensagem_cliente_etapa12():
    return montar_pergunta_triagem(
        ID_ETAPA12,
        faixa_etaria=FAIXA_ETARIA_ADULTA,
    )


def montar_mensagem_dependente_etapa12(nome, idade_dependente):
    return montar_pergunta_triagem(
        ID_ETAPA12,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
        nome_pessoa=nome,
    )


def montar_mensagem_cliente_contexto_invalido_etapa12():
    return PREFIXO_CONTEXTO_INVALIDO_CLIENTE + montar_mensagem_cliente_etapa12()


def montar_mensagem_dependente_contexto_invalido_etapa12(
    nome,
    idade_dependente,
):
    return (
        PREFIXO_CONTEXTO_INVALIDO_DEPENDENTE
        + montar_mensagem_dependente_etapa12(nome, idade_dependente)
    )
