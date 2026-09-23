import logging

from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_etapa2_contexto_opcao_invalida,
    enviar_etapa2_financeiro,
    enviar_etapa2_midia,
    enviar_etapa2_reforco_escolar,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import (
    enviar_etapa3,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    OPCAO_PARA_OUTRA_PESSOA,
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_etapa2,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_3_CONFIRMACAO_DESTINO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa2")


def resolve_etapa2(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem["cliente_telefone"]
    phone_id_unidade = mensagem["id_phone_unidade"]

    if validar_midia(tipo_mensagem):
        _logar_tratamento(
            contexto_historico,
            "tipo_mensagem_nao_suportado",
        )
        return enviar_etapa2_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )
        return enviar_etapa2_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )
        return enviar_etapa2_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    opcao_atendimento = validar_etapa2(texto_cliente)

    if opcao_atendimento is None:
        if contexto_historico.get("retorno_followup"):
            return enviar_repeticao_followup(contexto_historico)
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )
        return enviar_etapa2_contexto_opcao_invalida(
            cliente_telefone,
            phone_id_unidade,
        )

    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
        destinos_esperados={ETAPA_3_CONFIRMACAO_DESTINO},
    )
    status_dependente = (
        opcao_atendimento == OPCAO_PARA_OUTRA_PESSOA
    )

    contexto_envio = enviar_etapa3(
        cliente_telefone,
        phone_id_unidade,
        status_dependente,
    )
    contexto_envio.update(
        {
            "opcao_atendimento": opcao_atendimento,
            "status_dependente": status_dependente,
        }
    )

    logger.info(
        "etapa2_destino_validado | acao=enviar_etapa3 id_conversa=%s "
        "id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "opcao_atendimento=%s status_dependente=%s",
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
        etapa_destino,
        opcao_atendimento,
        status_dependente,
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
        etapa_destino,
    )


def _logar_tratamento(contexto_historico, motivo):
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
