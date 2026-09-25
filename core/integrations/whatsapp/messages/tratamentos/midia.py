"""Orienta a resposta por texto ou pelos botões que a etapa realmente possui."""

from .composicao import compor_tratamento


MENSAGEM_TRATAMENTO_MIDIA = (
    "Olha ainda não consigo reconhecer áudio e mensagens com mídia, apenas texto. \n\n"

)
MENSAGEM_TRATAMENTO_MIDIA_COM_BOTOES = (
    "Olha ainda não consigo reconhecer áudio e mensagens com mídia, apenas texto. \n\n"

)


def montar_mensagem_tratamento_midia(mensagem_repeticao, *, aceita_botoes=False):
    prefixo = (
        MENSAGEM_TRATAMENTO_MIDIA_COM_BOTOES
        if aceita_botoes
        else MENSAGEM_TRATAMENTO_MIDIA
    )
    return compor_tratamento(prefixo, mensagem_repeticao)
