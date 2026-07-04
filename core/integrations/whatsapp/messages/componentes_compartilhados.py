"""
Componentes de apresentação compartilhados entre diferentes etapas.

Mensagens interativas usam cabeçalho e rodapé reais da Meta. Mensagens de texto
simples não possuem esses campos; nelas, este módulo reproduz a hierarquia
visual no próprio corpo usando a formatação aceita pelo WhatsApp.
"""


CABECALHO_ETAPA1_SAUDACAO = "Saudação"
CABECALHO_ETAPA2_ATENDIMENTO = "Para quem é o atendimento?"
CABECALHO_ETAPA7_RETORNO = "Bem-vindo(a) de volta!"
CABECALHO_ETAPA9_TRIAGEM = "Triagem cognitiva"

RODAPE_ETAPA1_BOAS_VINDAS = "Seja muito bem-vindo(a)!"
RODAPE_ETAPA6_ESPERA = "Estaremos te esperando!"
RODAPE_OPCAO_UNICA = "Selecione apenas uma opção abaixo."
RODAPE_TRATAMENTO_TEXTO = (
    "responda apenas à mensagem mais recente e envie uma resposta "
    "por vez."
)


def montar_texto_com_cabecalho(mensagem, cabecalho):
    return f"*{cabecalho}*\n\n{mensagem}"


def montar_texto_com_rodape(mensagem, rodape):
    return f"{mensagem}\n\n_{rodape}_"


def montar_texto_com_cabecalho_e_rodape(
    mensagem,
    cabecalho,
    rodape,
):
    mensagem_com_cabecalho = montar_texto_com_cabecalho(
        mensagem,
        cabecalho,
    )
    return montar_texto_com_rodape(
        mensagem_com_cabecalho,
        rodape,
    )
