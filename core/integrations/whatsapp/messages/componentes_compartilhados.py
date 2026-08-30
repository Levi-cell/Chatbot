"""Componentes de apresentação compartilhados pelo fluxo do WhatsApp.

Fora da triagem, o fluxo utiliza somente rodapés pontuais. Cabeçalhos
compartilhados identificam a introdução da triagem e a pesquisa final.
"""

from datetime import datetime, timedelta


CABECALHO_ETAPA11_TRIAGEM = "Triagem cognitiva"
CABECALHO_PESQUISA_SATISFACAO = "Pesquisa de satisfação"

RODAPE_ETAPA1_BOAS_VINDAS = "Seja muito bem-vindo(a)!"
RODAPE_ETAPA8_ESPERA = "Estaremos te esperando!"
RODAPE_OPCAO_UNICA = "Selecione apenas uma opção abaixo."

INTERVALO_SAUDACAO_RETORNO = timedelta(hours=3)


def montar_texto_com_cabecalho(mensagem, cabecalho):
    """Mantém o cabeçalho no corpo para padronizar sua exibição no WhatsApp."""
    return f"*{cabecalho}*\n\n{mensagem}"


def montar_texto_com_rodape(mensagem, rodape):
    return f"{mensagem}\n\n_{rodape}_"


def montar_saudacao_retorno(
    nome_cliente,
    ultima_mensagem_bot_em,
    mensagem_cliente_atual_em,
    id_etapa_atual,
):
    """Monta a saudação após três horas sem resposta do cliente.

    A etapa 1 fica fora da regra porque o nome ainda não foi confirmado para
    a conversa atual. Timestamps ausentes ou incompatíveis não podem impedir
    o fluxo principal; nesses casos, a saudação simplesmente não é aplicada.
    """
    if id_etapa_atual in {None, 1}:
        return None

    nome_normalizado = " ".join(str(nome_cliente or "").split())
    if not nome_normalizado:
        return None

    if not isinstance(ultima_mensagem_bot_em, datetime):
        return None

    if not isinstance(mensagem_cliente_atual_em, datetime):
        return None

    try:
        intervalo = mensagem_cliente_atual_em - ultima_mensagem_bot_em
    except TypeError:
        return None

    if intervalo < INTERVALO_SAUDACAO_RETORNO:
        return None

    return f"Olá novamente, {nome_normalizado}!\n\n"
