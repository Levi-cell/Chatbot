import logging

from workers.worker_flow.response_flow.etapas.resolver_etapa1 import (
    resolve_etapa1,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa2 import (
    resolve_etapa2,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa3 import (
    resolve_etapa3,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa4 import (
    resolve_etapa4,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa5 import (
    resolve_etapa5,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa6 import (
    resolve_etapa6,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa7 import (
    resolve_etapa7,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa8 import (
    resolve_etapa8,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa9 import (
    resolve_etapa9,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa10 import (
    resolve_etapa10,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa11 import (
    resolve_etapa11,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa12 import (
    resolve_etapa12,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa13 import (
    resolve_etapa13,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa14 import (
    resolve_etapa14,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa15 import (
    resolve_etapa15,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa16 import (
    resolve_etapa16,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa17 import (
    resolve_etapa17,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa18 import (
    resolve_etapa18,
)
from workers.worker_flow.response_flow.etapas.resolver_etapa19 import (
    resolve_etapa19,
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

    if id_etapa_atual == 5:
        return resolve_etapa5(contexto_historico)

    if id_etapa_atual == 6:
        return resolve_etapa6(contexto_historico)

    if id_etapa_atual == 7:
        return resolve_etapa7(contexto_historico)

    if id_etapa_atual == 8:
        return resolve_etapa8(contexto_historico)

    if id_etapa_atual == 9:
        return resolve_etapa9(contexto_historico)

    if id_etapa_atual == 10:
        return resolve_etapa10(contexto_historico)

    if id_etapa_atual == 11:
        return resolve_etapa11(contexto_historico)

    if id_etapa_atual == 12:
        return resolve_etapa12(contexto_historico)

    if id_etapa_atual == 13:
        return resolve_etapa13(contexto_historico)

    if id_etapa_atual == 14:
        return resolve_etapa14(contexto_historico)

    if id_etapa_atual == 15:
        return resolve_etapa15(contexto_historico)

    if id_etapa_atual == 16:
        return resolve_etapa16(contexto_historico)

    if id_etapa_atual == 17:
        return resolve_etapa17(contexto_historico)

    if id_etapa_atual == 18:
        return resolve_etapa18(contexto_historico)

    if id_etapa_atual == 19:
        return resolve_etapa19(contexto_historico)

    # A etapa 20 é terminal e não possui resolver. Conversas encerradas são
    # barradas pelo cache/webhook e pelo fallback transacional do worker.

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa=%s",
        id_conversa,
        id_etapa_atual,
    )
    raise NotImplementedError(
        f"Sender da etapa atual {id_etapa_atual} ainda nao implementado"
    )
