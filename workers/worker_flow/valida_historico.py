import logging

from core.logging_config import short_value
from core.repositories.inserts import inserir_historico_mensagem_cliente
from core.repositories.querys import buscar_resposta_bot_por_mensagem_cliente
from core.repositories.updates import (
    atualizar_conversa_mensagem_cliente,
    atualizar_conversa_resposta_bot_sem_avancar,
)


logger = logging.getLogger("worker.valida_historico")

ETAPA_INICIAL = 1
ETAPA_FINAL = 7


def valida_historico(mensagem, contexto_banco, cursor):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    last_message_from_entrada = contexto_conversa.get("last_message_from")
    id_etapa_para_insert = _resolver_etapa_cliente(contexto_conversa)

    (
        id_historico_cliente,
        data_historico_cliente,
        id_etapa_cliente,
        cliente_inserido_no_historico,
    ) = inserir_historico_mensagem_cliente(
        mensagem=mensagem,
        id_conversa=id_conversa,
        id_etapa=id_etapa_para_insert,
        cursor=cursor,
    )

    mensagem_cliente_atual = {
        "id_mensagem": id_historico_cliente,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa_cliente,
        "received_data_hora": data_historico_cliente,
        "cliente_telefone": mensagem["cliente_telefone"],
        "conteudo_texto": mensagem["conteudo_texto"],
        "tipo_mensagem": mensagem["tipo_mensagem"],
        "id_hash_msg": mensagem["id_hash"],
        "id_mensagem_fila": mensagem["id_mensagem"],
        "id_hash_cliente_origem": None,
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "unidade_telefone": mensagem["unidade_telefone"],
        "quem_enviou": "cliente",
        "status_envio": None,
    }

    resposta_bot_para_mensagem_atual = _normalizar_resposta_bot(
        buscar_resposta_bot_por_mensagem_cliente(
            id_conversa=id_conversa,
            id_mensagem_fila=mensagem["id_mensagem"],
            id_hash_cliente_origem=mensagem["id_hash"],
            cursor=cursor,
        )
    )

    if resposta_bot_para_mensagem_atual:
        id_etapa_resposta = resposta_bot_para_mensagem_atual["id_etapa"]

        if last_message_from_entrada != "bot":
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                resposta_bot_para_mensagem_atual["received_data_hora"],
                cursor,
            )

        last_message_from_saida = "bot"
    else:
        id_etapa_resposta = _resolver_etapa_resposta(contexto_conversa)
        atualizar_conversa_mensagem_cliente(
            id_conversa,
            data_historico_cliente,
            cursor,
        )
        last_message_from_saida = "cliente"

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s last_from_entrada=%s last_from_saida=%s retry=%s resposta_bot_existente=%s cliente=%s phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        last_message_from_entrada,
        last_message_from_saida,
        mensagem["retry_count"],
        bool(resposta_bot_para_mensagem_atual),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    return {
        "id_conversa": id_conversa,
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        "id_etapa_resposta": id_etapa_resposta,
        "status_dependente": contexto_conversa.get("status_dependente"),
        "last_message_from": last_message_from_saida,
        "last_message_from_entrada": last_message_from_entrada,
        "mensagem_cliente_atual": mensagem_cliente_atual,
        "mensagem_cliente_inserida": cliente_inserido_no_historico,
        "resposta_bot_para_mensagem_atual": resposta_bot_para_mensagem_atual,
        "texto_cliente_atual": mensagem["conteudo_texto"],
        "tipo_mensagem_atual": mensagem["tipo_mensagem"],
        "retry_count": mensagem["retry_count"],
        "precisa_tratamento_erro": False,
        "motivo_tratamento_erro": None,
    }


def _resolver_etapa_cliente(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return id_etapa_atual


def _resolver_etapa_resposta(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return min(id_etapa_atual + 1, ETAPA_FINAL)


def _normalizar_linha_historico(registro):
    (
        id_mensagem,
        id_conversa,
        id_etapa,
        received_data_hora,
        cliente_telefone,
        conteudo_texto,
        tipo_mensagem,
        id_hash_msg,
        id_mensagem_fila,
        id_hash_cliente_origem,
        id_phone_unidade,
        unidade_telefone,
        quem_enviou,
        status_envio,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa,
        "received_data_hora": received_data_hora,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_hash_msg": id_hash_msg,
        "id_mensagem_fila": id_mensagem_fila,
        "id_hash_cliente_origem": id_hash_cliente_origem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "quem_enviou": quem_enviou,
        "status_envio": status_envio,
    }


def _normalizar_resposta_bot(registro):
    if not registro:
        return None

    return _normalizar_linha_historico(registro)
