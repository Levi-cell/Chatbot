"""Saudação da reação ao follow-up; o worker escolhe a repetição sem transição."""

from .composicao import montar_prefixo_retorno


def montar_saudacao_retomada_followup(nome_titular=None):
    """Recebe apenas o nome autorizado pelo worker; na etapa 1 ele passa None."""
    nome_titular = " ".join(nome_titular.split()) if isinstance(nome_titular, str) else ""
    saudacao = (
        f"Que bom te ver novamente, {nome_titular}!"
        if nome_titular
        else "Que bom te ver novamente!"
    )
    return montar_prefixo_retorno(saudacao)
