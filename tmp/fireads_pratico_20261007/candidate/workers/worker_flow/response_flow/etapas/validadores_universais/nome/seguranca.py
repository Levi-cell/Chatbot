import re
import unicodedata


MOTIVO_UNICODE_INSEGURO = "unicode_inseguro"
MOTIVO_ALFABETO_NAO_SUPORTADO = "alfabeto_nao_suportado"
MOTIVO_TEXTO_CORROMPIDO = "texto_corrompido"

TAMANHO_MAXIMO_ENTRADA_NOME = 240

PADRAO_ESPACOS = re.compile(r" +")
CARACTERES_MOJIBAKE_INEQUIVOCOS = {
    "\ufffd",
}
CATEGORIAS_UNICODE_PROIBIDAS = {
    "Cc",
    "Cf",
    "Cs",
    "Co",
    "Cn",
}
TRADUCAO_SEPARADORES_NOME = str.maketrans(
    {
        "\u2010": "-",
        "\u2011": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "-",
        "\u2212": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u02bc": "'",
        "\uff07": "'",
        "\u00a0": " ",
        "\u2007": " ",
        "\u202f": " ",
    }
)


def normalizar_entrada_nome(texto):
    texto_normalizado = unicodedata.normalize("NFKC", texto)

    if len(texto_normalizado) > TAMANHO_MAXIMO_ENTRADA_NOME:
        return None, MOTIVO_UNICODE_INSEGURO

    if any(
        caractere in CARACTERES_MOJIBAKE_INEQUIVOCOS
        for caractere in texto_normalizado
    ):
        return None, MOTIVO_TEXTO_CORROMPIDO

    if any(
        unicodedata.category(caractere) in CATEGORIAS_UNICODE_PROIBIDAS
        for caractere in texto_normalizado
    ):
        return None, MOTIVO_UNICODE_INSEGURO

    texto_normalizado = texto_normalizado.translate(
        TRADUCAO_SEPARADORES_NOME
    )

    if any(
        caractere.isalpha() and not _e_letra_latina(caractere)
        for caractere in texto_normalizado
    ):
        return None, MOTIVO_ALFABETO_NAO_SUPORTADO

    if any(
        unicodedata.category(caractere).startswith("M")
        for caractere in texto_normalizado
    ):
        return None, MOTIVO_UNICODE_INSEGURO

    texto_normalizado = PADRAO_ESPACOS.sub(
        " ",
        texto_normalizado.strip(),
    )
    return unicodedata.normalize("NFC", texto_normalizado), None


def _e_letra_latina(caractere):
    return "LATIN" in unicodedata.name(caractere, "")
