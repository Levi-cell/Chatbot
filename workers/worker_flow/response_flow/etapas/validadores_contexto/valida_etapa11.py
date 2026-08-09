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
    "text",
}

_CONFIRMACOES_DIRETAS = {
    "beleza",
    "certo",
    "claro",
    "com certeza",
    "combinado",
    "estou pronta",
    "estou pronto",
    "fechado",
    "ok",
    "okay",
    "partiu",
    "pode ser",
    "pronta",
    "pronto",
    "sim",
    "ta bom",
    "ta certo",
    "tudo bem",
    "tudo certo",
}

_PADRAO_NEGACAO = re.compile(
    r"\b(?:nao|nunca|jamais|talvez|depois|recuso|dispenso)\b"
)

_PADRAO_CONFIRMACAO_COM_ACAO = re.compile(
    r"(?:"
    r"(?:sim|ok|okay|certo|claro|com\s+certeza|beleza|combinado|"
    r"fechado|pronto|pronta|estou\s+pronto|estou\s+pronta)\s+"
    r")?"
    r"(?:"
    r"(?:vamos|bora)(?:\s+(?:la|nessa|comecar(?:\s+a\s+triagem)?|"
    r"iniciar(?:\s+a)?\s+triagem|iniciar|continuar|prosseguir|seguir))?|"
    r"(?:pode|podemos|quero)\s+(?:comecar(?:\s+a\s+triagem)?|"
    r"iniciar(?:\s+a)?\s+triagem|iniciar|continuar|prosseguir|seguir)|"
    r"comecar(?:\s+a\s+triagem)?|comece|"
    r"iniciar(?:\s+a)?\s+triagem|iniciar|"
    r"continuar|continue|prosseguir|prossiga|seguir"
    r")"
    r"(?:\s+(?:por\s+favor|entao))?"
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
