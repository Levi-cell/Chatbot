"""Checkpoint da reação validada ao follow-up; nunca controla commits."""

import logging

from core.repositories.atendimento.followup import (
    buscar_contexto_repeticao,
    buscar_retomada,
    concluir_retomada,
    registrar_retomada,
)
from core.repositories.atendimento.historico import (
    buscar_resposta_bot_por_mensagem_cliente,
    inserir_historico_mensagem_cliente,
)

from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_9_RETORNO_OFERTA,
    EVENTO_CLIENTE_RETORNOU,
)
from workers.worker_flow.transacoes.persistencia_resposta import (
    atualizar_banco_com_contexto_final,
)
from workers.worker_flow.valida_historico import valida_historico

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

        # Reutiliza os dados, o histórico e o mapa do atendimento normal.
        # A saudação de 3h não concorre com a saudação deste retorno.
        contexto = valida_historico(
            mensagem, contexto_banco, cursor, retorno_followup=True
        )
        if contexto.get("resposta_bot_para_mensagem_atual"):
            raise ValueError("Resposta apareceu sem confirmação da retomada")
        contexto.update(
            retorno_followup=True,
            lock_version=conversa["lock_version"],
            stage_anterior=retomada["stage_anterior"],
            followup_em=retomada["followup_em"],
            dados_repeticao=dados,
        )
        logger.info(
            "resposta_followup | conversa=%s unidade=%s stage=%s etapa=%s versao=%s recuperada=False",
            id_conversa,
            contexto_banco["id_unidade"],
            retomada["stage_anterior"],
            etapa,
            conversa["lock_version"],
        )
        return contexto

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
    resposta_normalizada = {
        "id_mensagem": resposta[0],
        "id_etapa": resposta[2],
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
    contexto = {
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
    return contexto


def persistir_retorno_followup(contexto, envio, cursor):
    resposta = contexto.get("resposta_bot_para_mensagem_atual")
    if not resposta:
        if not envio.get("enviou") or envio.get("resposta_ja_existia"):
            raise ValueError("Retorno de follow-up sem envio confirmado")
        if contexto["id_etapa_atual"] == ETAPA_8_OFERTA_ADIADA:
            _validar_retorno_etapa8(envio)
        final = atualizar_banco_com_contexto_final(contexto, envio, cursor)
        concluir_retomada(
            contexto,
            final["data_historico_bot"],
            cursor,
            id_etapa_resultante=final["id_etapa_resultante"],
        )
        return final
    # Replay não zera um possível ciclo novo nem altera last_interaction_at.
    return {
        "historico_bot_inserido": False,
        "resposta_ja_existia": True,
        "id_hash_msg_bot": envio["id_hash_msg_bot"],
        "id_historico_bot": resposta["id_mensagem"],
        "data_historico_bot": resposta["received_data_hora"],
        # Inclui repetições da versão antiga e avanços válidos da versão atual.
        "id_etapa_resultante": resposta.get("id_etapa", contexto["id_etapa_atual"]),
        "movimento_conversa": "sem_avanco",
        "atualizar_conversa": False,
        "atualizar_last_from_bot": False,
        "intencao_encerramento": None,
    }


def _validar_retorno_etapa8(envio):
    """A reação da etapa 8 abre a etapa 9, nunca responde à oferta seguinte."""
    if (
        not envio.get("enviou")
        or envio.get("resposta_ja_existia")
        or envio.get("tratamento")
        or envio.get("id_etapa_origem_transicao") != ETAPA_8_OFERTA_ADIADA
        or envio.get("evento_transicao") != EVENTO_CLIENTE_RETORNOU
        or envio.get("id_etapa_resultante") != ETAPA_9_RETORNO_OFERTA
    ):
        raise ValueError("Retorno de follow-up da etapa 8 exige a transição 8 -> 9")
