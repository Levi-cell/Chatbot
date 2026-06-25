import logging

from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.flow_treat_context import flow_treat_context
from workers.worker_flow.response_flow.flow_treat_financial import (
    flow_treat_financial,
)
from workers.worker_flow.response_flow.flow_treat_unsupported_type import (
    flow_treat_unsupported_type,
)
from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    RESULTADO_PERGUNTA_FINANCEIRA,
    RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO,
    validar_resposta_cliente,
)


logger = logging.getLogger("worker.rotear_resposta")


def rotear_resposta_cliente(contexto_historico):
    contexto_validacao = validar_resposta_cliente(contexto_historico)
    resultado_validacao = contexto_validacao["resultado"]

    if resultado_validacao == RESULTADO_TIPO_MENSAGEM_NAO_SUPORTADO:
        return flow_treat_unsupported_type(
            contexto_historico,
            contexto_validacao,
        )

    if resultado_validacao == RESULTADO_PERGUNTA_FINANCEIRA:
        return flow_treat_financial(
            contexto_historico,
            contexto_validacao,
        )

    if resultado_validacao == RESULTADO_MENSAGEM_FORA_DE_CONTEXTO:
        return flow_treat_context(
            contexto_historico,
            contexto_validacao,
        )

    return flow_sender(contexto_historico)
