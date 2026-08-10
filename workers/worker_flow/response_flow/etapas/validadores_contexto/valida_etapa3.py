from dataclasses import dataclass

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    normalizar_texto,
)


TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA = "confirmacao_destino_invalida"

MOTIVO_RESPOSTA_AUSENTE = "confirmacao_ausente"
MOTIVO_RESPOSTA_NAO_RECONHECIDA = "confirmacao_nao_reconhecida"

TIPOS_MENSAGEM_ACEITOS_ETAPA3 = {
    "button",
    "interactive",
    "text",
}

RESPOSTA_SIM = "sim"
RESPOSTA_NAO = "nao"


@dataclass(frozen=True)
class ResultadoConfirmacaoDestino:
    valida: bool
    status_dependente_final: bool | None = None
    motivo: str | None = None


def validar_etapa3(conteudo_texto, status_dependente_atual):
    """Aceita somente as duas opções exibidas pela etapa: Sim ou Não.

    O clique no botão e o texto digitado chegam no mesmo campo. A resposta
    "Sim" mantém a escolha feita na etapa 2; "Não" escolhe o polo oposto.
    Qualquer outro conteúdo deve repetir a confirmação com tratamento de
    contexto.
    """
    if not isinstance(conteudo_texto, str):
        return _resultado_invalido(MOTIVO_RESPOSTA_AUSENTE)

    resposta = " ".join(normalizar_texto(conteudo_texto).split())
    if not resposta:
        return _resultado_invalido(MOTIVO_RESPOSTA_AUSENTE)

    status_atual = bool(status_dependente_atual)

    if resposta == RESPOSTA_SIM:
        return _resultado_valido(status_atual)

    if resposta == RESPOSTA_NAO:
        return _resultado_valido(not status_atual)

    return _resultado_invalido(MOTIVO_RESPOSTA_NAO_RECONHECIDA)


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
