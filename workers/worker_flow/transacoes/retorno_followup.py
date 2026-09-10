"""Checkpoint de reação e persistência da repetição; nunca controla commits."""

import logging

from core.repositories.atendimento.conversas import atualizar_conversa_mensagem_cliente
from core.repositories.atendimento.followup import (
    buscar_contexto_repeticao,
    buscar_retomada,
    concluir_retomada,
    registrar_retomada,
)
from core.repositories.atendimento.historico import (
    buscar_resposta_bot_por_mensagem_cliente,
    inserir_historico_mensagem_cliente,
    inserir_historico_mensagem_bot,
)

logger = logging.getLogger("worker.retorno_followup")


def preparar_retorno_followup(mensagem, contexto_banco, cursor):
    conversa = contexto_banco["conversa"]
    id_conversa = conversa["id_conversa"]
    stage = conversa.get("followup_stage") or 0
    if stage < 0:
        raise ValueError("followup_stage negativo")
    retomada = buscar_retomada(id_conversa, mensagem, cursor)
    if stage == 0 and retomada is None:
        return None
    resposta = buscar_resposta_bot_por_mensagem_cliente(
        id_conversa,
        mensagem["id_mensagem"],
        mensagem["id_hash"],
        cursor,
    )
    # Uma resposta de turno normal já persistida tem prioridade sobre stage atual.
    if resposta and retomada is None:
        return None
    if retomada and retomada["concluida_em"] is not None and not resposta:
        raise ValueError(
            "Retomada concluída sem histórico correspondente; não reenviar"
        )
    if resposta and retomada["concluida_em"] is None:
        raise ValueError("Resposta sem confirmação atômica da retomada")
    if (
        retomada
        and not resposta
        and (
            stage != retomada["stage_anterior"]
            or conversa.get("followup_last_sent_at") != retomada["followup_em"]
            or conversa.get("id_etapa_atual") != retomada["id_etapa"]
        )
    ):
        raise ValueError("Retomada pendente pertence a outro contexto")

    dados = None
    if not resposta:
        etapa = conversa.get("id_etapa_atual")
        if type(etapa) is not int or not 1 <= etapa <= 21:
            raise ValueError("Retorno de follow-up sem etapa repetível")
        dados = buscar_contexto_repeticao(
            id_conversa, contexto_banco["id_unidade"], cursor
        )
        if retomada is None:
            registrar_retomada(conversa, mensagem, cursor)
            retomada = {
                "id_etapa": etapa,
                "stage_anterior": stage,
                "followup_em": conversa.get("followup_last_sent_at"),
                "concluida_em": None,
            }

    id_cliente_hist, recebido_em, etapa_cliente, inserido = (
        inserir_historico_mensagem_cliente(
            mensagem,
            id_conversa,
            retomada["id_etapa"],
            cursor,
        )
    )
    msg = {
        "id_mensagem": id_cliente_hist,
        "id_conversa": id_conversa,
        "id_etapa": etapa_cliente,
        "received_data_hora": recebido_em,
        "cliente_telefone": mensagem["cliente_telefone"],
        "conteudo_texto": mensagem["conteudo_texto"],
        "tipo_mensagem": mensagem["tipo_mensagem"],
        "id_hash_msg": mensagem["id_hash"],
        "id_mensagem_fila": mensagem["id_mensagem"],
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "unidade_telefone": mensagem["unidade_telefone"],
    }
    if not resposta:
        atualizar_conversa_mensagem_cliente(id_conversa, recebido_em, cursor)
    resposta_normalizada = None
    if resposta:
        resposta_normalizada = {
            "id_mensagem": resposta[0],
            "received_data_hora": resposta[3],
            "id_hash_msg": resposta[7],
        }
    logger.info(
        "resposta_followup | conversa=%s unidade=%s stage=%s etapa=%s versao=%s recuperada=%s",
        id_conversa,
        contexto_banco["id_unidade"],
        retomada["stage_anterior"],
        retomada["id_etapa"],
        conversa["lock_version"],
        bool(resposta),
    )
    return {
        "retorno_followup": True,
        "id_conversa": id_conversa,
        "id_cliente": contexto_banco["id_cliente"],
        "id_unidade": contexto_banco["id_unidade"],
        "lock_version": conversa["lock_version"],
        "id_etapa_atual": retomada["id_etapa"],
        "id_etapa_cliente": etapa_cliente,
        "id_etapa_resposta": retomada["id_etapa"],
        "stage_anterior": retomada["stage_anterior"],
        "followup_em": retomada["followup_em"],
        "dados_repeticao": dados,
        "mensagem_cliente_atual": msg,
        "mensagem_cliente_inserida": inserido,
        "resposta_bot_para_mensagem_atual": resposta_normalizada,
    }


def persistir_retorno_followup(contexto, envio, cursor):
    resposta = contexto.get("resposta_bot_para_mensagem_atual")
    if resposta:
        # Replay não zera um possível ciclo novo nem altera last_interaction_at.
        id_bot, data_bot, inserido = (
            resposta["id_mensagem"],
            resposta["received_data_hora"],
            False,
        )
    else:
        if (
            not envio.get("enviou")
            or envio.get("id_etapa_resultante") != contexto["id_etapa_atual"]
        ):
            raise ValueError("Repetição não confirmada ou mudou de etapa")
        id_bot, data_bot, inserido = inserir_historico_mensagem_bot(
            contexto, envio, cursor
        )
        concluir_retomada(contexto, data_bot, cursor)
    return {
        "historico_bot_inserido": inserido,
        "resposta_ja_existia": bool(resposta),
        "id_hash_msg_bot": envio["id_hash_msg_bot"],
        "id_historico_bot": id_bot,
        "data_historico_bot": data_bot,
        "id_etapa_resultante": contexto["id_etapa_atual"],
        "movimento_conversa": "sem_avanco",
        "atualizar_conversa": False,
        "atualizar_last_from_bot": not bool(resposta),
        "intencao_encerramento": None,
    }
