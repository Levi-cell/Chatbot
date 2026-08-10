from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_reforco_escolar,
)


# ENTRADA NA ETAPA 7 - CLIENTE

MENSAGEM_OFERTA_CLIENTE_ETAPA7 = (
    "Maravilha! ☺️\n\n"
    "Quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"

)


def montar_mensagem_oferta_cliente_etapa7(nome):
    return MENSAGEM_OFERTA_CLIENTE_ETAPA7.format(nome=nome)


# ENTRADA NA ETAPA 7 - DEPENDENTE

MENSAGEM_OFERTA_DEPENDENTE_ETAPA7 = (
    "Maravilha! ☺️\n\n"
    "Quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"

)


def montar_mensagem_oferta_dependente_etapa7(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_ETAPA7.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM MÍDIA

MENSAGEM_OFERTA_CLIENTE_MIDIA_ETAPA7 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá, quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"

)


def montar_mensagem_oferta_cliente_midia_etapa7():
    return MENSAGEM_OFERTA_CLIENTE_MIDIA_ETAPA7


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM MÍDIA

MENSAGEM_OFERTA_DEPENDENTE_MIDIA_ETAPA7 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá, quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"

)


def montar_mensagem_oferta_dependente_midia_etapa7(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_MIDIA_ETAPA7.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM PERGUNTA FINANCEIRA

MENSAGEM_OFERTA_CLIENTE_FINANCEIRO_ETAPA7 = (
    "Olha, demais informações, como valores de investimento, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Mas bora lá, quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"

)


def montar_mensagem_oferta_cliente_financeiro_etapa7():
    return MENSAGEM_OFERTA_CLIENTE_FINANCEIRO_ETAPA7


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_OFERTA_DEPENDENTE_FINANCEIRO_ETAPA7 = (
    "Olha, demais informações, como valores de investimento, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Mas bora lá, quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"

)


def montar_mensagem_oferta_dependente_financeiro_etapa7(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_FINANCEIRO_ETAPA7.format(nome=nome)


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR

MENSAGEM_RETOMADA_OFERTA_CLIENTE_ETAPA7 = (
    "Quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"
)

MENSAGEM_RETOMADA_OFERTA_DEPENDENTE_ETAPA7 = (
    "Quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"
)


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
    "Mas bora lá, quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"

)


def montar_mensagem_oferta_cliente_contexto_invalido_etapa7():
    return MENSAGEM_OFERTA_CLIENTE_CONTEXTO_INVALIDO_ETAPA7


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_OFERTA_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA7 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Mas bora lá, quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"

)


def montar_mensagem_oferta_dependente_contexto_invalido_etapa7(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA7.format(
        nome=nome,
    )


# BOTOES DA ETAPA 7

BOTAO_ETAPA7_QUERO_AGENDAR = "Quero agendar"
BOTAO_ETAPA7_TALVEZ_MAIS_TARDE = "Talvez mais tarde"

BOTOES_ETAPA7 = (
    BOTAO_ETAPA7_QUERO_AGENDAR,
    BOTAO_ETAPA7_TALVEZ_MAIS_TARDE,
)


def montar_botoes_etapa7():
    return BOTOES_ETAPA7
