import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa19 import (
    enviar_etapa19,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa18 import (
    normalizar_comentario_etapa18,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_19_FINALIZACAO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- NORMALIZAR O COMENTARIO OPCIONAL DA PESQUISA
- ENCAMINHAR QUALQUER INTERACAO PARA A FINALIZACAO AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa18")


def resolve_etapa18(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # TEXTO UTIL E SALVO; MIDIA OU RECUSA EXPLICITA GERAM COMENTARIO NULO.
    comentario_satisfacao = normalizar_comentario_etapa18(
        texto_cliente,
        tipo_mensagem,
    )

    # VALIDANDO DESTINO
    # A etapa 18 aceita qualquer interacao e possui um unico destino.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        destinos_esperados={ETAPA_19_FINALIZACAO},
    )

    logger.info(
        "etapa18_comentario_recebido | acao=enviar_etapa19 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s comentario_preenchido=%s tipo=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        etapa_destino,
        bool(comentario_satisfacao),
        tipo_mensagem,
    )

    contexto_envio = enviar_etapa19(
        cliente_telefone,
        phone_id_unidade,
    )
    contexto_envio["comentario_satisfacao"] = comentario_satisfacao

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
        etapa_destino,
    )
