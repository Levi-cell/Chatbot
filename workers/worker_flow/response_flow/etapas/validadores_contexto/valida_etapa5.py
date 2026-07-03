import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)


OPCAO_QUERO_AGENDAR = EVENTO_OFERTA_ACEITA
OPCAO_TALVEZ_MAIS_TARDE = EVENTO_OFERTA_ADIADA

TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"

TEXTO_BOTAO_QUERO_AGENDAR = "quero agendar"
TEXTO_BOTAO_TALVEZ_MAIS_TARDE = "talvez mais tarde"

PADRAO_RESPOSTA_NEGATIVA = re.compile(
    r"(?:"
    r"\bnao\b|"
    r"\bnunca\b|"
    r"\bjamais\b|"
    r"\bnem\s+pensar\b|"
    r"\bde\s+jeito\s+nenhum\b|"
    r"\bsem\s+interesse\b|"
    r"\bnao\s+tenho\s+interesse\b|"
    r"\bdispenso\b|"
    r"\brecuso\b"
    r")"
)

PADRAO_RESPOSTA_POSITIVA = re.compile(
    r"(?:"
    r"\bsim\b|"
    r"\bsimbora\b|"
    r"\bbora(?:\s+la)?\b|"
    r"\bpartiu\b|"
    r"\bclaro\b|"
    r"\bcom\s+certeza\b|"
    r"\bfechado\b|"
    r"\bcombinado\b|"
    r"\bdemorou\b|"
    r"\bbeleza\b|"
    r"\bblz\b|"
    r"\bok(?:ay)?\b|"
    r"\btopo\b|"
    r"\baceito\b|"
    r"\bquero\b|"
    r"\beu\s+quero\b|"
    r"\bquero\s+muito\b|"
    r"\bquero\s+agendar\b|"
    r"\bquero\s+participar\b|"
    r"\bquero\s+experimentar\b|"
    r"\bquero\s+conhecer\b|"
    r"\bquero\s+fazer\b|"
    r"\bgostaria\b|"
    r"\badoraria\b|"
    r"\bdesejo\b|"
    r"\bpretendo\b|"
    r"\btenho\s+interesse\b|"
    r"\bestou\s+interessad[oa]\b|"
    r"\bme\s+interessa\b|"
    r"\bvamos(?:\s+sim|\s+agendar|\s+marcar|\s+nessa|\s+la)?\b|"
    r"\bvamo(?:\s+agendar|\s+marcar|\s+nessa|\s+la)?\b|"
    r"\bpode(?:m)?\s+(?:agendar|marcar|ser|continuar)\b|"
    r"\bagende\b|"
    r"\bmarque\b|"
    r"\bmarca\s+pra\s+mim\b"
    r")"
)


def validar_etapa5(conteudo_texto):
    """
    Converte a resposta da oferta em um dos eventos permitidos na etapa 5.

    Clique e texto digitado chegam pelo mesmo conteudo_texto. A opção de
    adiamento é intencionalmente estrita; respostas negativas livres recebem
    tratamento, enquanto diferentes confirmações positivas são aceitas.
    """
    if not isinstance(conteudo_texto, str):
        return None

    texto_normalizado = _normalizar_resposta(conteudo_texto)

    if not texto_normalizado:
        return None

    if texto_normalizado == TEXTO_BOTAO_TALVEZ_MAIS_TARDE:
        return OPCAO_TALVEZ_MAIS_TARDE

    # A negação sempre prevalece, inclusive em frases que também tenham
    # palavras positivas, como "quero, mas não agora".
    if PADRAO_RESPOSTA_NEGATIVA.search(texto_normalizado):
        return None

    if texto_normalizado == TEXTO_BOTAO_QUERO_AGENDAR:
        return OPCAO_QUERO_AGENDAR

    if PADRAO_RESPOSTA_POSITIVA.search(texto_normalizado):
        return OPCAO_QUERO_AGENDAR

    return None


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())
