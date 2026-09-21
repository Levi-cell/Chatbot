"""Lembrete proativo e saudação da retomada com stage positivo."""

MENSAGEM_FOLLOWUP = "Você viu a minha mensagem?"


def montar_saudacao_retomada_followup(nome=None):
    """Formata o nome autorizado pelo worker; na etapa 1 ele deve passar None."""
    nome_normalizado = " ".join(nome.split()) if isinstance(nome, str) else ""
    if nome_normalizado:
        return f"Que bom te ver novamente, {nome_normalizado}!\n\n"
    return "Que bom te ver novamente!\n\n"
