"""Saudação da reação ao follow-up; o worker valida a resposta da etapa."""

MENSAGEM_RETORNO_FOLLOWUP_SEM_NOME = "Bom te ver novamente ☺️\n\n"


def montar_saudacao_retomada_followup(nome_titular=None):
    """Mantém a assinatura dos chamadores, mas a saudação nunca inclui o nome."""
    return MENSAGEM_RETORNO_FOLLOWUP_SEM_NOME
