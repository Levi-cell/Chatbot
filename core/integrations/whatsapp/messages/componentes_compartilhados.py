"""Componentes de apresentação compartilhados pelo fluxo do WhatsApp.

Fora da triagem, o fluxo utiliza somente rodapés pontuais. Cabeçalhos
compartilhados identificam a introdução da triagem e a pesquisa final.
"""


CABECALHO_ETAPA9_TRIAGEM = "Triagem cognitiva"
CABECALHO_PESQUISA_SATISFACAO = "Pesquisa de satisfação"

RODAPE_ETAPA1_BOAS_VINDAS = "Seja muito bem-vindo(a)!"
RODAPE_ETAPA6_ESPERA = "Estaremos te esperando!"
RODAPE_OPCAO_UNICA = "Selecione apenas uma opção abaixo."


def montar_texto_com_cabecalho(mensagem, cabecalho):
    """Mantém o cabeçalho no corpo para padronizar sua exibição no WhatsApp."""
    return f"*{cabecalho}*\n\n{mensagem}"


def montar_texto_com_rodape(mensagem, rodape):
    return f"{mensagem}\n\n_{rodape}_"
