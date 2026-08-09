import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa21 import (
    enviar_etapa21_contexto_invalido,
    enviar_etapa21_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa22 import (
    enviar_etapa22,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa20 import (
    TIPOS_MENSAGEM_ACEITOS_ETAPA20,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa21 import (
    normalizar_comentario_etapa21,
    recusou_comentario_etapa21,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_22_FINALIZACAO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa21")

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "comentario_satisfacao_invalido"


def resolve_etapa21(contexto_historico):
    """Coleta o comentário livre e encaminha para a etapa terminal."""
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    if tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA20:
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_MIDIA,
        )
        return enviar_etapa21_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    desistiu = recusou_comentario_etapa21(
        texto_cliente,
        tipo_mensagem,
    )
    comentario_satisfacao = normalizar_comentario_etapa21(
        texto_cliente,
        tipo_mensagem,
    )

    if not desistiu and comentario_satisfacao is None:
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )
        return enviar_etapa21_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        destinos_esperados={ETAPA_22_FINALIZACAO},
    )

    logger.info(
        "etapa21_comentario_recebido | acao=enviar_etapa22 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s comentario_preenchido=%s desistiu=%s tipo=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        etapa_destino,
        bool(comentario_satisfacao),
        desistiu,
        tipo_mensagem,
    )

    contexto_envio = enviar_etapa22(
        cliente_telefone,
        phone_id_unidade,
    )
    contexto_envio["comentario_satisfacao"] = comentario_satisfacao

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        etapa_destino,
    )


def _logar_tratamento(contexto_historico, motivo):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        motivo,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )
