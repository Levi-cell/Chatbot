"""Etapa 3: confirmação do destinatário, com repetição neutra."""

from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


### MENSAGENS INICIAIS: CONFIRMAÇÃO PARA TITULAR OU DEPENDENTE
MENSAGEM_PADRAO_TITULAR = "Você confirma que esse atendimento é para você? ☺️"

MENSAGEM_PADRAO_DEPENDENTE = (
    "Você confirma que esse atendimento é para um dependente? ☺️"
)

### REPETIÇÕES: MANTER O MESMO DESTINATÁRIO NA PERGUNTA
MENSAGEM_REPETICAO_TITULAR = "Me confirma, esse atendimento é para você?"

MENSAGEM_REPETICAO_DEPENDENTE = "Me confirma, esse atendimento é para um dependente?"


def montar_mensagem_etapa3(status_dependente, *, repeticao=False):
    if repeticao:
        return (
            MENSAGEM_REPETICAO_DEPENDENTE
            if status_dependente
            else MENSAGEM_REPETICAO_TITULAR
        )
    return MENSAGEM_PADRAO_DEPENDENTE if status_dependente else MENSAGEM_PADRAO_TITULAR


### TRATAMENTOS: ORIENTAÇÃO + REPETIÇÃO DA ROTA CORRETA
def montar_mensagem_financeiro_etapa3(status_dependente):
    return montar_mensagem_tratamento_financeiro(
        montar_mensagem_etapa3(status_dependente, repeticao=True)
    )


def montar_mensagem_midia_etapa3(status_dependente):
    return montar_mensagem_tratamento_midia(
        montar_mensagem_etapa3(status_dependente, repeticao=True), aceita_botoes=True
    )


def montar_mensagem_reforco_escolar_etapa3(status_dependente):
    return montar_mensagem_tratamento_reforco_escolar(
        montar_mensagem_etapa3(status_dependente, repeticao=True)
    )


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_etapa3(status_dependente):
    destinatario = "um dependente" if status_dependente else "você"
    return (
        "Olha, não consegui entender, "
        f"Me confirma, esse atendimento é para {destinatario}?"
    )


BOTAO_ETAPA3_SIM = "Sim"
BOTAO_ETAPA3_NAO = "Não"
BOTOES_ETAPA3 = (BOTAO_ETAPA3_SIM, BOTAO_ETAPA3_NAO)


def montar_botoes_etapa3():
    return BOTOES_ETAPA3
