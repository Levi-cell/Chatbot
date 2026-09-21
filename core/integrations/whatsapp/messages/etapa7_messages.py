from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_financeiro,
    montar_mensagem_tratamento_reforco_escolar,
)


# Convite compartilhado pelas variantes; os tratamentos só acrescentam o aviso.
_CONVITE_CLIENTE_ETAPA7 = (
    "Gostaria de te convidar para uma *demonstração prática exclusiva* na nossa "
    "unidade.\n"
    "\n"
    "Você também participará de uma avaliação para conhecer melhor suas "
    "habilidades de memória, atenção, concentração e raciocínio lógico.\n"
    "\n"
    "Vamos reservar o melhor dia e horário para sua *experiência Supera gratuita*?"
)

_CONVITE_DEPENDENTE_ETAPA7 = (
    "Gostaria de convidar {nome} para receber uma *demonstração prática exclusiva* na "
    "nossa unidade.\n"
    "\n"
    "{nome} também participará de uma avaliação para conhecer melhor as "
    "habilidades de memória, atenção, concentração e raciocínio lógico.\n"
    "\n"
    "Vamos reservar o melhor dia e horário para a *experiência Supera gratuita* de {nome}?"
)


# ENTRADA NA ETAPA 7 - CLIENTE

MENSAGEM_OFERTA_CLIENTE_ETAPA7 = _CONVITE_CLIENTE_ETAPA7


def montar_mensagem_oferta_cliente_etapa7(nome):
    return MENSAGEM_OFERTA_CLIENTE_ETAPA7.format(nome=nome)


# ENTRADA NA ETAPA 7 - DEPENDENTE

MENSAGEM_OFERTA_DEPENDENTE_ETAPA7 = _CONVITE_DEPENDENTE_ETAPA7


def montar_mensagem_oferta_dependente_etapa7(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_ETAPA7.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM MÍDIA

MENSAGEM_OFERTA_CLIENTE_MIDIA_ETAPA7 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    + _CONVITE_CLIENTE_ETAPA7
)


def montar_mensagem_oferta_cliente_midia_etapa7():
    return MENSAGEM_OFERTA_CLIENTE_MIDIA_ETAPA7


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM MÍDIA

MENSAGEM_OFERTA_DEPENDENTE_MIDIA_ETAPA7 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    + _CONVITE_DEPENDENTE_ETAPA7
)


def montar_mensagem_oferta_dependente_midia_etapa7(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_MIDIA_ETAPA7.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM PERGUNTA FINANCEIRA

MENSAGEM_OFERTA_CLIENTE_FINANCEIRO_ETAPA7 = montar_mensagem_tratamento_financeiro(
    "Vamos *reservar* o melhor dia e horário para sua experiência?"
)


def montar_mensagem_oferta_cliente_financeiro_etapa7():
    return MENSAGEM_OFERTA_CLIENTE_FINANCEIRO_ETAPA7


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_OFERTA_DEPENDENTE_FINANCEIRO_ETAPA7 = montar_mensagem_tratamento_financeiro(
    "Vamos *reservar* o melhor dia e horário para a experiência de {nome}?"
)


def montar_mensagem_oferta_dependente_financeiro_etapa7(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_FINANCEIRO_ETAPA7.format(nome=nome)


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR

MENSAGEM_RETOMADA_OFERTA_CLIENTE_ETAPA7 = _CONVITE_CLIENTE_ETAPA7

MENSAGEM_RETOMADA_OFERTA_DEPENDENTE_ETAPA7 = _CONVITE_DEPENDENTE_ETAPA7


def montar_mensagem_oferta_cliente_reforco_escolar_etapa7():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_OFERTA_CLIENTE_ETAPA7,
    )


def montar_mensagem_oferta_dependente_reforco_escolar_etapa7(nome):
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_OFERTA_DEPENDENTE_ETAPA7.format(nome=nome),
    )


# CLIENTE RESPONDE À OFERTA COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_OFERTA_CLIENTE_CONTEXTO_INVALIDO_ETAPA7 = (
    "Não consegui entender a sua mensagem.\n\n"
    + _CONVITE_CLIENTE_ETAPA7
)


def montar_mensagem_oferta_cliente_contexto_invalido_etapa7():
    return MENSAGEM_OFERTA_CLIENTE_CONTEXTO_INVALIDO_ETAPA7


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_OFERTA_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA7 = (
    "Não consegui entender a sua mensagem.\n\n"
    + _CONVITE_DEPENDENTE_ETAPA7
)


def montar_mensagem_oferta_dependente_contexto_invalido_etapa7(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA7.format(
        nome=nome,
    )


# BOTOES DA ETAPA 7

BOTAO_ETAPA7_QUERO_AGENDAR = "Quero reservar"
BOTAO_ETAPA7_TALVEZ_MAIS_TARDE = "Talvez mais tarde"

BOTOES_ETAPA7 = (
    BOTAO_ETAPA7_QUERO_AGENDAR,
    BOTAO_ETAPA7_TALVEZ_MAIS_TARDE,
)


def montar_botoes_etapa7():
    return BOTOES_ETAPA7
