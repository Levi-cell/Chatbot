"""Identifica pedidos de apresentação; não valida nomes nem autoriza transições.

O resolver usa este classificador somente no primeiro texto da conversa,
depois de mídia, reforço escolar e financeiro. Correspondência completa evita
que uma palavra solta ou um assunto diferente acione a explicação do Supera.
"""

import re
import unicodedata


# Referências genéricas são suficientes no primeiro contato com o chatbot.
_REFERENCIA = (
    r"(?:(?:o\s+)?(?:(?:metodo|curso|programa)\s+)?supera|"
    r"isso|isto|esse\s+(?:curso|programa|metodo)|essa\s+experiencia|voces)"
)
_ASSUNTO = rf"(?:(?:sobre|a\s+respeito\s+de|do|da|de)\s+{_REFERENCIA})"
_PERGUNTA = (
    rf"(?:(?:o\s+que|oque|oq|que|q)\s+(?:e|eh)(?:\s+{_REFERENCIA})?|"
    rf"(?:do\s+que|de\s+que|sobre\s+o\s+que|do\s+q)\s+se\s+trata"
    rf"(?:\s+{_REFERENCIA})?|"
    rf"como\s+(?:e\s+que\s+)?funciona(?:\s+{_REFERENCIA})?)"
)
_INTENCAO = (
    r"(?:(?:eu\s+)?(?:tenho\s+interesse\s+e\s+)?(?:quero|queria|gostaria\s+de)|"
    r"(?:eu\s+)?tenho\s+interesse\s+em)"
)
_INFORMACOES = r"(?:(?:mais|algumas)\s+)?(?:informacoes|informacao|infos?|detalhes)"
_PEDIR = (
    r"(?:posso\s+(?:ter|receber|obter)|"
    r"(?:(?:voce|voces|vc|vcs)\s+)?(?:pode|podem|poderia|poderiam)\s+"
    r"(?:me\s+)?(?:dar|passar|enviar|mandar|fornecer)|"
    r"(?:me\s+)?(?:manda|mande|passa|passe|envia|envie))"
)

# Saudações e cortesia são opcionais e não fazem parte da intenção principal.
_SAUDACAO = re.compile(
    r"^(?:oi+|ola|alo|bom\s+dia|boa\s+tarde|boa\s+noite|tudo\s+bem|tudo\s+bom|"
    r"por\s+favor|por\s+gentileza)(?:\s+|$)"
)
_CORTESIA_FINAL = re.compile(r"\s+(?:por\s+favor|por\s+gentileza|obrigad[oa])$")

_PADROES = tuple(
    re.compile(padrao)
    for padrao in (
        _PERGUNTA,
        rf"{_INTENCAO}\s+(?:saber|entender)\s+{_PERGUNTA}",
        rf"{_INTENCAO}\s+(?:saber|conhecer|entender)\s+"
        rf"(?:um\s+pouco\s+)?(?:mais|melhor)(?:\s+{_ASSUNTO})?",
        rf"{_INTENCAO}\s+(?:(?:receber|ter|obter)\s+)?{_INFORMACOES}"
        rf"(?:\s+{_ASSUNTO})?",
        rf"{_PEDIR}\s+{_INFORMACOES}(?:\s+{_ASSUNTO})?",
        rf"(?:posso\s+saber|(?:(?:voce|voces|vc|vcs)\s+)?"
        rf"(?:pode|podem|poderia|poderiam)\s+(?:me\s+)?falar)\s+"
        rf"(?:um\s+pouco\s+)?mais(?:\s+{_ASSUNTO})?",
        rf"(?:(?:(?:voce|voces|vc|vcs)\s+)?(?:pode|podem|poderia|poderiam)\s+"
        rf"(?:me\s+)?explicar|me\s+(?:explica|explique))\s+"
        rf"(?:{_PERGUNTA}|{_ASSUNTO}|{_REFERENCIA})",
        rf"mais\s+(?:informacoes|detalhes)(?:\s+{_ASSUNTO})?",
    )
)


def validar_pedido_informacoes_supera(texto):
    """Aceita frases com ou sem acentos, saudação, emojis e interrogação."""
    if not isinstance(texto, str) or not texto.strip():
        return False
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(letra for letra in texto if not unicodedata.combining(letra))
    texto = " ".join(re.sub(r"[^a-z0-9\s]", " ", texto).split())

    while saudacao := _SAUDACAO.match(texto):
        texto = texto[saudacao.end() :]
    while _CORTESIA_FINAL.search(texto):
        texto = _CORTESIA_FINAL.sub("", texto)

    return any(padrao.fullmatch(texto) for padrao in _PADROES)
