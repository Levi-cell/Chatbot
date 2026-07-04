import logging

from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_10_TRIAGEM_PERGUNTA_1,
    EVENTO_TRIAGEM_INICIADA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM UMA RESPONSABILIDADE

- ENCAMINHAR QUALQUER INTERACAO DA ETAPA 9 PARA A PRIMEIRA PERGUNTA DA TRIAGEM
"""


logger = logging.getLogger("worker.etapa9")


def resolve_etapa9(contexto_historico):
    """
    A etapa 9 apenas apresenta a triagem cognitiva.

    Qualquer interação produz triagem_iniciada. Não existem validações de
    mídia, financeiro ou contexto nesta etapa.
    """
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]

    # VALIDANDO DESTINO
    # A própria existência da interação produz o único evento da etapa 9.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_TRIAGEM_INICIADA,
        destinos_esperados={ETAPA_10_TRIAGEM_PERGUNTA_1},
    )

    logger.info(
        "etapa9_triagem_iniciada | acao=simular_envio_etapa10 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "tipo_mensagem=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_TRIAGEM_INICIADA,
        etapa_destino,
        contexto_historico.get("tipo_mensagem_atual"),
    )

    contexto_envio = _montar_contexto_etapa10_simulada(
        contexto_historico,
        etapa_destino,
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_TRIAGEM_INICIADA,
        etapa_destino,
    )


def _montar_contexto_etapa10_simulada(
    contexto_historico,
    etapa_destino,
):
    # TEMPORARIO: remover quando a primeira pergunta e seu sender existirem.
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
