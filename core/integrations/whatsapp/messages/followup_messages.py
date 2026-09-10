"""Lembrete proativo e saudação da retomada com stage positivo."""

MENSAGEM_FOLLOWUP = "Você viu a minha mensagem?"


def montar_saudacao_retomada_followup(nome=None):
    """Usa somente o nome já persistido, sem interpretar a nova mensagem."""
    nome_normalizado = " ".join(nome.split()) if isinstance(nome, str) else ""
    if nome_normalizado:
        return f"Que bom te ver novamente, {nome_normalizado}!\n\n"
    return "Que bom te ver novamente!\n\n"
