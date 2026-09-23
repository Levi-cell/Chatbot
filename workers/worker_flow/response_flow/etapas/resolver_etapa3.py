import logging

from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import (
    enviar_etapa3_contexto_invalido,
    enviar_etapa3_financeiro,
    enviar_etapa3_midia,
    enviar_etapa3_reforco_escolar,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import (
    enviar_etapa4,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa3 import (
    TIPOS_MENSAGEM_ACEITOS_ETAPA3,
    TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA,
    validar_etapa3,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_4_PROFISSAO,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa3")


def resolve_etapa3(contexto_historico):
    """Mantém com Sim ou inverte com Não o destino salvo pela etapa 2.

    Qualquer outro texto recebe tratamento e permanece na etapa 3. Uma
    resposta válida sempre produz um estado final absoluto, evitando que
    retries reapliquem uma inversão.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente_atual = contexto_historico.get("status_dependente")
    if not isinstance(status_dependente_atual, bool):
        raise ValueError(
            "Etapa 3 sem status_dependente booleano persistido "
            f"(valor={status_dependente_atual!r})"
        )
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    if (
        validar_midia(tipo_mensagem)
        and tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA3
    ):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
        )
        return enviar_etapa3_midia(
            cliente_telefone,
            phone_id_unidade,
            status_dependente_atual,
        )

    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )
        return enviar_etapa3_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
            status_dependente_atual,
        )

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )
        return enviar_etapa3_financeiro(
            cliente_telefone,
            phone_id_unidade,
            status_dependente_atual,
        )

    resultado = validar_etapa3(
        texto_cliente,
        status_dependente_atual,
    )

    if not resultado.valida:
        if contexto_historico.get("retorno_followup"):
            return enviar_repeticao_followup(contexto_historico)
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA,
            motivo_detalhado=resultado.motivo,
        )
        return enviar_etapa3_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
            status_dependente_atual,
        )

    status_dependente_final = resultado.status_dependente_final

    evento = EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO
    destino_esperado = ETAPA_4_PROFISSAO

    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento,
        destinos_esperados={destino_esperado},
    )

    contexto_envio = enviar_etapa4(
        cliente_telefone,
        phone_id_unidade,
    )

    # O efeito transacional usa SET para este valor absoluto. Não carregamos
    # uma ordem de "inverter", que seria insegura durante reaplicações.
    contexto_envio.update(
        {
            "status_dependente_anterior": status_dependente_atual,
            "status_dependente_final": status_dependente_final,
            "status_dependente_alterado": (
                status_dependente_final != status_dependente_atual
            ),
        }
    )

    logger.info(
        "etapa3_destino_confirmado | acao=avancar_fluxo "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "status_dependente_anterior=%s status_dependente_final=%s "
        "status_dependente_alterado=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento,
        etapa_destino,
        status_dependente_atual,
        status_dependente_final,
        status_dependente_final != status_dependente_atual,
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento,
        etapa_destino,
    )


def _logar_tratamento(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )
