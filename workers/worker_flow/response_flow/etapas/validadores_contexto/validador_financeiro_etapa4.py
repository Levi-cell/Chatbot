import re
import unicodedata


_TERMOS_FINANCEIROS_ISOLADOS = {
    "custo",
    "custos",
    "mensalidade",
    "preco",
    "precos",
    "valor",
    "valores",
}

_PADROES_PERGUNTA_FINANCEIRA = (
    re.compile(
        r"\bqual(?: e| seria)? (?:(?:o|a) )?"
        r"(?:custo|preco|valor|mensalidade|investimento)\b"
    ),
    re.compile(
        r"\bquanto "
        r"(?:"
        r"custa|custaria|e|fica|sai|pago|"
        r"eu pago|vou pagar|tenho que pagar|"
        r"vou investir|preciso investir|vai ser"
        r")\b"
    ),
    re.compile(
        r"\b(?:tem|possui|ha) (?:algum )?"
        r"(?:custo|preco|valor|mensalidade|taxa|investimento)\b"
    ),
    re.compile(
        r"\b(?:custo|preco|valor) "
        r"(?:da|das|de|do|dos) "
        r"(?:aula|avaliacao|curso|matricula|mensalidade)\b"
    ),
    re.compile(r"\b(?:matricula|mensalidade) (?:custa|e|fica|valor)\b"),
    re.compile(
        r"\b(?:aceita|aceitam|recebe|recebem) "
        r"(?:pix|boleto|cartao|credito|debito)\b"
    ),
    re.compile(
        r"\b(?:pagar|pagamento) "
        r"(?:com|no|por|via) "
        r"(?:pix|boleto|cartao|credito|debito)\b"
    ),
    re.compile(r"\b\d+(?:[.,]\d{1,2})? reais?\b"),
)


def validar_pergunta_financeira_etapa4(conteudo_texto):
    if not isinstance(conteudo_texto, str):
        return False

    if re.search(r"(?:r\s*\$|\$)", conteudo_texto, flags=re.IGNORECASE):
        return True

    texto_normalizado = _normalizar_texto(conteudo_texto)

    if not texto_normalizado:
        return False

    if texto_normalizado in _TERMOS_FINANCEIROS_ISOLADOS:
        return True

    return any(
        padrao.search(texto_normalizado)
        for padrao in _PADROES_PERGUNTA_FINANCEIRA
    )


def _normalizar_texto(texto):
    texto_decomposto = unicodedata.normalize("NFD", texto.casefold())
    texto_sem_acentos = "".join(
        caractere
        for caractere in texto_decomposto
        if unicodedata.category(caractere) != "Mn"
    )
    texto_sem_pontuacao = re.sub(r"[^\w\s]", " ", texto_sem_acentos)
    return " ".join(texto_sem_pontuacao.split())
