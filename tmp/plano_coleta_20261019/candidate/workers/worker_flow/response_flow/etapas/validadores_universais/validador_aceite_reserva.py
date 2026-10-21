import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)


OPCAO_ACEITA = "aceita"
OPCAO_ADIADA = "adiada"

TEXTO_BOTAO_QUERO_RESERVAR = "quero reservar"
TEXTO_BOTAO_RESERVAR_AGORA = "reservar agora"
TEXTO_BOTAO_TALVEZ_MAIS_TARDE = "talvez mais tarde"

# Só retira a expressão inicial de ausência de objeção. O restante da resposta
# ainda precisa passar pelas negativas, pedidos de informação e aceite.
PADRAO_PREFIXO_SEM_OBJECAO = re.compile(r"^nao\s+ha\s+problema\b\s*")

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
    r"\bcancelar\b|"
    r"\brecuso\b"
    r")"
)

# Pedidos informativos precisam prevalecer sobre palavras positivas genéricas.
# Os padrões usam construções completas para não invalidar "quero", "gostaria"
# e outras confirmações curtas quando elas aparecem sozinhas.
PADRAO_PEDIDO_INFORMACOES = re.compile(
    r"(?:"
    r"\b(?:quero|queria|gostaria|desejo|preciso)\b"
    r"(?:\s+de)?"
    r"(?:\s+(?:receber|ter|obter))?"
    r"(?:\s+(?:mais|alguma|algumas))?"
    r"\s+(?:informacoes?|detalhes?|explicacoes?|esclarecimentos?)\b|"
    r"\b(?:quero|queria|gostaria|desejo|preciso)\b"
    r"(?:\s+de)?\s+(?:saber|entender)\b|"
    r"\b(?:quero|queria|gostaria|desejo|preciso)\b"
    r"(?:\s+de)?\s+tirar\s+(?:uma\s+|algumas?\s+)?duvidas?\b|"
    r"\b(?:quero|queria|gostaria|desejo|preciso)\b"
    r"(?:\s+de)?\s+(?:fazer\s+(?:uma\s+)?perguntas?|perguntar)\b"
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
    r"\bquero\s+(?:agendar|reservar)\b|"
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
    r"\bpode(?:m)?\s+(?:agendar|reservar|marcar|ser|continuar)\b|"
    r"\b(?:agende|reserve)\b|"
    r"\bmarque\b|"
    r"\bmarca\s+pra\s+mim\b"
    r")"
)


def validar_aceite_reserva(conteudo_texto):
    """Interpreta aceite/adiamento por botão ou texto, preservando termos antigos."""
    if not isinstance(conteudo_texto, str):
        return None

    texto_normalizado = _normalizar_resposta(conteudo_texto)

    if not texto_normalizado:
        return None

    if texto_normalizado == TEXTO_BOTAO_TALVEZ_MAIS_TARDE:
        return OPCAO_ADIADA

    texto_normalizado = PADRAO_PREFIXO_SEM_OBJECAO.sub(
        "", texto_normalizado, count=1
    )

    # A negação prevalece mesmo quando a frase também contém termo positivo.
    if PADRAO_RESPOSTA_NEGATIVA.search(texto_normalizado):
        return None

    # "Sim" ou "quero" não representam aceite quando compõem um pedido de
    # informação, como em "sim, quero mais informações".
    if PADRAO_PEDIDO_INFORMACOES.search(texto_normalizado):
        return None

    if texto_normalizado in (
        TEXTO_BOTAO_RESERVAR_AGORA,
        TEXTO_BOTAO_QUERO_RESERVAR,
    ):
        return OPCAO_ACEITA

    if PADRAO_RESPOSTA_POSITIVA.search(texto_normalizado):
        return OPCAO_ACEITA

    return None


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())
