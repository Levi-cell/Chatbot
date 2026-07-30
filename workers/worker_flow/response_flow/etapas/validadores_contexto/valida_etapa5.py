import re
import unicodedata
from dataclasses import dataclass


STATUS_IDADE_VALIDA = "idade_valida"
STATUS_IDADE_INVALIDA = "idade_invalida"
STATUS_IDADE_ACIMA_LIMITE = "idade_acima_limite"

MOTIVO_SEM_IDADE = "sem_idade"
MOTIVO_MULTIPLAS_IDADES = "multiplas_idades"
MOTIVO_FORA_INTERVALO = "fora_intervalo"
MOTIVO_FORMATO_INVALIDO = "formato_invalido"

IDADE_MINIMA_DEPENDENTE_PADRAO = 5
IDADE_MINIMA_DEPENDENTE_BPA = 4

UNIDADES = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
}

ATE_DEZENOVE = {
    **UNIDADES,
    "dez": 10,
    "onze": 11,
    "doze": 12,
    "treze": 13,
    "quatorze": 14,
    "catorze": 14,
    "quinze": 15,
    "dezesseis": 16,
    "dezasseis": 16,
    "dezessete": 17,
    "dezassete": 17,
    "dezoito": 18,
    "dezenove": 19,
}

DEZENAS = {
    "vinte": 20,
    "trinta": 30,
    "quarenta": 40,
    "cinquenta": 50,
    "sessenta": 60,
    "setenta": 70,
    "oitenta": 80,
    "noventa": 90,
}

CENTENAS = {
    "cem": 100,
    "cento": 100,
    "duzentos": 200,
    "duzentas": 200,
    "trezentos": 300,
    "trezentas": 300,
    "quatrocentos": 400,
    "quatrocentas": 400,
    "quinhentos": 500,
    "quinhentas": 500,
    "seiscentos": 600,
    "seiscentas": 600,
    "setecentos": 700,
    "setecentas": 700,
    "oitocentos": 800,
    "oitocentas": 800,
    "novecentos": 900,
    "novecentas": 900,
    "mil": 1000,
}

PADRAO_NUMERO = re.compile(r"\d+")
PADRAO_TOKEN = re.compile(r"[a-z]+", re.IGNORECASE)


@dataclass(frozen=True)
class ResultadoValidacaoIdade:
    status: str
    idade: int | None = None
    motivo: str | None = None

    @property
    def valida(self):
        return self.status == STATUS_IDADE_VALIDA

    @property
    def acima_limite(self):
        return self.status == STATUS_IDADE_ACIMA_LIMITE


def validar_idade(texto):
    texto_original = str(texto or "").strip()

    if not texto_original:
        return _resultado_invalido(MOTIVO_SEM_IDADE)

    texto_normalizado = _normalizar_texto(texto_original)

    if _tem_formato_numerico_invalido(texto_normalizado):
        return _resultado_invalido(MOTIVO_FORMATO_INVALIDO)

    candidatos = [
        int(valor)
        for valor in PADRAO_NUMERO.findall(texto_normalizado)
    ]
    candidatos.extend(_extrair_numeros_por_extenso(texto_normalizado))

    if not candidatos:
        return _resultado_invalido(MOTIVO_SEM_IDADE)

    if len(candidatos) != 1:
        return _resultado_invalido(MOTIVO_MULTIPLAS_IDADES)

    idade = candidatos[0]

    if idade <= 0:
        return _resultado_invalido(MOTIVO_FORA_INTERVALO)

    if idade >= 100:
        return ResultadoValidacaoIdade(
            status=STATUS_IDADE_ACIMA_LIMITE,
            idade=idade,
        )

    return ResultadoValidacaoIdade(
        status=STATUS_IDADE_VALIDA,
        idade=idade,
    )


def obter_idade_minima_dependente(bpa_ativo):
    """Resolve o corte da unidade sem alterar a validação da idade informada."""
    if bpa_ativo:
        return IDADE_MINIMA_DEPENDENTE_BPA

    return IDADE_MINIMA_DEPENDENTE_PADRAO


def _tem_formato_numerico_invalido(texto):
    if re.search(
        r"(?:^|\s)(?:-|menos(?:\s+de)?)\s*\d",
        texto,
    ):
        return True

    if re.search(
        r"\bmenos(?:\s+de)?\s+(?:"
        r"um|uma|dois|duas|tres|quatro|cinco|seis|sete|oito|nove|"
        r"dez|onze|doze|treze|quatorze|catorze|quinze|"
        r"dezesseis|dezasseis|dezessete|dezassete|dezoito|"
        r"dezenove|vinte|trinta|quarenta|cinquenta|sessenta|"
        r"setenta|oitenta|noventa|cem|cento"
        r")\b",
        texto,
    ):
        return True

    if re.search(r"\d+\s*[,\.]\s*\d+", texto):
        return True

    if re.search(r"\b(?:virgula|ponto|meio|meia)\b", texto):
        return True

    return False


def _extrair_numeros_por_extenso(texto):
    tokens = PADRAO_TOKEN.findall(texto)
    resultados = []
    indice = 0

    while indice < len(tokens):
        valor, consumidos = _ler_numero_por_extenso(tokens, indice)

        if consumidos:
            resultados.append(valor)
            indice += consumidos
            continue

        indice += 1

    return resultados


def _ler_numero_por_extenso(tokens, indice):
    token = tokens[indice]

    if token in CENTENAS:
        valor = CENTENAS[token]
        consumidos = 1

        if _token_em(tokens, indice + 1) == "e":
            restante, usados = _ler_ate_noventa_e_nove(
                tokens,
                indice + 2,
            )
            if usados:
                valor += restante
                consumidos += usados + 1

        return valor, consumidos

    return _ler_ate_noventa_e_nove(tokens, indice)


def _ler_ate_noventa_e_nove(tokens, indice):
    token = _token_em(tokens, indice)

    if token in ATE_DEZENOVE:
        return ATE_DEZENOVE[token], 1

    if token not in DEZENAS:
        return None, 0

    valor = DEZENAS[token]

    if (
        _token_em(tokens, indice + 1) == "e"
        and _token_em(tokens, indice + 2) in UNIDADES
    ):
        return valor + UNIDADES[tokens[indice + 2]], 3

    return valor, 1


def _token_em(tokens, indice):
    if indice < 0 or indice >= len(tokens):
        return None

    return tokens[indice]


def _normalizar_texto(texto):
    texto_decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caractere
        for caractere in texto_decomposto
        if unicodedata.category(caractere) != "Mn"
    )


def _resultado_invalido(motivo):
    return ResultadoValidacaoIdade(
        status=STATUS_IDADE_INVALIDA,
        motivo=motivo,
    )
