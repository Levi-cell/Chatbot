import logging

from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa18 import enviar_etapa18
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa19 import enviar_etapa19
from core.validacoes.turno import validar_turno
from workers.worker_flow.response_flow.contato_comercial import preparar_mensagem_comercial

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa17 import (
    enviar_etapa17_cliente_contexto_invalido,
    enviar_etapa17_dependente_contexto_invalido,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa20 import (
    enviar_etapa20,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    TIPO_TRATAMENTO_RESPOSTA_TRIAGEM_INVALIDA,
    validar_resposta_triagem,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_18_ESCOLHA_TURNO,
    ETAPA_19_ENCAMINHAMENTO_COMERCIAL,
    ETAPA_20_AGENDAMENTO,
    EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK,
    EVENTO_TRIAGEM_CONCLUIDA_TURNO_COLETADO,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A RESPOSTA DA PERGUNTA 6
- ESCOLHER TURNO OU PLATAFORMA CONFORME O LINK ATUAL E O MAPA
"""


logger = logging.getLogger("worker.etapa17")


def resolve_etapa17(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(contexto_historico.get("status_dependente"))
    nome_dependente = contexto_historico.get("nome_dependente")
    idade_pessoa_triagem = contexto_historico[
        "idade_pessoa_triagem"
    ]
    link_agendamento = contexto_historico.get(
        "link_agendamento_unidade"
    )
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # VALIDANDO A OPCAO DA PERGUNTA 6
    resposta_triagem = validar_resposta_triagem(
        texto_cliente,
        tipo_mensagem,
    )

    if resposta_triagem is None:
        if contexto_historico.get("retorno_followup"):
            return enviar_repeticao_followup(contexto_historico)
        _logar_tratamento_contexto(contexto_historico)

        if status_dependente:
            return enviar_etapa17_dependente_contexto_invalido(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
                idade_pessoa_triagem,
            )

        return enviar_etapa17_cliente_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    turno = contexto_historico.get('turno')
    if link_agendamento:
        evento = EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA
    elif turno is not None:
        validar_turno(turno)
        evento = EVENTO_TRIAGEM_CONCLUIDA_TURNO_COLETADO
    else:
        evento = EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK
    # VALIDANDO DESTINOS
    # O contexto leu o link atual da unidade neste ciclo; não congelamos a configuração.
    etapa_destino = resolver_destino_transicao(
        contexto_historico, evento,
        destinos_esperados=_destinos_esperados_por_evento(evento),
    )
    if etapa_destino == ETAPA_18_ESCOLHA_TURNO:
        contexto_envio = enviar_etapa18(
            cliente_telefone, phone_id_unidade,
            nome_dependente if status_dependente else None,
        )
    elif etapa_destino == ETAPA_19_ENCAMINHAMENTO_COMERCIAL:
        contexto_envio = enviar_etapa19(
            cliente_telefone, phone_id_unidade,
            contexto_historico['numero_comercial_unidade'],
            preparar_mensagem_comercial(contexto_historico, turno=turno),
            nome_dependente if status_dependente else None,
        )
    else:
        contexto_envio = enviar_etapa20(
            cliente_telefone, phone_id_unidade, link_agendamento,
            nome_dependente=nome_dependente if status_dependente else None,
        )
    contexto_envio["resposta_triagem"] = resposta_triagem
    logger.info("triagem_concluida | id_conversa=%s destino=%s", contexto_historico["id_conversa"], etapa_destino)
    return anexar_transicao_ao_contexto_envio(
        contexto_historico, contexto_envio, evento, etapa_destino,
    )


def _destinos_esperados_por_evento(evento):
    return {
        EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA: {ETAPA_20_AGENDAMENTO},
        EVENTO_TRIAGEM_CONCLUIDA_SEM_LINK: {ETAPA_18_ESCOLHA_TURNO},
        EVENTO_TRIAGEM_CONCLUIDA_TURNO_COLETADO: {ETAPA_19_ENCAMINHAMENTO_COMERCIAL},
    }[evento]



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
