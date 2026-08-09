import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa20 import (
    enviar_etapa20_contexto_invalido,
    enviar_etapa20_financeiro,
    enviar_etapa20_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa21 import (
    enviar_etapa21,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa22 import (
    enviar_etapa22,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa20 import (
    TIPOS_MENSAGEM_ACEITOS_ETAPA20,
    validar_decisao_comentario_etapa20,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_21_COMENTARIO_SATISFACAO,
    ETAPA_22_FINALIZACAO,
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa20")

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_comentario_invalida"


def resolve_etapa20(contexto_historico):
    """Exige uma decisão inequívoca antes de comentar ou finalizar."""
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
        return enviar_etapa20_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )
        return enviar_etapa20_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    evento = validar_decisao_comentario_etapa20(
        texto_cliente,
        tipo_mensagem,
    )

    if evento is None:
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )
        return enviar_etapa20_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    if evento == EVENTO_COMENTARIO_SATISFACAO_ACEITO:
        destino_esperado = ETAPA_21_COMENTARIO_SATISFACAO
    elif evento == EVENTO_COMENTARIO_SATISFACAO_RECUSADO:
        destino_esperado = ETAPA_22_FINALIZACAO
    else:
        raise ValueError(
            f"Evento inesperado na decisao de comentario: {evento}"
        )

    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento,
        destinos_esperados={destino_esperado},
    )

    if evento == EVENTO_COMENTARIO_SATISFACAO_ACEITO:
        contexto_envio = enviar_etapa21(
            cliente_telefone,
            phone_id_unidade,
        )
    else:
        contexto_envio = enviar_etapa22(
            cliente_telefone,
            phone_id_unidade,
        )
        contexto_envio["comentario_satisfacao"] = None

    logger.info(
        "etapa20_decisao_validada | acao=avancar_fluxo "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento,
        etapa_destino,
    )

    contexto_envio["decisao_comentario"] = evento

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento,
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
