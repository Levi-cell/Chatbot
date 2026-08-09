import re
from dataclasses import dataclass

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    FRASES_PARA_DEPENDENTE,
    FRASES_PARA_MIM,
    PARENTESCOS_ACEITOS,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)


TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA = "confirmacao_destino_invalida"

MOTIVO_RESPOSTA_AUSENTE = "confirmacao_ausente"
MOTIVO_RESPOSTA_NAO_RECONHECIDA = "confirmacao_nao_reconhecida"
MOTIVO_SINAIS_CONTRADITORIOS = "confirmacao_contraditoria"

TIPOS_MENSAGEM_ACEITOS_ETAPA3 = {
    "button",
    "interactive",
    "text",
}


@dataclass(frozen=True)
class ResultadoConfirmacaoDestino:
    valida: bool
    status_dependente_final: bool | None = None
    motivo: str | None = None


_CONFIRMACOES_POSITIVAS = frozenset(
    {
        "aham",
        "beleza",
        "blz",
        "certo",
        "claro",
        "com certeza",
        "combinado",
        "confirmado",
        "confirmada",
        "confirmo",
        "confirmo sim",
        "correto",
        "e isso",
        "e isso mesmo",
        "exato",
        "exatamente",
        "fechado",
        "isso",
        "isso mesmo",
        "ok",
        "ok continuar",
        "okay",
        "perfeito",
        "pode continuar",
        "pode prosseguir",
        "pode seguir",
        "positivo",
        "s",
        "sim",
        "sim confirmo",
        "sim isso mesmo",
        "sim pode continuar",
        "sim vamos la",
        "ss",
        "ta certo",
        "tudo certo",
        "uhum",
        "vamos continuar",
        "vamos la",
        "vamos prosseguir",
    }
)

_CONFIRMACOES_NEGATIVAS = frozenset(
    {
        "acabei me confundindo",
        "acabei me enganando",
        "cometi erro",
        "cometi um erro",
        "confundi",
        "engano",
        "errei",
        "escolhi errado",
        "eu cometi erro",
        "eu cometi um erro",
        "eu me confundi",
        "eu me enganei",
        "foi engano",
        "foi um engano",
        "marquei errado",
        "me confundi",
        "me enganei",
        "n",
        "nao",
        "nao acabei me enganando",
        "nao confirmo",
        "nao concordo",
        "nao e isso",
        "nao esta certo",
        "negativo",
        "respondi errado",
        "quero corrigir",
    }
)

_PADRAO_CONFIRMACAO_POSITIVA = re.compile(
    r"(?:"
    r"(?:sim|s|ok|okay|certo|claro|confirmo|com certeza|beleza)\s+"
    r")?"
    r"(?:"
    r"(?:pode|podemos|quero|vamos)\s+"
    r"(?:continuar|prosseguir|seguir|la)|"
    r"(?:bora)(?:\s+la)?|"
    r"(?:continuar|continue|prosseguir|prossiga|seguir)"
    r")"
    r"(?:\s+(?:entao|por favor))?"
)

_PADRAO_CONFIRMACAO_NEGATIVA = re.compile(
    r"(?:"
    r"(?:nao|n)(?:\s+(?:confirmo|concordo|esta certo|e isso))?|"
    r"(?:nao\s+)?(?:acabei\s+)?me\s+(?:enganando|confundindo)|"
    r"(?:eu\s+)?me\s+(?:enganei|confundi)|"
    r"(?:eu\s+)?cometi\s+(?:um\s+)?erro|"
    r"(?:foi|cometi)?\s*(?:um\s+)?engano|"
    r"(?:errei|confundi)|"
    r"(?:escolhi|marquei|respondi)\s+errado|"
    r"(?:quero|preciso)\s+corrigir"
    r")"
    r"(?:\s+(?:a resposta|a opcao|isso))?"
)

# A etapa 2 já concentra o vocabulário de destinatários. Na confirmação,
# aproveitamos apenas as formas afirmativas; frases iniciadas por "não" são
# analisadas como polaridade para evitar aceitar contradições silenciosamente.
_DESTINOS_TITULAR_CANONICOS = frozenset(
    frase
    for frase in FRASES_PARA_MIM
    if not frase.startswith("nao ")
) | {
    "e a para mim",
    "e a pra mim",
    "e para min",
    "eu msm",
    "para min",
    "pra min",
    "sim e para min",
    "sim para min",
    "so pra min",
}

# O erro "min" deve funcionar em todas as construções já aceitas com "mim",
# não apenas em meia dúzia de frases enumeradas manualmente.
_DESTINOS_TITULAR = _DESTINOS_TITULAR_CANONICOS | frozenset(
    re.sub(r"\bmim\b", "min", frase)
    for frase in _DESTINOS_TITULAR_CANONICOS
)

