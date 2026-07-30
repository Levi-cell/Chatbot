import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)


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


def validar_etapa6(conteudo_texto):
    """
    Converte a resposta da oferta diretamente no evento da etapa 6.

    O adiamento é estrito. Respostas negativas livres recebem tratamento,
    enquanto diferentes confirmações positivas produzem oferta_aceita.
    """
    if not isinstance(conteudo_texto, str):
        return None

    texto_normalizado = _normalizar_resposta(conteudo_texto)

    if not texto_normalizado:
        return None

    if texto_normalizado == TEXTO_BOTAO_TALVEZ_MAIS_TARDE:
        return EVENTO_OFERTA_ADIADA

    # A negação prevalece mesmo quando a frase também contém termo positivo.
    if PADRAO_RESPOSTA_NEGATIVA.search(texto_normalizado):
        return None

    if texto_normalizado == TEXTO_BOTAO_QUERO_AGENDAR:
        return EVENTO_OFERTA_ACEITA

    if PADRAO_RESPOSTA_POSITIVA.search(texto_normalizado):
        return EVENTO_OFERTA_ACEITA

    return None


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())
