from core.integrations.whatsapp.messages.triagem_componentes import (
    montar_orientacao_contexto_triagem,
)
from core.triagem.perguntas import (
    FAIXA_ETARIA_ADULTA,
    montar_pergunta_triagem,
    obter_faixa_etaria_triagem,
)


# ETAPA 16 - TRIAGEM, PERGUNTA 5

CABECALHO_ETAPA16 = "Pergunta 5"
ID_ETAPA16 = 16


def montar_cabecalho_etapa16():
    return CABECALHO_ETAPA16


### PERGUNTA CANÔNICA: A MESMA NA APRESENTAÇÃO E NA REPETIÇÃO
# Titular e dependente usam o catálogo central, com a faixa etária correspondente.
def montar_mensagem_cliente_etapa16():
    return montar_pergunta_triagem(
        ID_ETAPA16,
        faixa_etaria=FAIXA_ETARIA_ADULTA,
    )


def montar_mensagem_dependente_etapa16(nome_dependente, idade_dependente):
    return montar_pergunta_triagem(
        ID_ETAPA16,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
        nome_dependente=nome_dependente,
    )


### CONTEXTO INVÁLIDO: ORIENTAR A RESPOSTA SEM REENVIAR A PERGUNTA
# Aqui não há tratamentos específicos de financeiro, mídia ou reforço escolar.
def montar_mensagem_cliente_contexto_invalido_etapa16():
    return montar_orientacao_contexto_triagem()


def montar_mensagem_dependente_contexto_invalido_etapa16(nome_dependente, idade_dependente):
    return montar_orientacao_contexto_triagem(
        nome_dependente=nome_dependente,
        faixa_etaria=obter_faixa_etaria_triagem(idade_dependente),
    )
