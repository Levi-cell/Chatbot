"""Componentes de apresentação compartilhados pelo fluxo do WhatsApp.

Fora da triagem, o fluxo utiliza somente rodapés pontuais. O cabeçalho
compartilhado permanece restrito à introdução da triagem cognitiva.
"""


CABECALHO_ETAPA9_TRIAGEM = "Triagem cognitiva"

RODAPE_ETAPA1_BOAS_VINDAS = "Seja muito bem-vindo(a)!"
RODAPE_ETAPA6_ESPERA = "Estaremos te esperando!"
RODAPE_OPCAO_UNICA = "Selecione apenas uma opção abaixo."


def montar_texto_com_rodape(mensagem, rodape):
    return f"{mensagem}\n\n_{rodape}_"
