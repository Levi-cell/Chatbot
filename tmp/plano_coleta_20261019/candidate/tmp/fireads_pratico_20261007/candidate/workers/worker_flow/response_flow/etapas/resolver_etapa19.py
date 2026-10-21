"""Uma mensagem textual após o repasse apresenta a pergunta de satisfação."""

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa19 import (
    enviar_etapa19,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa21 import (
    enviar_etapa21,
)
from core.validacoes.turno import validar_turno
from workers.worker_flow.response_flow.contato_comercial import (
    preparar_mensagem_comercial,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa19 import (
    validar_etapa19,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_21_PESQUISA_SATISFACAO,
    EVENTO_AVALIACAO_SOLICITADA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


def resolve_etapa19(contexto_historico):
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    if not validar_etapa19(
        contexto_historico.get("texto_cliente_atual"),
        contexto_historico.get("tipo_mensagem_atual"),
    ):
        # Mídia não contém a manifestação textual solicitada para começar a pesquisa.
        turno = validar_turno(contexto_historico.get("turno"))
        return enviar_etapa19(
            mensagem_cliente["cliente_telefone"],
            mensagem_cliente["id_phone_unidade"],
            contexto_historico["numero_comercial_unidade"],
            preparar_mensagem_comercial(contexto_historico, turno=turno),
            (
                contexto_historico.get("nome_dependente")
                if contexto_historico["status_dependente"]
                else None
            ),
            pedir_texto=True,
        )

    # VALIDANDO DESTINO
    # Não interpretar o texto (mesmo '5') como nota antes de fazer a pergunta.
    destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_AVALIACAO_SOLICITADA,
        destinos_esperados={ETAPA_21_PESQUISA_SATISFACAO},
    )
    envio = enviar_etapa21(
        mensagem_cliente["cliente_telefone"],
        mensagem_cliente["id_phone_unidade"],
        contexto_historico["nome_cliente"],
    )
    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        envio,
        EVENTO_AVALIACAO_SOLICITADA,
        destino,
    )
