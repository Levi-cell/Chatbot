import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa11 import (
    enviar_etapa11_cliente,
    enviar_etapa11_dependente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_11_TRIAGEM_PERGUNTA_1,
    EVENTO_TRIAGEM_INICIADA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM UMA RESPONSABILIDADE

- ENCAMINHAR QUALQUER INTERACAO DA ETAPA 10 PARA A PRIMEIRA PERGUNTA DA TRIAGEM
"""


logger = logging.getLogger("worker.etapa10")


def resolve_etapa10(contexto_historico):
    """
    A etapa 10 apenas apresenta a triagem cognitiva.

    Qualquer interação produz triagem_iniciada. Não existem validações de
    mídia, financeiro ou contexto nesta etapa.
    """
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]

    # VALIDANDO DESTINO
    # A própria existência da interação produz o único evento da etapa 10.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_TRIAGEM_INICIADA,
        destinos_esperados={ETAPA_11_TRIAGEM_PERGUNTA_1},
    )

    logger.info(
        "etapa10_triagem_iniciada | acao=enviar_etapa11 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "tipo_mensagem=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_TRIAGEM_INICIADA,
        etapa_destino,
        contexto_historico.get("tipo_mensagem_atual"),
    )

    if contexto_historico.get("status_dependente"):
        contexto_envio = enviar_etapa11_dependente(
            mensagem_cliente["cliente_telefone"],
            mensagem_cliente["id_phone_unidade"],
            contexto_historico.get("nome_dependente"),
        )
    else:
        contexto_envio = enviar_etapa11_cliente(
            mensagem_cliente["cliente_telefone"],
            mensagem_cliente["id_phone_unidade"],
        )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_TRIAGEM_INICIADA,
        etapa_destino,
    )
