import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa16 import (
    enviar_etapa16_contexto_invalido,
    enviar_etapa16_financeiro,
    enviar_etapa16_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa17 import (
    enviar_etapa17,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa16 import (
    TIPO_TRATAMENTO_AGENDAMENTO_NAO_CONFIRMADO,
    validar_etapa16,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_17_FINALIZACAO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- APLICAR OS TRATAMENTOS DA ETAPA 16
- ENCAMINHAR PARA A ETAPA TERMINAL 17 AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa16")


def resolve_etapa16(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    link_agendamento = contexto_historico.get(
        "link_agendamento_unidade"
    )
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # VALIDANDO MIDIA NA ETAPA 16
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        return enviar_etapa16_midia(
            cliente_telefone,
            phone_id_unidade,
            link_agendamento,
        )

    # VALIDANDO PERGUNTA FINANCEIRA NA ETAPA 16
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_etapa16_financeiro(
            cliente_telefone,
            phone_id_unidade,
            link_agendamento,
        )

    # VALIDANDO A CONFIRMACAO DE AGENDAMENTO
    evento_transicao = validar_etapa16(texto_cliente)

    if evento_transicao is None:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_AGENDAMENTO_NAO_CONFIRMADO,
        )

        return enviar_etapa16_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
            link_agendamento,
        )

    # VALIDANDO DESTINO
    # A etapa 16 produz um único evento e um único destino.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados={ETAPA_17_FINALIZACAO},
    )

    logger.info(
        "etapa16_agendamento_confirmado | acao=enviar_etapa17 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento_transicao,
        etapa_destino,
    )

    contexto_envio = enviar_etapa17(
        cliente_telefone,
        phone_id_unidade,
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
