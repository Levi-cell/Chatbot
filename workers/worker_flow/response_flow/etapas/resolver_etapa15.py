import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa15 import (
    enviar_etapa15_cliente_contexto_invalido,
    enviar_etapa15_dependente_contexto_invalido,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa16 import (
    enviar_etapa16_cliente,
    enviar_etapa16_dependente,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA,
    validar_resposta_triagem,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_16_TRIAGEM_PERGUNTA_6,
    EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A RESPOSTA DA PERGUNTA 5
- ENCAMINHAR PARA A PERGUNTA 6 AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa15")


def resolve_etapa15(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(contexto_historico.get("status_dependente"))
    nome_dependente = contexto_historico.get("nome_dependente")
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # VALIDANDO A OPCAO DA PERGUNTA 5
    resposta_triagem = validar_resposta_triagem(
        texto_cliente,
        tipo_mensagem,
    )

    if resposta_triagem is None:
        _logar_tratamento_contexto(contexto_historico)

        if status_dependente:
            return enviar_etapa15_dependente_contexto_invalido(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa15_cliente_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO DESTINO
    # Esta etapa produz um único evento e um único destino. O conjunto fica
    # explícito; _destinos_esperados_por_evento é usado com múltiplos eventos.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
        destinos_esperados={ETAPA_16_TRIAGEM_PERGUNTA_6},
    )

    logger.info(
        "etapa15_resposta_validada | acao=enviar_etapa16 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s resposta=%s status_dependente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
        etapa_destino,
        resposta_triagem,
        status_dependente,
    )

    if status_dependente:
        contexto_envio = enviar_etapa16_dependente(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )
    else:
        contexto_envio = enviar_etapa16_cliente(
            cliente_telefone,
            phone_id_unidade,
        )

    contexto_envio["resposta_triagem"] = resposta_triagem

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
        etapa_destino,
    )


def _logar_tratamento_contexto(contexto_historico):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )
