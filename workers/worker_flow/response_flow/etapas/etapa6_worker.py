import logging

from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_7_RETORNO_OFERTA,
    EVENTO_CLIENTE_RETORNOU,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM UMA RESPONSABILIDADE

- ENCAMINHAR QUALQUER NOVA MENSAGEM DA ETAPA 6 PARA A ETAPA 7
"""


logger = logging.getLogger("worker.etapa6")


def resolve_etapa6(contexto_historico):
    """
    A etapa 6 representa a espera após o cliente adiar a oferta.

    Qualquer nova mensagem significa que o cliente retornou. Não existem
    validações de mídia, financeiro ou contexto nesta etapa.
    """
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]

    # VALIDANDO DESTINO
    # A própria existência da mensagem produz o único evento da etapa 6.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_CLIENTE_RETORNOU,
        destinos_esperados={ETAPA_7_RETORNO_OFERTA},
    )

    logger.info(
        "etapa6_cliente_retornou | acao=simular_envio_etapa7 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "tipo_mensagem=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_CLIENTE_RETORNOU,
        etapa_destino,
        contexto_historico.get("tipo_mensagem_atual"),
    )

    contexto_envio = _montar_contexto_etapa7_simulada(
        contexto_historico,
        etapa_destino,
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_CLIENTE_RETORNOU,
        etapa_destino,
    )


def _montar_contexto_etapa7_simulada(
    contexto_historico,
    etapa_destino,
):
    # TEMPORÁRIO: remover quando o sender real da etapa 7 existir.
    id_mensagem_fila = contexto_historico[
        "mensagem_cliente_atual"
    ]["id_mensagem_fila"]

    return {
        "enviou": True,
        "envio_simulado": True,
        "resposta_ja_existia": False,
        "mensagem_bot": (
            f"Nesse momento a futura etapa {etapa_destino} foi enviada."
        ),
        "id_hash_msg_bot": (
            f"simulacao.etapa{etapa_destino}.fila.{id_mensagem_fila}"
        ),
        "id_etapa_resultante": etapa_destino,
        "tipo_mensagem": "simulacao",
        "canal": "simulacao_worker",
        "atualizar_conversa": True,
        "atualizar_last_from_bot": True,
    }
