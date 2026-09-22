"""Saudação reativa de três horas; não interpreta respostas nem decide destinos."""

from datetime import datetime, timedelta

from .composicao import montar_prefixo_retorno


INTERVALO_SAUDACAO_RETORNO = timedelta(hours=3)


def montar_saudacao_retorno(
    nome_titular,
    ultima_mensagem_bot_em,
    mensagem_cliente_atual_em,
    id_etapa_atual,
):
    """O worker usa esta saudação somente no caminho normal sem follow-up pendente."""
    if id_etapa_atual in {None, 1}:
        return None
    nome_titular = " ".join(str(nome_titular or "").split())
    if not nome_titular:
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
    return montar_prefixo_retorno(f"Olá novamente, {nome_titular}!")
