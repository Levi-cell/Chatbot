import logging
from core.repositories.fireads.consulta import guardar_coletas
from core.repositories.atendimento.coleta_abertura import guardar_coletas as guardar_coleta_abertura

from core.repositories.atendimento.historico import inserir_historico_mensagem_bot
from core.repositories.seguranca.suspeita_bot import (
    incrementar_turnos_sem_avanco,
    resetar_turnos_sem_avanco,
)
from workers.worker_flow.transacoes.encerramento_atendimento import (
    resolver_intencao_encerramento,
)
from workers.worker_flow.transacoes.efeitos_transicao import (
    atualizar_banco_conforme_transicao_de_etapa,
)
from workers.worker_flow.transacoes.movimento_conversa import (
    MOVIMENTO_SEM_AVANCO,
    MOVIMENTO_TRANSICAO,
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
    3. incrementar ou zerar a suspeita de bot;
    4. aplicar os efeitos específicos da aresta;
    5. devolver o contexto final para a finalização da fila.
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

    turnos_sem_avanco = _persistir_turnos_sem_avanco(
        id_conversa=id_conversa,
        movimento=movimento,
        tratamento=bool(contexto_envio.get("tratamento")),
        historico_bot_inserido=historico_bot_inserido,
        retorno_followup=bool(contexto_historico.get("retorno_followup")),
        cursor=cursor,
    )

    efeitos_transicao = atualizar_banco_conforme_transicao_de_etapa(
        contexto_historico,
        contexto_envio,
        cursor,
    )
    guardar_coletas(contexto_historico, efeitos_transicao, cursor)
    guardar_coleta_abertura(contexto_historico, efeitos_transicao, cursor)
    intencao_encerramento = resolver_intencao_encerramento(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto "
        "id_conversa=%s id_historico_bot=%s inserido=%s "
        "resposta_ja_existia=%s movimento=%s etapa=%s evento=%s "
        "id_hash_msg_bot=%s turnos_sem_avanco=%s",
        id_conversa,
        id_historico_bot,
        historico_bot_inserido,
        resposta_ja_existia,
        movimento,
        id_etapa_resultante,
        contexto_envio.get("evento_transicao"),
        contexto_envio.get("id_hash_msg_bot"),
        turnos_sem_avanco,
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

    if turnos_sem_avanco is not None:
        contexto_final["turnos_sem_avanco"] = turnos_sem_avanco

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


def _persistir_turnos_sem_avanco(
    *,
    id_conversa,
    movimento,
    tratamento,
    historico_bot_inserido,
    cursor,
    retorno_followup=False,
):
    if movimento == MOVIMENTO_TRANSICAO:
        return resetar_turnos_sem_avanco(id_conversa, cursor)

    if (
        movimento == MOVIMENTO_SEM_AVANCO
        and tratamento
        # A primeira reação ao lembrete não penaliza o cliente.
        and not retorno_followup
        and historico_bot_inserido
    ):
        return incrementar_turnos_sem_avanco(id_conversa, cursor)

    return None


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
