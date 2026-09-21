import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa9 import (
    enviar_etapa9_cliente,
    enviar_etapa9_dependente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_9_RETORNO_OFERTA,
    EVENTO_CLIENTE_RETORNOU,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM UMA RESPONSABILIDADE

- ENCAMINHAR QUALQUER NOVA MENSAGEM DA ETAPA 8 PARA A ETAPA 9
"""


logger = logging.getLogger("worker.etapa8")


def resolve_etapa8(contexto_historico):
    """
    A etapa 8 representa a espera após o cliente adiar a oferta.

    Qualquer nova mensagem significa que o cliente retornou. Não existem
    validações de mídia, financeiro ou contexto nesta etapa.
    """
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )
    nome_cliente = contexto_historico.get("nome_cliente")
    nome_dependente = contexto_historico.get("nome_dependente")
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # VALIDANDO DESTINO
    # A própria existência da mensagem produz o único evento da etapa 8.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_CLIENTE_RETORNOU,
        destinos_esperados={ETAPA_9_RETORNO_OFERTA},
    )

    logger.info(
        "etapa8_cliente_retornou | acao=enviar_etapa9 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "tipo_mensagem=%s status_dependente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_CLIENTE_RETORNOU,
        etapa_destino,
        contexto_historico.get("tipo_mensagem_atual"),
        status_dependente,
    )

    if status_dependente:
        contexto_envio = enviar_etapa9_dependente(
            cliente_telefone,
            phone_id_unidade,
            nome_cliente,
            nome_dependente,
            incluir_saudacao=not bool(contexto_historico.get("saudacao_retorno")),
        )
    else:
        contexto_envio = enviar_etapa9_cliente(
            cliente_telefone,
            phone_id_unidade,
            nome_cliente,
            incluir_saudacao=not bool(contexto_historico.get("saudacao_retorno")),
        )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_CLIENTE_RETORNOU,
        etapa_destino,
    )
