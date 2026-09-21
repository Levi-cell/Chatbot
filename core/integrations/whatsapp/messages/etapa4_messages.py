from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_financeiro,
    montar_mensagem_tratamento_reforco_escolar,
)


MENSAGEM_ETAPA4 = "Antes de prosseguirmos, me fala, qual sua profissão hoje?"


def montar_mensagem_etapa4():
    return MENSAGEM_ETAPA4


MENSAGEM_MIDIA_ETAPA4 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Mas bora lá, me fala novamente, qual sua profissão?"
)


def montar_mensagem_midia_etapa4():
    return MENSAGEM_MIDIA_ETAPA4


MENSAGEM_FINANCEIRO_ETAPA4 = montar_mensagem_tratamento_financeiro(
    "Me fala, qual sua profissão?"
)


def montar_mensagem_financeiro_etapa4():
    return MENSAGEM_FINANCEIRO_ETAPA4


MENSAGEM_RETOMADA_ETAPA4 = "Me fala novamente, qual sua profissão?"


def montar_mensagem_reforco_escolar_etapa4():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_ETAPA4,
    )


MENSAGEM_CONTEXTO_PROFISSAO_INVALIDA_ETAPA4 = (
    "Não consegui entender, por favor me diz novamente, qual sua profissão?"
)


def montar_mensagem_contexto_profissao_invalida_etapa4():
    return MENSAGEM_CONTEXTO_PROFISSAO_INVALIDA_ETAPA4
