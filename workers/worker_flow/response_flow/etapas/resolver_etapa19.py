import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa19 import (
    enviar_etapa19_contexto_invalido,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa20 import (
    enviar_etapa20,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa19 import (
    TIPO_TRATAMENTO_SATISFACAO_INVALIDA,
    validar_etapa19,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_20_DECISAO_COMENTARIO,
    EVENTO_SATISFACAO_AVALIADA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR UMA UNICA NOTA DA PESQUISA DE SATISFACAO
- ENCAMINHAR PARA A DECISAO DE COMENTARIO AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa19")


def resolve_etapa19(contexto_historico):
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # VALIDANDO A NOTA DA PESQUISA
    nota_satisfacao = validar_etapa19(texto_cliente)

    if nota_satisfacao is None:
        _logar_tratamento_contexto(contexto_historico)
        return enviar_etapa19_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO DESTINO
    # A etapa 19 produz um unico evento e um unico destino.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_SATISFACAO_AVALIADA,
        destinos_esperados={ETAPA_20_DECISAO_COMENTARIO},
    )

    logger.info(
        "etapa19_satisfacao_validada | acao=enviar_etapa20 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s nota=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_SATISFACAO_AVALIADA,
        etapa_destino,
        nota_satisfacao,
    )

    contexto_envio = enviar_etapa20(
        cliente_telefone,
        phone_id_unidade,
    )
    contexto_envio["nota_satisfacao"] = nota_satisfacao

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_SATISFACAO_AVALIADA,
        etapa_destino,
    )


def _logar_tratamento_contexto(contexto_historico):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        TIPO_TRATAMENTO_SATISFACAO_INVALIDA,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )
