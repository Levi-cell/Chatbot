from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)


# ETAPA 17 - TRIAGEM, PERGUNTA 6

CABECALHO_ETAPA17 = "Pergunta 6"
ID_ETAPA17 = 17
PREFIXO_CONTEXTO_INVALIDO = "Não consegui entender sua resposta.\n\n"


def montar_cabecalho_etapa17():
    return CABECALHO_ETAPA17


def montar_mensagem_cliente_etapa17():
    return montar_pergunta_triagem(
        ID_ETAPA17,
        faixa_etaria=FAIXA_ETARIA_ADULTA,
    )


def montar_mensagem_dependente_etapa17(nome, idade_dependente):
    return montar_pergunta_triagem(
        ID_ETAPA17,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
        nome_pessoa=nome,
    )


def montar_mensagem_cliente_contexto_invalido_etapa17():
    return PREFIXO_CONTEXTO_INVALIDO + montar_mensagem_cliente_etapa17()


def montar_mensagem_dependente_contexto_invalido_etapa17(
    nome,
    idade_dependente,
):
    return (
        PREFIXO_CONTEXTO_INVALIDO
        + montar_mensagem_dependente_etapa17(nome, idade_dependente)
    )
