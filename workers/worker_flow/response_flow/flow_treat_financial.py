import logging

from core.integrations.whatsapp.pywa_functions.tratamentos_financeiros import (
    sender_tratamento_financeiro,
)


logger = logging.getLogger("worker.treat_financial")


def flow_treat_financial(contexto_historico, contexto_validacao):
    # Tratamento financeiro responde a duvida e reapresenta a etapa atual.
    id_conversa = contexto_historico["id_conversa"]
    retry_count = contexto_historico["retry_count"]
    id_etapa_cliente = contexto_historico["id_etapa_cliente"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_financial_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_cliente=%s tratamento=%s retry=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_cliente,
            contexto_validacao["tipo_tratamento"],
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
            "tratamento": True,
            "tipo_tratamento": contexto_validacao["tipo_tratamento"],
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

    if retry_count > 1:
        logger.info(
            "flow_treat_financial_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s tratamento=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            retry_count,
            contexto_validacao["tipo_tratamento"],
        )

    return sender_tratamento_financeiro(
        cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
        phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
        id_etapa=id_etapa_cliente,
        conversa_nova=contexto_historico.get("id_etapa_atual") is None,
    )
