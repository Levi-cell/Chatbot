"""Aceita uma única preferência explícita de turno, sem inferir disponibilidade."""

import re
import unicodedata

PADRAO_TURNOS = re.compile(r"\b(manha|tarde|noite)\b")
PADRAO_RECUSA = re.compile(r"\b(nao|n|nunca|nem|sem|nenhum|nenhuma|impossivel)\b")
PADRAO_INDEFINICAO = re.compile(
    r"\b(talvez|qualquer|indiferente|depende|duvida)\b|\btanto faz\b"
)


def validar_etapa18(texto, tipo_mensagem="text"):
    """Retorna o valor persistível, ou None para repetir a escolha.

    Botões usam o próprio título como callback. A grafia 'amanhã' não é
    confundida com o turno 'manhã'. Repetir o mesmo turno não cria dois turnos.
    A presença de negação rejeita a frase inteira, como definido no produto.
    """
    if tipo_mensagem not in {"text", "interactive_button"} or not isinstance(
        texto, str
    ):
        return None
    normalizado = "".join(
        c
        for c in unicodedata.normalize("NFD", texto.casefold())
        if unicodedata.category(c) != "Mn"
    )
    if (
        "?" in texto
        or PADRAO_RECUSA.search(normalizado)
        or PADRAO_INDEFINICAO.search(normalizado)
    ):
        return None
    turnos = set(PADRAO_TURNOS.findall(normalizado))
    return next(iter(turnos)) if len(turnos) == 1 else None
