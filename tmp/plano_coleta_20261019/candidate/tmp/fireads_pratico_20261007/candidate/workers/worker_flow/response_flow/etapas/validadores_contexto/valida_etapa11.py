import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_TRIAGEM_INICIADA,
)


TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA = "confirmacao_triagem_invalida"

TIPOS_MENSAGEM_ACEITOS_ETAPA11 = {
    "button",
    "interactive",
    "interactive_button",
    "text",
}

_CONFIRMACOES_DIRETAS = {
    "aceito",
    "beleza",
    "bora",
    "certo",
    "claro",
    "claro que sim",
    "com certeza",
    "combinado",
    "estou pronta",
    "estou pronto",
    "fechado",
    "manda ver",
    "ok",
    "okay",
    "partiu",
    "pode",
    "pode sim",
    "pode ser",
    "podemos",
    "podemos sim",
    "pronta",
    "pronto",
    "quero",
    "quero sim",
    "sim",
    "sim pode",
    "simbora",
    "ta bom",
    "ta certo",
    "topo",
    "tudo bem",
    "tudo certo",
    "vamos",
    "vamos sim",
}

_PADRAO_NEGACAO = re.compile(
    r"\b(?:nao|nunca|jamais|talvez|depois|recuso|dispenso)\b"
)

_ACAO_INICIAR_TRIAGEM = (
    r"(?:comecar|comeca|comece|iniciar|inicia|inicie)"
    r"(?:\s+(?:a\s+)?triagem)?"
)

_ACAO_CONTINUAR = r"(?:continuar|continue|prosseguir|prossiga|seguir)"

_ACAO_CONFIRMADA = rf"(?:{_ACAO_INICIAR_TRIAGEM}|{_ACAO_CONTINUAR})"

_PREFIXO_AFIRMATIVO = (
    r"(?:sim|ok|okay|certo|claro|com\s+certeza|beleza|combinado|"
    r"fechado|pronto|pronta|estou\s+pronto|estou\s+pronta)"
)

_PADRAO_CONFIRMACAO_COM_ACAO = re.compile(
    rf"(?:{_PREFIXO_AFIRMATIVO}\s+)?"
    rf"(?:"
    rf"(?:vamos|bora)(?:\s+(?:la|nessa|agora))?"
    rf"(?:\s+{_ACAO_CONFIRMADA})?|"
    rf"(?:pode|podemos|quero)(?:\s+sim)?\s+{_ACAO_CONFIRMADA}|"
    rf"{_ACAO_CONFIRMADA}"
    rf")"
    rf"(?:\s+(?:por\s+favor|entao|agora|sim))?"
)


def validar_etapa11(conteudo_texto):
    """Traduz uma confirmação inequívoca no evento da etapa 11.

    O webhook coloca o título do botão no mesmo campo usado por texto livre.
    Assim, botão e confirmações digitadas percorrem a mesma regra específica.
    """
    if not isinstance(conteudo_texto, str):
        return None

    resposta_normalizada = _normalizar_resposta(conteudo_texto)

    if not resposta_normalizada:
        return None

    # Uma negativa sempre prevalece, mesmo acompanhada de termo afirmativo.
    if _PADRAO_NEGACAO.search(resposta_normalizada):
        return None

    if resposta_normalizada in _CONFIRMACOES_DIRETAS:
        return EVENTO_TRIAGEM_INICIADA

    if _PADRAO_CONFIRMACAO_COM_ACAO.fullmatch(resposta_normalizada):
        return EVENTO_TRIAGEM_INICIADA

    return None


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())
