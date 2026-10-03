"""Escolha de turno: padrão, repetição e tratamentos compartilhados."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.tratamentos.composicao import (
    compor_mensagem_inicial,
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

MENSAGEM_REPETICAO_ETAPA18 = "Qual turno fica melhor para reservar {participante}?"
# A orientação completa pertence somente à entrada; tratamentos retomam a pergunta.
ORIENTACAO_ESCOLHA_UNICA_ETAPA18 = (
    "\n\n"
    "Mesmo que você possa em mais de um turno, escolha o de sua preferência. "
    "Se precisar corrigir depois, basta combinar com nosso consultor."
)
MENSAGEM_PADRAO_ETAPA18 = compor_mensagem_inicial(
    "Agradeço por responder às perguntas! ☺️\n\n",
    MENSAGEM_REPETICAO_ETAPA18 + ORIENTACAO_ESCOLHA_UNICA_ETAPA18,
)


def montar_botoes_etapa18():
    return ["Pela manhã", "Pela tarde", "Pela noite"]


def montar_mensagem_etapa18(nome_dependente=None, *, tratamento=None, repeticao=False):
    participante = (
        f"o *momento Supera* de {nome_dependente}"
        if nome_dependente
        else "seu *momento Supera*"
    )
    pergunta = MENSAGEM_REPETICAO_ETAPA18.format(participante=participante)
    if tratamento == "financeiro":
        texto = montar_mensagem_tratamento_financeiro(pergunta)
    elif tratamento == "reforco_escolar":
        texto = montar_mensagem_tratamento_reforco_escolar(pergunta)
    elif tratamento == "midia":
        texto = montar_mensagem_tratamento_midia(pergunta, aceita_botoes=True)
    elif tratamento == "contexto_invalido":
        texto = "Para continuar, escolha apenas um turno."
    elif tratamento is None:
        texto = (
            pergunta
            if repeticao
            else MENSAGEM_PADRAO_ETAPA18.format(participante=participante)
        )
    else:
        raise ValueError("Tratamento desconhecido para escolha de turno")
    return montar_texto_com_rodape(texto, RODAPE_OPCAO_UNICA)
