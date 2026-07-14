import logging

from core.repositories.atendimento.conversas import encerrar_conversa
from core.repositories.atendimento.dependentes import (
    excluir_dependente_da_conversa,
)
from core.repositories.fluxo.politicas import buscar_politica_etapa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    obter_idade_minima_dependente,
    validar_idade,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_4_IDADE_ALUNO,
)


logger = logging.getLogger("worker.support")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"
MOTIVO_ETAPA_FINAL = "etapa_final"

MOTIVO_ENCERRAMENTO_IDADE_INVALIDA = "idade_invalida"
MOTIVO_ENCERRAMENTO_FOI_AGENDADO = "foi_agendado"


def resolver_intencao_encerramento(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("encerrar_atendimento"):
        return {
            "motivo": contexto_envio["motivo_encerramento"],
            "motivo_encerramento": MOTIVO_ENCERRAMENTO_IDADE_INVALIDA,
            "excluir_dependente": bool(
                contexto_envio.get("excluir_dependente")
            ),
            "bloqueio_dias": 0,
        }

    # No retry, a resposta já existe e a decisão é reconstruída pela mesma
    # mensagem original da etapa 4, sem consultar conversas anteriores.
    if contexto_envio.get("resposta_ja_existia"):
        intencao_reconstruida = _reconstruir_encerramento_etapa4(
            contexto_historico
        )
        if intencao_reconstruida:
            return intencao_reconstruida

    if not contexto_envio.get("evento_transicao"):
        return None

    id_etapa_destino = contexto_envio.get("id_etapa_resultante")
    politica_destino = buscar_politica_etapa(
        id_etapa_destino,
        cursor,
    )

    if not politica_destino.encerra_automaticamente:
        return None

    return {
        "motivo": MOTIVO_ETAPA_FINAL,
        "motivo_encerramento": MOTIVO_ENCERRAMENTO_FOI_AGENDADO,
        "excluir_dependente": False,
        "bloqueio_dias": politica_destino.bloqueio_dias,
    }


def _reconstruir_encerramento_etapa4(contexto_historico):
    if (
        contexto_historico.get("id_etapa_origem_transicao")
        != ETAPA_4_IDADE_ALUNO
    ):
        return None

    resultado = validar_idade(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado.acima_limite:
        return {
            "motivo": MOTIVO_IDADE_ACIMA_99,
            "motivo_encerramento": MOTIVO_ENCERRAMENTO_IDADE_INVALIDA,
            "excluir_dependente": False,
            "bloqueio_dias": 0,
        }

    if not resultado.valida:
        return None

    if contexto_historico.get("status_dependente"):
        idade_minima = obter_idade_minima_dependente(
            contexto_historico.get("bpa_ativo_unidade")
        )

        if resultado.idade < idade_minima:
            return {
                "motivo": MOTIVO_DEPENDENTE_MENOR_5,
                "motivo_encerramento": MOTIVO_ENCERRAMENTO_IDADE_INVALIDA,
                "excluir_dependente": True,
                "bloqueio_dias": 0,
            }
        return None

    if resultado.idade < 18:
        return {
            "motivo": MOTIVO_CLIENTE_MENOR_18,
            "motivo_encerramento": MOTIVO_ENCERRAMENTO_IDADE_INVALIDA,
            "excluir_dependente": False,
            "bloqueio_dias": 0,
        }

    return None


def aplicar_encerramento_se_necessario(
    id_conversa,
    intencao_encerramento,
    cursor,
):
    if not intencao_encerramento:
        return {
            "atendimento_encerrado": False,
            "finalizou_em": None,
            "bloqueio_dias": 0,
            "motivo": None,
            "motivo_encerramento": None,
        }

    if intencao_encerramento["excluir_dependente"]:
        excluir_dependente_da_conversa(id_conversa, cursor)

    motivo_encerramento = intencao_encerramento["motivo_encerramento"]
    finalizou_em = encerrar_conversa(
        id_conversa,
        motivo_encerramento,
        cursor,
    )
    bloqueio_dias = int(
        intencao_encerramento.get("bloqueio_dias") or 0
    )

    logger.info(
        "atendimento_encerrado | acao=encerrar_conversa "
        "id_conversa=%s motivo=%s motivo_encerramento=%s "
        "dependente_excluido=%s",
        id_conversa,
        intencao_encerramento["motivo"],
        motivo_encerramento,
        intencao_encerramento["excluir_dependente"],
    )
    return {
        "atendimento_encerrado": True,
        "finalizou_em": finalizou_em,
        "bloqueio_dias": bloqueio_dias,
        "motivo": intencao_encerramento["motivo"],
        "motivo_encerramento": motivo_encerramento,
    }
