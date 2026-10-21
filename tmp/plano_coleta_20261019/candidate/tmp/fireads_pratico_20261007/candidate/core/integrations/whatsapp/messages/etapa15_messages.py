from core.integrations.whatsapp.messages.triagem_componentes import (
    montar_orientacao_contexto_triagem,
)
from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)


# ETAPA 15 - TRIAGEM, PERGUNTA 4

CABECALHO_ETAPA15 = "Pergunta 4"
ID_ETAPA15 = 15


def montar_cabecalho_etapa15():
    return CABECALHO_ETAPA15


### PERGUNTA CANÔNICA: A MESMA NA APRESENTAÇÃO E NA REPETIÇÃO
# Titular e dependente usam o catálogo central, com a faixa etária correspondente.
def montar_mensagem_cliente_etapa15():
    return montar_pergunta_triagem(
        ID_ETAPA15,
        faixa_etaria=FAIXA_ETARIA_ADULTA,
    )


def montar_mensagem_dependente_etapa15(nome_dependente, idade_dependente):
    return montar_pergunta_triagem(
        ID_ETAPA15,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
        nome_dependente=nome_dependente,
    )


### CONTEXTO INVÁLIDO: ORIENTAR A RESPOSTA SEM REENVIAR A PERGUNTA
# Aqui não há tratamentos específicos de financeiro, mídia ou reforço escolar.
def montar_mensagem_cliente_contexto_invalido_etapa15():
    return montar_orientacao_contexto_triagem()


def montar_mensagem_dependente_contexto_invalido_etapa15(nome_dependente, idade_dependente):
    return montar_orientacao_contexto_triagem(
        nome_dependente=nome_dependente,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
    )
