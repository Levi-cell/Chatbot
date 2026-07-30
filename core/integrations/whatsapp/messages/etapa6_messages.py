# ENTRADA NA ETAPA 6 - CLIENTE

MENSAGEM_OFERTA_CLIENTE_ETAPA6 = (
    "Maravilha! ☺️\n\n"
    "Quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_cliente_etapa6(nome):
    return MENSAGEM_OFERTA_CLIENTE_ETAPA6.format(nome=nome)


# ENTRADA NA ETAPA 6 - DEPENDENTE

MENSAGEM_OFERTA_DEPENDENTE_ETAPA6 = (
    "Maravilha! ☺️\n\n"
    "Quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_dependente_etapa6(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_ETAPA6.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM MÍDIA

MENSAGEM_OFERTA_CLIENTE_MIDIA_ETAPA6 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá, quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_cliente_midia_etapa6():
    return MENSAGEM_OFERTA_CLIENTE_MIDIA_ETAPA6


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM MÍDIA

MENSAGEM_OFERTA_DEPENDENTE_MIDIA_ETAPA6 = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n\n"
    "Mas bora lá, quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_dependente_midia_etapa6(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_MIDIA_ETAPA6.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM PERGUNTA FINANCEIRA

MENSAGEM_OFERTA_CLIENTE_FINANCEIRO_ETAPA6 = (
    "Olha, demais informações, como valores, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Mas bora lá, quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_cliente_financeiro_etapa6():
    return MENSAGEM_OFERTA_CLIENTE_FINANCEIRO_ETAPA6


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_OFERTA_DEPENDENTE_FINANCEIRO_ETAPA6 = (
    "Olha, demais informações, como valores, são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n\n"
    "Mas bora lá, quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_dependente_financeiro_etapa6(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_FINANCEIRO_ETAPA6.format(nome=nome)


# CLIENTE RESPONDE À OFERTA COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_OFERTA_CLIENTE_CONTEXTO_INVALIDO_ETAPA6 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Mas bora lá, quero te presentear com uma experiência que pode fazer toda a diferença "
    "no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, você fará "
    "uma avaliação que vai mostrar como estão habilidades importantes para o "
    "seu dia a dia, como: memória, atenção, concentração e raciocínio lógico."
    "\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_cliente_contexto_invalido_etapa6():
    return MENSAGEM_OFERTA_CLIENTE_CONTEXTO_INVALIDO_ETAPA6


# CLIENTE RESPONDE À OFERTA DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_OFERTA_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA6 = (
    "Não consegui entender a sua mensagem.\n\n"
    "Mas bora lá, quero presentear {nome} com uma experiência que pode fazer toda a "
    "diferença no seu desenvolvimento.\n\n"
    "Além de participar de uma Aula Exclusiva totalmente gratuita, {nome} "
    "fará uma avaliação que vai mostrar como estão habilidades importantes "
    "para o seu dia a dia, como: memória, atenção, concentração e raciocínio "
    "lógico.\n\n"
    "Vamos agendar?"
)


def montar_mensagem_oferta_dependente_contexto_invalido_etapa6(nome):
    return MENSAGEM_OFERTA_DEPENDENTE_CONTEXTO_INVALIDO_ETAPA6.format(
        nome=nome,
    )


# BOTOES DA ETAPA 6

BOTAO_ETAPA6_QUERO_AGENDAR = "Quero agendar"
BOTAO_ETAPA6_TALVEZ_MAIS_TARDE = "Talvez mais tarde"

BOTOES_ETAPA6 = (
    BOTAO_ETAPA6_QUERO_AGENDAR,
    BOTAO_ETAPA6_TALVEZ_MAIS_TARDE,
)


def montar_botoes_etapa6():
    return BOTOES_ETAPA6
