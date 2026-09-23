"""Processa a reação ao lembrete com os mesmos validadores do turno normal."""

from core.integrations.whatsapp.messages.tratamentos.retorno_followup import (
    montar_saudacao_retomada_followup,
)
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)


def enviar_retorno_followup(contexto):
    if contexto.get("resposta_bot_para_mensagem_atual"):
        # Recupera somente o resultado salvo, sem interpretar outra vez a reação.
        return enviar_repeticao_followup(contexto)

    nome_titular = (
        None
        if contexto["id_etapa_atual"] == 1
        else contexto["dados_repeticao"].get("nome_titular")
    )
    contexto = dict(
        contexto,
        saudacao_retorno=montar_saudacao_retomada_followup(nome_titular),
    )
    # Cada resolver mantém suas prioridades e transições. Só o contexto inválido
    # genérico usa a repetição neutra; tratamentos específicos seguem normais.
    return flow_sender(contexto)
