import re

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_AGENDAMENTO_CONFIRMADO,
)


TIPO_TRATAMENTO_AGENDAMENTO_NAO_CONFIRMADO = (
    "agendamento_nao_confirmado"
)

_CONFIRMACOES_ACEITAS = {
    "ja agendei",
    "agendei",
    "agendado",
    "ja esta agendado",
    "esta agendado",
    "consegui agendar",
    "agendamento feito",
    "agendamento realizado",
}


def validar_etapa18(conteudo_texto):
    """Aceita somente confirmações curtas de agendamento concluído.

    O webhook coloca o título do botão no mesmo campo usado pelo texto. Assim,
    clique e resposta digitada percorrem a mesma validação estrita.
    """
    if not isinstance(conteudo_texto, str):
        return None

    texto_normalizado = _normalizar_resposta(conteudo_texto)

    if texto_normalizado in _CONFIRMACOES_ACEITAS:
        return EVENTO_AGENDAMENTO_CONFIRMADO

    return None


def _normalizar_resposta(texto):
    texto_sem_acento = normalizar_texto(texto)
    texto_sem_pontuacao = re.sub(
        r"[^a-z0-9\s]",
        " ",
        texto_sem_acento,
    )
    return " ".join(texto_sem_pontuacao.split())
