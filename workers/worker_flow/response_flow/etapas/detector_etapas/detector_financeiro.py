import re
import unicodedata


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


def detecta_pergunta_financeira(texto):
    texto_normalizado = normalizar_texto(texto or "")
    return bool(PADRAO_PERGUNTA_FINANCEIRA.search(texto_normalizado))


def normalizar_texto(texto):
    texto_sem_acento = unicodedata.normalize("NFKD", texto)
    texto_ascii = "".join(
        caractere
        for caractere in texto_sem_acento
        if not unicodedata.combining(caractere)
    )

    return texto_ascii.lower()
