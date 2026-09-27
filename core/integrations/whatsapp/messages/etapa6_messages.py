"""Etapa 6: idade do participante e saídas por política da unidade."""

import re

from core.validacoes.suporte_por_idade import (
    validar_idade_minima_suporte,
)

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_ETAPA6_IDADE_AVANCADA,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.tratamentos.financeiro import (
    montar_mensagem_tratamento_financeiro,
)
from core.integrations.whatsapp.messages.tratamentos.midia import (
    montar_mensagem_tratamento_midia,
)
from core.integrations.whatsapp.messages.tratamentos.reforco_escolar import (
    montar_mensagem_tratamento_reforco_escolar,
)


### PERGUNTA INICIAL DE IDADE: CLIENTE
MENSAGEM_PADRAO_CLIENTE = "Agora me conta, *qual é a sua idade*? ☺️"

### REPETIÇÃO DA IDADE: CLIENTE, SEM A ABERTURA INICIAL
MENSAGEM_REPETICAO_CLIENTE = "Me diz, qual é a sua idade?"


def montar_mensagem_idade_etapa6(*, repeticao=False):
    mensagem = MENSAGEM_REPETICAO_CLIENTE if repeticao else MENSAGEM_PADRAO_CLIENTE
    return mensagem


### TRATAMENTOS DO CLIENTE: ORIENTAÇÃO + REPETIÇÃO DA IDADE
def montar_mensagem_idade_etapa6_financeiro():
    return montar_mensagem_tratamento_financeiro(MENSAGEM_REPETICAO_CLIENTE)


def montar_mensagem_idade_etapa6_midia():
    return montar_mensagem_tratamento_midia(MENSAGEM_REPETICAO_CLIENTE)


def montar_mensagem_idade_etapa6_reforco_escolar():
    return montar_mensagem_tratamento_reforco_escolar(MENSAGEM_REPETICAO_CLIENTE)


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_idade_invalida_etapa6():
    return (
        "Olha, não consegui entender a sua idade. "
        "Digite apenas o número, exemplo: 25."
    )


### PERGUNTA INICIAL DE IDADE: DEPENDENTE
MENSAGEM_PADRAO_DEPENDENTE = "E qual é a *idade de {nome_dependente}*? ☺️"

### REPETIÇÃO DA IDADE: DEPENDENTE, SEM A ABERTURA INICIAL
MENSAGEM_REPETICAO_DEPENDENTE = "Me diz, qual é a idade de {nome_dependente}?"


def montar_mensagem_idade_dependente_etapa6(nome_dependente, *, repeticao=False):
    mensagem = (
        MENSAGEM_REPETICAO_DEPENDENTE if repeticao else MENSAGEM_PADRAO_DEPENDENTE
    )
    return mensagem.format(nome_dependente=nome_dependente)


