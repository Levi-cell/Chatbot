import re
import unicodedata

from core.validacoes.formulario_meta import remover_enunciado_investimento


TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"

PADRAO_PERGUNTA_FINANCEIRA = re.compile(
    r"("
    r"r\s*\$|"
    r"\$|"
    r"\b("
    r"valor(?:es)?|"
    r"preco(?:s)?|"
    r"custo(?:s)?|"
    r"mensalidade(?:s)?|"
    r"mensal|"
    r"pagamento(?:s)?|"
    r"pagar|"
    r"pago|"
    r"cobra(?:r|m|do|da)?|"
    r"cobranca(?:s)?|"
    r"taxa(?:s)?|"
    r"investimento(?:s)?|"
    r"investir|"
    r"capital|"
    r"orcamento(?:s)?|"
    r"plano(?:s)?|"
    r"pacote(?:s)?|"
    r"matricula(?:s)?|"
    r"inscricao(?:s)?|"
    r"parcela(?:s)?|"
    r"parcelamento|"
    r"parcelado|"
    r"pix|"
    r"boleto(?:s)?|"
    r"cartao|"
    r"credito|"
    r"debito|"
    r"dinheiro|"
    r"real|"
    r"reais|"
    r"barato|"
    r"caro|"
    r"desconto(?:s)?|"
    r"promocao|"
    r"gratis|"
    r"gratuito"
    r")\b|"
    r"\bquanto\s+(?:custa|e|fica|sai|vou\s+pagar|tenho\s+que\s+pagar)\b|"
    r"\bqual\s+(?:o\s+)?(?:valor|preco|custo|investimento)\b|"
    r"\btem\s+(?:valor|preco|custo|mensalidade|taxa)\b"
    r")"
)


_PADRAO_EXPERIENCIA = re.compile(r"\b(?:demonstracao(?:\s+pratica)?|experiencia(?:\s+supera)?)\b")
_PADRAO_GRATUIDADE_FEMININA = re.compile(r"\bgratuitas?\b")
_PADRAO_PERGUNTA_GRATUIDADE = re.compile(
    r"\b(?:e|sera|seria|vai\s+ser|fica|sai)\s+(?:mesmo\s+)?gratuitas?\b"
)
_PADRAO_PERGUNTA_CURTA_GRATUIDADE = re.compile(
    r"(?:quero\s+reservar\s+)?(?:ela\s+)?(?:e\s+)?gratuita(?:\s+mesmo)?"
)


def validar_duvida_gratuidade_experiencia(texto, *, referencia_experiencia=False):
    """Reconhece a dúvida sobre a oferta, sem tornar 'gratuita' um termo genérico.

    Nas etapas de oferta/reserva, uma pergunta curta pode retomar a experiência
    já apresentada. Fora delas, o cliente precisa mencionar a atividade.
    """
    if not isinstance(texto, str):
        return False
    normalizado = normalizar_texto(texto)
    if not _PADRAO_GRATUIDADE_FEMININA.search(normalizado):
        return False
    if _PADRAO_EXPERIENCIA.search(normalizado) and (
        "?" in texto or _PADRAO_PERGUNTA_GRATUIDADE.search(normalizado)
    ):
        return True
    resposta = " ".join(re.sub(r"[^a-z0-9\s]", " ", normalizado).split())
    return bool(
        referencia_experiencia
        and _PADRAO_PERGUNTA_CURTA_GRATUIDADE.fullmatch(resposta)
    )


def validar_pergunta_financeira(texto, *, referencia_experiencia=False):
    texto_normalizado = normalizar_texto(texto or "")
    texto_normalizado = remover_enunciado_investimento(texto_normalizado)
    return bool(PADRAO_PERGUNTA_FINANCEIRA.search(texto_normalizado)) or (
        validar_duvida_gratuidade_experiencia(
            texto, referencia_experiencia=referencia_experiencia,
        )
    )


def normalizar_texto(texto):
    texto_sem_acento = unicodedata.normalize("NFKD", texto)
    texto_ascii = "".join(
        caractere
        for caractere in texto_sem_acento
        if not unicodedata.combining(caractere)
    )

    return texto_ascii.lower()
