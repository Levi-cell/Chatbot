import logging

from core.repositories.inserts import inserir_historico_mensagem_bot
from workers.worker_flow.transacoes.encerramento_atendimento import (
    resolver_intencao_encerramento,
)
from workers.worker_flow.transacoes.efeitos_transicao import (
    atualizar_banco_conforme_transicao_de_etapa,
)
from workers.worker_flow.transacoes.movimento_conversa import (
    MOVIMENTO_SEM_AVANCO,
    persistir_movimento_conversa,
)


logger = logging.getLogger("worker.support")


def _obter_data_interacao_bot_existente(contexto_historico):
    resposta_bot = (
        contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    )
    data_interacao = resposta_bot.get("received_data_hora")

    if data_interacao is None:
        raise ValueError(
            "Resposta do bot existente sem received_data_hora persistido"
        )

    return data_interacao


def atualizar_banco_com_contexto_final(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste o resultado completo do ciclo em uma única transação.

    Ordem preservada:
    1. registrar ou recuperar a resposta do bot;
    2. persistir inicialização, transição ou permanência;
    3. aplicar os efeitos específicos da aresta;
    4. devolver o contexto final para a finalização da fila.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    resposta_ja_existia = bool(
        contexto_envio.get("resposta_ja_existia")
    )

    (
        id_historico_bot,
        data_interacao_bot,
        historico_bot_inserido,
    ) = _persistir_ou_recuperar_resposta_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    movimento = persistir_movimento_conversa(
        contexto_historico,
        contexto_envio,
        data_interacao_bot,
        cursor,
    )

    efeitos_transicao = atualizar_banco_conforme_transicao_de_etapa(
        contexto_historico,
        contexto_envio,
        cursor,
    )
    intencao_encerramento = resolver_intencao_encerramento(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto id_conversa=%s id_historico_bot=%s inserido=%s resposta_ja_existia=%s movimento=%s etapa=%s evento=%s id_hash_msg_bot=%s",
        id_conversa,
        id_historico_bot,
        historico_bot_inserido,
        resposta_ja_existia,
        movimento,
        id_etapa_resultante,
        contexto_envio.get("evento_transicao"),
        contexto_envio.get("id_hash_msg_bot"),
    )

    contexto_final = {
        "historico_bot_inserido": historico_bot_inserido,
        "resposta_ja_existia": resposta_ja_existia,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "movimento_conversa": movimento,
        "atualizar_conversa": movimento != MOVIMENTO_SEM_AVANCO,
        "atualizar_last_from_bot": True,
        "intencao_encerramento": intencao_encerramento,
    }

    if id_historico_bot is not None:
        contexto_final.update(
            {
                "id_historico_bot": id_historico_bot,
                "data_historico_bot": data_interacao_bot,
            }
        )

    if efeitos_transicao:
        contexto_final["efeitos_transicao"] = efeitos_transicao

    return contexto_final


def _persistir_ou_recuperar_resposta_bot(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("resposta_ja_existia"):
        return (
            None,
            _obter_data_interacao_bot_existente(contexto_historico),
            False,
        )

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    return inserir_historico_mensagem_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )
