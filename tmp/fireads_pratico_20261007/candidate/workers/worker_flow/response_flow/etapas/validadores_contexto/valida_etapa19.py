"""A resposta textual ao repasse inicia a pesquisa, sem interpretar uma nota."""


def validar_etapa19(texto, tipo_mensagem):
    return tipo_mensagem in {"text", "interactive", "interactive_button"} and bool(
        isinstance(texto, str) and texto.strip()
    )
