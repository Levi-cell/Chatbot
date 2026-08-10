import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa11 import (
    enviar_etapa11_contexto_invalido,
    enviar_etapa11_financeiro,
    enviar_etapa11_midia,
    enviar_etapa11_reforco_escolar,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa12 import (
    enviar_etapa12_cliente,
    enviar_etapa12_dependente,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa11 import (
    TIPOS_MENSAGEM_ACEITOS_ETAPA11,
    TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA,
    validar_etapa11,
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
    ETAPA_12_TRIAGEM_PERGUNTA_1,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- APLICAR OS TRATAMENTOS DA ETAPA 11
- ENCAMINHAR UMA CONFIRMACAO PARA A PRIMEIRA PERGUNTA DA TRIAGEM
"""


logger = logging.getLogger("worker.etapa11")


def resolve_etapa11(contexto_historico):
    """Valida a confirmação antes de iniciar a triagem cognitiva.

    Mídia, financeiro e confirmação inválida recebem tratamento sem avançar.
    Somente uma confirmação reconhecida produz a transição 11 -> 12.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]
    idade_pessoa_triagem = contexto_historico[
        "idade_pessoa_triagem"
    ]

    # VALIDANDO MÍDIA NA ETAPA 11
    # Além de interactive, o webhook reconhece o formato legado button.
    if (
        validar_midia(tipo_mensagem)
        and tipo_mensagem not in TIPOS_MENSAGEM_ACEITOS_ETAPA11
    ):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
        )
        return enviar_etapa11_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )
        return enviar_etapa11_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO PERGUNTA FINANCEIRA NA ETAPA 11
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )
        return enviar_etapa11_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO A CONFIRMAÇÃO DE INÍCIO DA TRIAGEM
    evento_transicao = validar_etapa11(texto_cliente)

    if evento_transicao is None:
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_CONFIRMACAO_INVALIDA,
        )
        return enviar_etapa11_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO DESTINO
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados={ETAPA_12_TRIAGEM_PERGUNTA_1},
    )

    logger.info(
        "etapa11_triagem_iniciada | acao=enviar_etapa12 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "tipo_mensagem=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento_transicao,
        etapa_destino,
        tipo_mensagem,
    )

    if contexto_historico.get("status_dependente"):
        contexto_envio = enviar_etapa12_dependente(
            cliente_telefone,
            phone_id_unidade,
            contexto_historico.get("nome_dependente"),
            idade_pessoa_triagem,
        )
    else:
        contexto_envio = enviar_etapa12_cliente(
            cliente_telefone,
            phone_id_unidade,
        )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
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
