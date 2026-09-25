"""Saudação da reação ao follow-up; o worker valida a resposta da etapa."""

MENSAGEM_RETORNO_FOLLOWUP_SEM_NOME = "Bom te ver novamente ☺️\n\n"
MENSAGEM_RETORNO_FOLLOWUP_COM_NOME = "Bom te ver novamente, {nome_titular} ☺️\n\n"


def montar_saudacao_retomada_followup(nome_titular=None):
    """Recebe apenas o nome autorizado pelo worker; na etapa 1 ele passa None."""
    nome_titular = " ".join(nome_titular.split()) if isinstance(nome_titular, str) else ""
    mensagem = (
        MENSAGEM_RETORNO_FOLLOWUP_COM_NOME
        if nome_titular
        else MENSAGEM_RETORNO_FOLLOWUP_SEM_NOME
    )
    return mensagem.format(nome_titular=nome_titular)
