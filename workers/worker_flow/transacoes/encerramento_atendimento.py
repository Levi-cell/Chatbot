import logging

from core.repositories.encerramento_atendimento import (
    encerrar_conversa,
    excluir_dependente_da_conversa,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    validar_idade,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_4_IDADE_ALUNO,
)


logger = logging.getLogger("worker.support")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"


def resolver_intencao_encerramento(
    contexto_historico,
    contexto_envio,
):
    if contexto_envio.get("evento_transicao"):
        return None

    if contexto_envio.get("encerrar_atendimento"):
        return {
            "motivo": contexto_envio["motivo_encerramento"],
            "excluir_dependente": bool(
                contexto_envio.get("excluir_dependente")
            ),
        }

    # No retry, a resposta já existe e a decisão é reconstruída pela mesma
    # mensagem original da etapa 4, sem consultar conversas anteriores.
    if not contexto_envio.get("resposta_ja_existia"):
        return None

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
            "excluir_dependente": False,
        }

    if not resultado.valida:
        return None

    if contexto_historico.get("status_dependente"):
        if resultado.idade < 5:
            return {
                "motivo": MOTIVO_DEPENDENTE_MENOR_5,
                "excluir_dependente": True,
            }
        return None

    if resultado.idade < 18:
        return {
            "motivo": MOTIVO_CLIENTE_MENOR_18,
            "excluir_dependente": False,
        }

    return None


def aplicar_encerramento_se_necessario(
    id_conversa,
    intencao_encerramento,
    cursor,
):
    if not intencao_encerramento:
        return False

    if intencao_encerramento["excluir_dependente"]:
        excluir_dependente_da_conversa(id_conversa, cursor)

    encerrar_conversa(id_conversa, cursor)

    logger.info(
        "atendimento_encerrado | acao=encerrar_sem_bloqueio "
        "id_conversa=%s motivo=%s dependente_excluido=%s",
        id_conversa,
        intencao_encerramento["motivo"],
        intencao_encerramento["excluir_dependente"],
    )
    return True