_DESTINOS_DEPENDENTE = frozenset(
    frase
    for frase in FRASES_PARA_DEPENDENTE
    if not frase.startswith("nao ")
)

_PREFIXOS_POSITIVOS = tuple(
    sorted(
        {
            "com certeza",
            "confirmo sim",
            "isso mesmo",
            "sim confirmo",
            "beleza",
            "certo",
            "claro",
            "confirmo",
            "correto",
            "exato",
            "ok",
            "okay",
            "perfeito",
            "positivo",
            "s",
            "sim",
        },
        key=len,
        reverse=True,
    )
)

_PREFIXOS_NEGATIVOS = tuple(
    sorted(
        {
            "acabei me confundindo",
            "acabei me enganando",
            "eu cometi um erro",
            "escolhi errado",
            "eu me confundi",
            "eu me enganei",
            "foi um engano",
            "cometi um erro",
            "marquei errado",
            "me confundi",
            "me enganei",
            "nao confirmo",
            "nao concordo",
            "respondi errado",
            "foi engano",
            "negativo",
            "quero corrigir",
            "eu cometi erro",
            "cometi erro",
            "errei",
            "n",
            "nao",
        },
        key=len,
        reverse=True,
    )
)

_PARENTESCOS_REGEX = "|".join(
    sorted(
        (re.escape(parentesco) for parentesco in PARENTESCOS_ACEITOS),
        key=len,
        reverse=True,
    )
)
_ALVO_TITULAR_REGEX = (
    r"(?:mim|min|eu(?:\s+(?:mesma|mesmo|propria|proprio|msm))?)"
)
_ALVO_DEPENDENTE_REGEX = (
    r"(?:outra\s+pessoa|(?:um|uma)?\s*dependente(?:\s+(?:meu|minha))?|"
    r"alguem(?:\s+que\s+depende\s+de\s+mim)?|"
    r"(?:uma\s+)?crianca|(?:um\s+)?idoso|(?:uma\s+)?idosa|"
    r"(?:uma\s+)?pessoa\s+com\s+deficiencia|"
    r"(?:um\s+)?deficiente|(?:uma\s+)?deficiente|"
    rf"(?:(?:o|a)\s+)?(?:meu|minha)?\s*(?:{_PARENTESCOS_REGEX}))"
)


def _compilar_padrao_contraste(alvo_negado, alvo_afirmado):
    return re.compile(
        rf"(?:nao|n|ne)\s+"
        rf"(?:(?:e|eh)\s+)?(?:(?:para|pra|pro|p)\s+)?"
        rf"{alvo_negado}(?:\s+nao)?\s+"
        rf"(?:(?:mas|so\s+que)\s+)?(?:(?:e|eh)\s+)?"
        rf"(?:(?:para|pra|pro|p)\s+)?{alvo_afirmado}"
    )


_PADRAO_CONTRASTE_TITULAR_PARA_DEPENDENTE = _compilar_padrao_contraste(
    _ALVO_TITULAR_REGEX,
    _ALVO_DEPENDENTE_REGEX,
)
_PADRAO_CONTRASTE_DEPENDENTE_PARA_TITULAR = _compilar_padrao_contraste(
    _ALVO_DEPENDENTE_REGEX,
    _ALVO_TITULAR_REGEX,
)
_PADRAO_NEGACAO_ALVO_TITULAR = re.compile(
    rf"(?:nao|ne)\s+(?:(?:e|eh)\s+)?"
    rf"(?:(?:para|pra|pro|p)\s+)?{_ALVO_TITULAR_REGEX}(?:\s+nao)?"
)
_PADRAO_NEGACAO_ALVO_DEPENDENTE = re.compile(
    rf"(?:nao|ne)\s+(?:(?:e|eh)\s+)?"
    rf"(?:(?:para|pra|pro|p)\s+)?{_ALVO_DEPENDENTE_REGEX}(?:\s+nao)?"
)


