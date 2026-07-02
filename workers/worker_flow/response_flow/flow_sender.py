import logging

from workers.worker_flow.response_flow.etapas.etapa1_worker import (
    resolve_etapa1,
)
from workers.worker_flow.response_flow.etapas.etapa2_worker import (
    resolve_etapa2,
)
from workers.worker_flow.response_flow.etapas.etapa3_worker import (
    resolve_etapa3,
)
from workers.worker_flow.response_flow.etapas.etapa4_worker import (
    resolve_etapa4,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    identificar_evento_por_destino,
)


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]

    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    # Esta barreira continua antes de qualquer resolver ou sender.
    if resposta_bot_atual:
        id_etapa_resposta = resposta_bot_atual.get("id_etapa")
        evento_transicao = identificar_evento_por_destino(
            contexto_historico,
            id_etapa_resposta,
        )

        logger.info(
            "flow_sender_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_resposta=%s evento_transicao=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_resposta,
            evento_transicao,
            retry_count,
        )

        contexto_envio = {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": id_etapa_resposta,
            "id_etapa_origem_transicao": contexto_historico.get(
                "id_etapa_origem_transicao"
            ),
        }

        if evento_transicao:
            contexto_envio["evento_transicao"] = evento_transicao

        return contexto_envio

    if retry_count > 1:
        logger.info(
            "flow_sender_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            retry_count,
        )

    if id_etapa_atual is None or id_etapa_atual == 1:
        return resolve_etapa1(contexto_historico)

    if id_etapa_atual == 2:
        return resolve_etapa2(contexto_historico)

    if id_etapa_atual == 3:
        return resolve_etapa3(contexto_historico)

    if id_etapa_atual == 4:
        return resolve_etapa4(contexto_historico)

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa=%s",
        id_conversa,
        id_etapa_atual,
    )
    raise NotImplementedError(
        f"Sender da etapa atual {id_etapa_atual} ainda nao implementado"
    )
