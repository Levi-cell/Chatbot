"""Valida um turno e prepara a entrega ao comercial, sem gravar no banco."""

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa18 import (
    enviar_etapa18,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa19 import (
    enviar_etapa19,
)
from workers.worker_flow.response_flow.contato_comercial import (
    preparar_mensagem_comercial,
)
from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import (
    validar_etapa18,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    EVENTO_TURNO_ESCOLHIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


def resolve_etapa18(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    status_dependente = contexto_historico.get("status_dependente")
    if not isinstance(status_dependente, bool):
        raise ValueError("Destino de atendimento ausente na escolha de turno")
    nome_dependente = (
        contexto_historico.get("nome_dependente") if status_dependente else None
    )
    if status_dependente and not nome_dependente:
        raise ValueError("Nome do dependente ausente na escolha de turno")

    tratamento = None
    if validar_midia(tipo_mensagem):
        tratamento = "midia"
    elif validar_duvida_reforco_escolar(texto_cliente):
        tratamento = "reforco_escolar"
    elif validar_pergunta_financeira(texto_cliente):
        tratamento = "financeiro"
    turno = (
        validar_etapa18(texto_cliente, tipo_mensagem) if tratamento is None else None
    )
    if turno is None:
        if tratamento is None and contexto_historico.get("retorno_followup"):
            return enviar_repeticao_followup(contexto_historico)
        return enviar_etapa18(
            mensagem_cliente["cliente_telefone"],
            mensagem_cliente["id_phone_unidade"],
            nome_dependente,
            tratamento=tratamento or "contexto_invalido",
        )

    # VALIDANDO DESTINO
    destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_TURNO_ESCOLHIDO,
        destinos_esperados={ETAPA_19_ENCAMINHAMENTO_COMERCIAL},
    )
    envio = enviar_etapa19(
        mensagem_cliente["cliente_telefone"],
        mensagem_cliente["id_phone_unidade"],
        contexto_historico["numero_comercial_unidade"],
        preparar_mensagem_comercial(contexto_historico, turno=turno),
        nome_dependente,
    )
    envio["turno"] = turno
    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        envio,
        EVENTO_TURNO_ESCOLHIDO,
        destino,
    )