def validar_etapa3(conteudo_texto, status_dependente_atual):
    """Resolve a confirmação para um estado final absoluto e inequívoco.

    Polaridade e destino explícito são avaliados separadamente. Quando os
    dois aparecem, ambos precisam apontar para o mesmo resultado; assim,
    respostas como "sim, é para mim" não contradizem silenciosamente uma
    escolha anterior de dependente.
    """
    if not isinstance(conteudo_texto, str):
        return _resultado_invalido(MOTIVO_RESPOSTA_AUSENTE)

    resposta_normalizada = _normalizar_resposta(conteudo_texto)

    if not resposta_normalizada:
        return _resultado_invalido(MOTIVO_RESPOSTA_AUSENTE)

    status_atual = bool(status_dependente_atual)

    destino_contraste = _identificar_contraste(resposta_normalizada)
    if destino_contraste is not None:
        return _resultado_valido(destino_contraste)

    destino_negado = _identificar_destino_negado(
        conteudo_texto,
        resposta_normalizada,
    )
    if destino_negado is not None:
        return _resultado_valido(destino_negado)

    polaridade = _identificar_polaridade_direta(resposta_normalizada)
    destino_explicito = None

    # Prefixos de sim/não precisam ser destacados mesmo quando a etapa 2
    # reconheceria a frase completa como um destino. Caso contrário,
    # "sim, é para mim" apagaria a contradição com um estado dependente.
    if polaridade is None:
        polaridade_inicial, restante = _extrair_polaridade_inicial(
            resposta_normalizada
        )
        if polaridade_inicial is not None:
            polaridade = polaridade_inicial
            destino_explicito = _identificar_destino_restante(restante)
            if restante and destino_explicito is None:
                polaridade_restante = _identificar_polaridade_direta(
                    restante
                )
                if polaridade_restante is None:
                    return _resultado_invalido(
                        MOTIVO_RESPOSTA_NAO_RECONHECIDA
                    )
                if polaridade_restante != polaridade_inicial:
                    return _resultado_invalido(
                        MOTIVO_SINAIS_CONTRADITORIOS
                    )

    if polaridade is None:
        destino_explicito = _identificar_destino(resposta_normalizada)

    destino_pela_polaridade = None
    if polaridade is not None:
        destino_pela_polaridade = (
            status_atual if polaridade else not status_atual
        )

    if (
        destino_pela_polaridade is not None
        and destino_explicito is not None
        and destino_pela_polaridade != destino_explicito
    ):
        return _resultado_invalido(MOTIVO_SINAIS_CONTRADITORIOS)

    status_final = (
        destino_explicito
        if destino_explicito is not None
        else destino_pela_polaridade
    )

    if status_final is None:
        return _resultado_invalido(MOTIVO_RESPOSTA_NAO_RECONHECIDA)

    return _resultado_valido(status_final)


def _identificar_contraste(texto):
    if _PADRAO_CONTRASTE_TITULAR_PARA_DEPENDENTE.fullmatch(texto):
        return True

    if _PADRAO_CONTRASTE_DEPENDENTE_PARA_TITULAR.fullmatch(texto):
        return False

    return None


def _identificar_destino_negado(texto_original, texto_normalizado):
    texto_com_pontuacao = " ".join(normalizar_texto(texto_original).split())

    # A pausa torna o "não" uma polaridade independente: "não, é para
    # mim" precisa ser confrontado com o destino explícito logo abaixo.
    if re.match(r"^(?:nao|n)\s*[,;:]", texto_com_pontuacao):
        return None

    if _PADRAO_NEGACAO_ALVO_TITULAR.fullmatch(texto_normalizado):
        return True

    if _PADRAO_NEGACAO_ALVO_DEPENDENTE.fullmatch(texto_normalizado):
        return False

    return None


def _identificar_polaridade_direta(texto):
    if (
        texto in _CONFIRMACOES_POSITIVAS
        or _PADRAO_CONFIRMACAO_POSITIVA.fullmatch(texto)
    ):
        return True

    if (
        texto in _CONFIRMACOES_NEGATIVAS
        or _PADRAO_CONFIRMACAO_NEGATIVA.fullmatch(texto)
    ):
        return False

    return None


def _identificar_destino(texto):
    if not texto:
        return None

    if texto in _DESTINOS_TITULAR:
        return False

    if texto in _DESTINOS_DEPENDENTE:
        return True

    return None


def _identificar_destino_restante(texto):
    destino = _identificar_destino(texto)
    if destino is not None:
        return destino

    # Tolera construções coloquiais como "sim eu quero, é para meu
    # filho" sem abrir a validação para texto arbitrário depois do prefixo.
    for prefixo in ("eu quero ", "quero que ", "confirmo que "):
        if texto.startswith(prefixo):
            return _identificar_destino(texto[len(prefixo) :].strip())

    return None


def _extrair_polaridade_inicial(texto):
    for prefixo in _PREFIXOS_NEGATIVOS:
        restante = _remover_prefixo_completo(texto, prefixo)
        if restante is not None:
            return False, restante

    for prefixo in _PREFIXOS_POSITIVOS:
        restante = _remover_prefixo_completo(texto, prefixo)
        if restante is not None:
            return True, restante

    return None, texto


def _remover_prefixo_completo(texto, prefixo):
    if texto == prefixo:
        return ""

    marcador = f"{prefixo} "
    if not texto.startswith(marcador):
        return None

    return texto[len(marcador) :].strip()


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())


def _resultado_valido(status_dependente_final):
    return ResultadoConfirmacaoDestino(
        valida=True,
        status_dependente_final=bool(status_dependente_final),
    )


def _resultado_invalido(motivo):
    return ResultadoConfirmacaoDestino(
        valida=False,
        motivo=motivo,
    )