### TRATAMENTOS DO DEPENDENTE: ORIENTAÇÃO + REPETIÇÃO DA IDADE
def montar_mensagem_idade_dependente_etapa6_financeiro(nome_dependente):
    return montar_mensagem_tratamento_financeiro(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


def montar_mensagem_idade_dependente_etapa6_midia(nome_dependente):
    return montar_mensagem_tratamento_midia(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


def montar_mensagem_idade_dependente_etapa6_reforco_escolar(nome_dependente):
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_REPETICAO_DEPENDENTE.format(nome_dependente=nome_dependente)
    )


### CONTEXTO INVÁLIDO: MENSAGEM PRÓPRIA, SEM CONCATENAR A REPETIÇÃO
def montar_mensagem_contexto_idade_dependente_invalida_etapa6(nome_dependente):
    return (
        f"Olha, não consegui entender a idade de {nome_dependente}. "
        "Digite apenas o número, exemplo: 10."
    )


### CLIENTE COM MENOS DE 18 ANOS

MENSAGEM_CLIENTE_MENOR_18_ETAPA6 = (
    "Como você tem menos de 18 anos, este atendimento precisa ser realizado "
    "por um adulto responsável.\n"
    "Peça a um adulto para retornar nosso atendimento. "
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_cliente_menor_18_etapa6():
    return MENSAGEM_CLIENTE_MENOR_18_ETAPA6


### DEPENDENTE ABAIXO DA IDADE MINIMA DA UNIDADE

MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6 = (
    "No momento, esta unidade do Supera realiza treinamentos com crianças a "
    "partir de {idade_minima} anos. Quando {nome_dependente} completar {idade_minima} "
    "anos, você poderá entrar em contato "
    "novamente.\n"
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_dependente_menor_5_etapa6(
    nome_dependente,
    idade_minima=5,
):
    return MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6.format(
        nome_dependente=nome_dependente,
        idade_minima=idade_minima,
    )


### ENCAMINHAMENTO DO TITULAR PELA FAIXA CONFIGURADA NA UNIDADE
MENSAGEM_SUPORTE_IDOSO_ETAPA6 = (
    "Certo, vou te passar o contato da nossa equipe para dar continuidade a sua experiência supera! 😊\n"
    "Para entrar em contato, basta clicar no botão abaixo."
)


### CLIENTE OU DEPENDENTE COM 90 ANOS OU MAIS
# Nomes antigos preservados como contrato de importação; o corte fica no resolver.
# Regra geral, inclusive quando idade_minima_suporte está desativada.
# Mensagem própria: orienta o contato com o consultor sem repetir a pergunta de idade.
# A redação atende às duas rotas sem presumir que quem conversa é o participante.
MENSAGEM_IDADE_ACIMA_99_ETAPA6 = (
    "Certo, olha, para idades mais avançadas vamos precisar realizar uma pequena "
    "*anamnese* com um dos nossos consultores.\n"
    "Basta clicar no botão abaixo para falar com nosso time e iniciar a anamnese! 😊"
)

BOTAO_FALAR_COM_CONSULTORA_ETAPA6 = "Falar com Consultor"


def montar_mensagem_idade_acima_99_etapa6():
    return montar_texto_com_rodape(
        MENSAGEM_IDADE_ACIMA_99_ETAPA6,
        RODAPE_ETAPA6_IDADE_AVANCADA,
    )


def montar_botao_idade_acima_99_etapa6():
    return BOTAO_FALAR_COM_CONSULTORA_ETAPA6


### TITULAR A PARTIR DO LIMITE CONFIGURADO ATÉ 89 ANOS

BOTAO_SUPORTE_IDOSO_ETAPA6 = "Falar agora"


def montar_mensagem_suporte_idoso_etapa6(idade_minima):
    validar_idade_minima_suporte(idade_minima)
    if idade_minima is None:
        raise ValueError("Não há mensagem de suporte para política desativada")
    return MENSAGEM_SUPORTE_IDOSO_ETAPA6


def montar_botao_suporte_idoso_etapa6():
    return BOTAO_SUPORTE_IDOSO_ETAPA6


### TEXTO PRONTO NO WHATSAPP COMERCIAL: ORIGEM + PEDIDO DO PARTICIPANTE
MENSAGEM_ORIGEM_CONTATO_COMERCIAL_ETAPA6 = (
    "Olá, vim do atendimento com {artigo} {nome_agente}, "
    "chatbot da unidade {nome_unidade}."
)
MENSAGEM_PEDIDO_COMERCIAL_TITULAR_ETAPA6 = (
    "Me chamo {nome_titular}, tenho {idade_participante} anos "
    "e gostaria de reservar minha experiência Supera gratuita."
)
MENSAGEM_PEDIDO_COMERCIAL_DEPENDENTE_ETAPA6 = (
    "Me chamo {nome_titular} e gostaria de reservar uma experiência Supera gratuita "
    "para {nome_dependente}, que tem {idade_participante} anos."
)


def montar_mensagem_contato_comercial_etapa6(
    *,
    nome_agente,
    genero_agente,
    nome_unidade,
    nome_titular,
    idade_participante,
    status_dependente,
    nome_dependente=None,
):
    """Identifica origem e participante usando a idade informada nesta resposta.

    A elegibilidade do encaminhamento pertence ao worker. Na rota de dependente,
    a idade é do participante, nunca do cliente que está conversando com o bot.
    """
    artigo = {"feminino": "a", "masculino": "o"}.get(genero_agente)
    if artigo is None:
        raise ValueError("Gênero do agente inválido para contato comercial")
    if any(
        not isinstance(valor, str) or not valor.strip()
        for valor in (nome_agente, nome_unidade, nome_titular)
    ):
        raise ValueError("Nome do agente, da unidade e do cliente são necessários")
    if type(status_dependente) is not bool:
        raise ValueError("Rota do participante inválida para contato comercial")
    if status_dependente and (
        not isinstance(nome_dependente, str) or not nome_dependente.strip()
    ):
        raise ValueError("Nome do dependente é necessário para contato comercial")
    if type(idade_participante) is not int or idade_participante <= 0:
        raise ValueError("Idade do participante inválida para contato comercial")

    origem = MENSAGEM_ORIGEM_CONTATO_COMERCIAL_ETAPA6.format(
        artigo=artigo,
        nome_agente=nome_agente.strip(),
        nome_unidade=nome_unidade.strip(),
    )
    pedido = (
        MENSAGEM_PEDIDO_COMERCIAL_DEPENDENTE_ETAPA6
        if status_dependente
        else MENSAGEM_PEDIDO_COMERCIAL_TITULAR_ETAPA6
    ).format(
        nome_titular=nome_titular.strip(),
        nome_dependente=nome_dependente.strip() if status_dependente else None,
        idade_participante=idade_participante,
    )
    return f"{origem} {pedido}"


### COMPATIBILIDADE DE RECUPERAÇÃO COM A VERSÃO AINDA EM PRODUÇÃO
# Texto emitido pela versão 701b834; nunca usar em novos envios desta versão.
# Enquanto o próximo deploy não ocorrer, novas entradas podem receber esse corpo.
# O retry o reconhece para concluir o encerramento sem reenviar a resposta.
# Remover somente depois da troca de versão e da checagem de suas pendências.
_MENSAGEM_SUPORTE_IDOSO_LEGADA_SEM_FAIXA = (
    "Certo, olha, para idades mais avançadas oferecemos um atendimento "
    "personalizado com o nosso time! 😊\n\n"
    "Para entrar em contato, basta clicar no botão abaixo."
)


def reconhecer_mensagem_suporte_idoso_etapa6(conteudo):
    """Reconhece resposta já persistida; não monta nem envia mensagem ao cliente."""
    texto = str(conteudo or "").strip()
    mensagens = (
        MENSAGEM_SUPORTE_IDOSO_ETAPA6,
        # Recuperação de envios anteriores à revisão de espaçamento; não reenviar.
        MENSAGEM_SUPORTE_IDOSO_ETAPA6.replace("\n", "\n\n"),
        _MENSAGEM_SUPORTE_IDOSO_LEGADA_SEM_FAIXA,
    )
    # O prefixo de retorno pode anteceder o corpo salvo; não interpretar como envio novo.
    return texto.endswith(mensagens)


def reconhecer_encerramento_etapa6(conteudo, tipo_mensagem):
    """Identifica somente corpos conhecidos; espaços e prefixos não mudam a decisão.

    O chamador deve comprovar a conversa, a etapa e o vínculo com a entrada.
    Esta função não consulta configurações nem altera a formatação dos envios.
    """
    texto = " ".join(str(conteudo or "").split())

    def termina_com(corpo):
        return texto.endswith(" ".join(corpo.split()))

    if tipo_mensagem == "interactive_cta_url":
        if any(termina_com(corpo) for corpo in (
            MENSAGEM_SUPORTE_IDOSO_ETAPA6,
            _MENSAGEM_SUPORTE_IDOSO_LEGADA_SEM_FAIXA,
        )):
            return {"categoria": "suporte"}
        universal = montar_mensagem_idade_acima_99_etapa6()
        if any(termina_com(corpo) for corpo in (
            universal,
            universal.replace(" e iniciar a anamnese", ""),
        )):
            return {"categoria": "universal"}
        return None

    if tipo_mensagem != "text":
        return None
    if termina_com(MENSAGEM_CLIENTE_MENOR_18_ETAPA6):
        return {"categoria": "titular_menor"}

    # O mínimo aparece duas vezes no corpo. A referência exige que sejam iguais.
    modelo = " ".join(MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6.split())
    padrao = re.escape(modelo)
    padrao = padrao.replace(re.escape("{idade_minima}"), r"(?P<minimo>[45])", 1)
    padrao = padrao.replace(re.escape("{idade_minima}"), r"(?P=minimo)")
    padrao = padrao.replace(re.escape("{nome_dependente}"), r"(?P<nome>.+?)")
    encontrado = re.search(padrao + r"$", texto)
    if encontrado:
        return {
            "categoria": "dependente_menor",
            "idade_minima": int(encontrado.group("minimo")),
            "nome_dependente": encontrado.group("nome"),
        }
    return None
