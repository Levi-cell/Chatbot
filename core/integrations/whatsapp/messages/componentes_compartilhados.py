"""Componentes de apresentação compartilhados pelo fluxo do WhatsApp.

Fora da triagem, o fluxo utiliza somente rodapés pontuais. Cabeçalhos
compartilhados identificam a introdução da triagem e a pesquisa final.
"""

# Compatibilidade com consumidores antigos da saudação.
from .tratamentos.retorno_inatividade import (
    INTERVALO_SAUDACAO_RETORNO,
    montar_saudacao_retorno,
)


CABECALHO_ETAPA11_TRIAGEM = "Triagem cognitiva"
CABECALHO_PESQUISA_SATISFACAO = "Pesquisa de satisfação"

RODAPE_ETAPA1_BOAS_VINDAS = "Seja muito bem-vindo(a)!"
RODAPE_ETAPA6_IDADE_AVANCADA = "Nosso time vai orientar os próximos passos. 🧡"
RODAPE_ETAPA8_ESPERA = "Estaremos te esperando!"
RODAPE_OPCAO_UNICA = "Selecione apenas uma opção abaixo."


def montar_texto_com_cabecalho(mensagem, cabecalho):
    """Mantém o cabeçalho no corpo para padronizar sua exibição no WhatsApp."""
    return f"*{cabecalho}*\n\n{mensagem}"


def montar_texto_com_rodape(mensagem, rodape):
    return f"{mensagem}\n\n_{rodape}_"
