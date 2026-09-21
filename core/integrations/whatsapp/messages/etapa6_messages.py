from core.validacoes.suporte_por_idade import (
    IDADES_MINIMAS_SUPORTE,
    validar_idade_minima_suporte,
)


from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_financeiro,
    montar_mensagem_tratamento_reforco_escolar,
)


### ENTRADA NA ETAPA 6 - CLIENTE

MENSAGEM_IDADE_ETAPA6 = (
    "Certo, agora me fala, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6():
    return MENSAGEM_IDADE_ETAPA6


### ENTRADA NA ETAPA 6 - DEPENDENTE

MENSAGEM_IDADE_DEPENDENTE_ETAPA6 = (
    "Certo, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM MÍDIA

MENSAGEM_IDADE_ETAPA6_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6_midia():
    return MENSAGEM_IDADE_ETAPA6_MIDIA


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MÍDIA

MENSAGEM_IDADE_DEPENDENTE_ETAPA6_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6_midia(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6_MIDIA.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_ETAPA6_FINANCEIRO = montar_mensagem_tratamento_financeiro(
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6_financeiro():
    return MENSAGEM_IDADE_ETAPA6_FINANCEIRO


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_DEPENDENTE_ETAPA6_FINANCEIRO = montar_mensagem_tratamento_financeiro(
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6_financeiro(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6_FINANCEIRO.format(nome=nome)


### CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR

MENSAGEM_RETOMADA_IDADE_ETAPA6 = "Me diz, qual é a sua idade?"
MENSAGEM_RETOMADA_IDADE_DEPENDENTE_ETAPA6 = (
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_etapa6_reforco_escolar():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_IDADE_ETAPA6,
    )


def montar_mensagem_idade_dependente_etapa6_reforco_escolar(nome):
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_IDADE_DEPENDENTE_ETAPA6.format(nome=nome),
    )


### CLIENTE RESPONDE À IDADE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA6 = (
    "Não consegui entender a sua idade. Digite apenas o número, exemplo: 25.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_contexto_idade_invalida_etapa6():
    return MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA6


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA6 = (
    "Não consegui entender a idade de {nome}. Digite apenas o número, "
    "exemplo: 10.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_contexto_idade_dependente_invalida_etapa6(nome):
    return MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA6.format(
        nome=nome,
    )


### CLIENTE COM MENOS DE 18 ANOS

MENSAGEM_CLIENTE_MENOR_18_ETAPA6 = (
    "Como você tem menos de 18 anos, este atendimento precisa ser realizado "
    "por um adulto responsável.\n\n"
    "Peça a um adulto para retornar nosso atendimento.\n"
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_cliente_menor_18_etapa6():
    return MENSAGEM_CLIENTE_MENOR_18_ETAPA6


### DEPENDENTE ABAIXO DA IDADE MINIMA DA UNIDADE

MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6 = (
    "No momento, esta unidade do Supera realiza treinamentos com crianças a "
    "partir de {idade_minima} anos. Quando {nome} completar {idade_minima} "
    "anos, você poderá entrar em contato "
    "novamente.\n\n"
    "Um abraço e até logo! 👋☺️"

)


def montar_mensagem_dependente_menor_5_etapa6(
    nome,
    idade_minima=5,
):
    return MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6.format(
        nome=nome,
        idade_minima=idade_minima,
    )


### CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS

MENSAGEM_IDADE_ACIMA_99_ETAPA6 = (
    "Entendi. Olha, para idades muito avançadas, é melhor falar com nossa "
    "consultora especializada. Vou te passar o contato dela para continuar "
    "o atendimento, tudo bem?\n\n"
    "Basta clicar no botão abaixo."
)

BOTAO_FALAR_COM_CONSULTORA_ETAPA6 = "Falar com Consultora"


def montar_mensagem_idade_acima_99_etapa6():
    return MENSAGEM_IDADE_ACIMA_99_ETAPA6


def montar_botao_idade_acima_99_etapa6():
    return BOTAO_FALAR_COM_CONSULTORA_ETAPA6


### TITULAR A PARTIR DO LIMITE CONFIGURADO ATÉ 99 ANOS

MENSAGEM_SUPORTE_IDOSO_ETAPA6 = (
    "Certo, olha, para idades mais avançadas oferecemos um atendimento "
    "personalizado com o nosso time! 😊\n\n"
    "Para entrar em contato, basta clicar no botão abaixo."
)

BOTAO_SUPORTE_IDOSO_ETAPA6 = "Falar agora"

# Apenas para reconhecer respostas já enviadas antes da troca de texto.
# Novos envios usam sempre MENSAGEM_SUPORTE_IDOSO_ETAPA6.
_MENSAGEM_SUPORTE_IDOSO_LEGADA = (
    "Entendi. Para oferecer um atendimento mais adequado, esta unidade "
    "realiza o suporte a clientes com {idade_minima} anos ou mais diretamente com a "
    "nossa equipe comercial.\n\n"
    "Vou te passar o contato para continuar o atendimento. Basta clicar "
    "no botão abaixo."
)

def montar_mensagem_suporte_idoso_etapa6(idade_minima):
    validar_idade_minima_suporte(idade_minima)
    if idade_minima is None:
        raise ValueError("Não há mensagem de suporte para política desativada")
    return MENSAGEM_SUPORTE_IDOSO_ETAPA6


def montar_botao_suporte_idoso_etapa6():
    return BOTAO_SUPORTE_IDOSO_ETAPA6


def montar_mensagem_contato_suporte_idoso_etapa6(
    *, nome_agente, genero_agente, nome_cliente, idade_cliente,
):
    """Texto pré-preenchido do titular, usando a idade validada nesta resposta."""
    artigo = {"feminino": "a", "masculino": "o"}.get(genero_agente)
    if artigo is None:
        raise ValueError("Gênero do agente inválido para contato comercial")
    if any(
        not isinstance(nome, str) or not nome.strip()
        for nome in (nome_agente, nome_cliente)
    ):
        raise ValueError("Nome do agente e do cliente são necessários")
    if type(idade_cliente) is not int or not 50 <= idade_cliente <= 99:
        raise ValueError("Idade do titular inválida para suporte por idade")
    return (
        f"Olá, vim do atendimento com {artigo} {nome_agente.strip()}, "
        f"me chamo {nome_cliente.strip()}, tenho {idade_cliente} anos "
        "e gostaria de reservar uma demonstração prática."
    )


def reconhecer_mensagem_suporte_idoso_etapa6(conteudo):
    """Reconhece o corpo atual ou legado, inclusive após uma saudação."""
    texto = str(conteudo or "").strip()
    mensagens = (MENSAGEM_SUPORTE_IDOSO_ETAPA6,) + tuple(
        _MENSAGEM_SUPORTE_IDOSO_LEGADA.format(idade_minima=limite)
        for limite in IDADES_MINIMAS_SUPORTE
    )
    return texto.endswith(mensagens)
