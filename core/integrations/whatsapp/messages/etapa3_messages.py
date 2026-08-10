"""Mensagens da confirmação de quem receberá o atendimento."""

from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_reforco_escolar,
)


MENSAGEM_ETAPA3_TITULAR = (
    "Você confirma que esse atendimento é para você?"
)
MENSAGEM_ETAPA3_DEPENDENTE = (
    "Você confirma que esse atendimento é para um dependente?"
)

MENSAGEM_TRATAMENTO_MIDIA_ETAPA3 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto."
)
MENSAGEM_TRATAMENTO_FINANCEIRO_ETAPA3 = (
    "Olha, demais informações, como valores de investimento, são "
    "apresentadas no atendimento presencial após a aula *gratuita*."
)
MENSAGEM_TRATAMENTO_CONTEXTO_ETAPA3 = "Desculpe, não entendi."

BOTAO_ETAPA3_SIM = "Sim"
BOTAO_ETAPA3_NAO = "Não"
BOTOES_ETAPA3 = (
    BOTAO_ETAPA3_SIM,
    BOTAO_ETAPA3_NAO,
)


def montar_mensagem_etapa3(status_dependente):
    """Escolhe a confirmação correspondente ao destino salvo na etapa 2."""
    if status_dependente:
        return MENSAGEM_ETAPA3_DEPENDENTE

    return MENSAGEM_ETAPA3_TITULAR


def montar_mensagem_midia_etapa3(status_dependente):
    return _montar_mensagem_tratamento(
        MENSAGEM_TRATAMENTO_MIDIA_ETAPA3,
        status_dependente,
    )


def montar_mensagem_financeiro_etapa3(status_dependente):
    return _montar_mensagem_tratamento(
        MENSAGEM_TRATAMENTO_FINANCEIRO_ETAPA3,
        status_dependente,
    )


def montar_mensagem_reforco_escolar_etapa3(status_dependente):
    return montar_mensagem_tratamento_reforco_escolar(
        montar_mensagem_etapa3(status_dependente),
    )


def montar_mensagem_contexto_etapa3(status_dependente):
    return _montar_mensagem_tratamento(
        MENSAGEM_TRATAMENTO_CONTEXTO_ETAPA3,
        status_dependente,
    )


def montar_botoes_etapa3():
    return BOTOES_ETAPA3


def _montar_mensagem_tratamento(tratamento, status_dependente):
    pergunta = montar_mensagem_etapa3(status_dependente)
    return f"{tratamento}\n\nMas bora lá:\n\n{pergunta}"
