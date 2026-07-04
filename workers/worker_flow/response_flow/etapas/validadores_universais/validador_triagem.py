import unicodedata


TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA = "resposta_triagem_invalida"

RESPOSTA_TRIAGEM_NUNCA = "nunca"
RESPOSTA_TRIAGEM_AS_VEZES = "às vezes"
RESPOSTA_TRIAGEM_FREQUENTEMENTE = "frequentemente"

TIPOS_MENSAGEM_ACEITOS = {
    "button",
    "interactive",
    "text",
}

_RESPOSTAS_ACEITAS = {
    "nunca": RESPOSTA_TRIAGEM_NUNCA,
    "as vezes": RESPOSTA_TRIAGEM_AS_VEZES,
    "frequentemente": RESPOSTA_TRIAGEM_FREQUENTEMENTE,
}


def validar_resposta_triagem(conteudo_texto, tipo_mensagem):
    """
    Retorna a resposta canônica somente quando toda a mensagem é uma opção.

    O webhook coloca o título do botão em conteudo_texto. Assim, botão e texto
    digitado percorrem a mesma regra sem permitir palavras extras.
    """
    if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS:
        return None

    if not isinstance(conteudo_texto, str):
        return None

    texto_normalizado = _normalizar_resposta(conteudo_texto)

    if not texto_normalizado:
        return None

    return _RESPOSTAS_ACEITAS.get(texto_normalizado)


def _normalizar_resposta(texto):
    texto_decomposto = unicodedata.normalize(
        "NFKD",
        texto.strip().casefold(),
    )
    texto_sem_acento = "".join(
        caractere
        for caractere in texto_decomposto
        if not unicodedata.combining(caractere)
    )
    return " ".join(texto_sem_acento.split())
