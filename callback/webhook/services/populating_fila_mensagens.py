import logging
from datetime import datetime

from core.logging_config import short_value
from core.repositories.turno_cliente import avaliar_turno_cliente_para_fila


logger = logging.getLogger("webhook.fila")


def inserir_dados_na_tabela_fila(dados, cursor):
    if not dados or dados.get("erro"):
        logger.warning("fila_insert_ignorado | motivo=dados_invalidos acao=nao_inserir")
        return {
            "status": "ignored",
            "reason": "dados_invalidos",
        }

    turno = avaliar_turno_cliente_para_fila(
        cursor=cursor,
        cliente_telefone=dados["cliente_telefone"],
        id_phone_unidade=dados["id_phone_unidade"],
        usar_lock=True,
    )

    if not turno["pode_enfileirar"]:
        if turno["motivo"] == "fila_aberta_sem_resposta_bot":
            logger.info(
                "mensagem_ignorada | motivo=fila_aberta_pending_processing acao=nao_enfileirar cliente=%s phone_number_id=%s detalhe=ja_existe_mensagem_pending_ou_processing",
                short_value(dados["cliente_telefone"]),
                short_value(dados["id_phone_unidade"]),
            )
        else:
            logger.info(
                "fila_insert_ignorado | motivo=%s acao=nao_inserir_turno cliente=%s phone_number_id=%s",
                turno["motivo"],
                short_value(dados["cliente_telefone"]),
                short_value(dados["id_phone_unidade"]),
            )

        return {
            "status": "ignored",
            "reason": turno["motivo"],
        }

    cursor.execute("""
        INSERT INTO chatbot.fila_mensagens (
            status,
            retry_count,
            next_attempt_at,
            processing_started_at,
            received_data_hora,
            cliente_telefone,
            conteudo_texto,
            tipo_mensagem,
            id_hash_msg,
            id_phone_unidade,
            unidade_telefone
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT DO NOTHING
    """, (
        dados["status"],
        dados["retry_count"],
        dados["next_attempt_at"],
        dados["processing_started_at"],
        dados["received_data_hora"],
        dados["cliente_telefone"],
        dados["conteudo_texto"],
        dados["tipo_mensagem"],
        dados["id_hash_msg"],
        dados["id_phone_unidade"],
        dados["unidade_telefone"],
    ))

    if cursor.rowcount == 0:
        logger.info(
            "fila_insert_ignorado | motivo=conflito_unico acao=nao_inserir id_msg=%s cliente=%s phone_number_id=%s",
            short_value(dados["id_hash_msg"]),
            short_value(dados["cliente_telefone"]),
            short_value(dados["id_phone_unidade"]),
        )
        return {
            "status": "ignored",
            "reason": "conflito_unico",
        }

    return {
        "status": "inserted",
        "reason": None,
    }


def extrair_dados_whatsapp(data):
    try:
        entry = data.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})

        if not value.get("messages"):
            return {
                "erro": "evento_sem_mensagem",
                "raw": data,
            }

        metadata = value.get("metadata", {})
        unidade_telefone = metadata.get("display_phone_number")
        id_phone_unidade = metadata.get("phone_number_id")

        contacts = value.get("contacts", [{}])[0]
        cliente_telefone = contacts.get("wa_id")

        message = value.get("messages", [{}])[0]
        message_id = message.get("id")
        timestamp = message.get("timestamp")
        tipo = message.get("type")
        conteudo_texto = extrair_conteudo_texto_mensagem(message, tipo)

        received_data_hora = datetime.fromtimestamp(int(timestamp))

        if not all([
            cliente_telefone,
            message_id,
            id_phone_unidade,
            unidade_telefone,
            tipo,
        ]):
            return {
                "erro": "dados_incompletos",
                "raw": data,
            }

        return {
            "status": "pending",
            "retry_count": 0,
            "next_attempt_at": received_data_hora,
            "processing_started_at": None,
            "received_data_hora": received_data_hora,
            "cliente_telefone": cliente_telefone,
            "conteudo_texto": conteudo_texto,
            "tipo_mensagem": tipo,
            "id_hash_msg": message_id,
            "id_phone_unidade": id_phone_unidade,
            "unidade_telefone": unidade_telefone,
        }

    except (IndexError, KeyError, TypeError, ValueError) as erro:
        return {
            "erro": "exception",
            "detalhe": str(erro),
            "raw": data,
        }


def extrair_conteudo_texto_mensagem(message, tipo):
    if tipo == "text":
        return message.get("text", {}).get("body")

    if tipo == "interactive":
        return extrair_conteudo_interactive(message.get("interactive", {}))

    if tipo == "button":
        return extrair_conteudo_button(message.get("button", {}))

    return None


def extrair_conteudo_interactive(interactive):
    tipo_interactive = interactive.get("type")

    if tipo_interactive == "button_reply":
        button_reply = interactive.get("button_reply", {})
        return button_reply.get("title") or button_reply.get("id")

    if tipo_interactive == "list_reply":
        list_reply = interactive.get("list_reply", {})
        return list_reply.get("title") or list_reply.get("id")

    return None


def extrair_conteudo_button(button):
    return button.get("text") or button.get("payload")


def preparar_dados_fila(data):
    dados = extrair_dados_whatsapp(data)

    if dados.get("erro"):
        logger.warning(
            "fila_extracao_falhou | motivo=%s acao=nao_enfileirar",
            dados.get("erro"),
        )
        return {
            "status": "ignored",
            "reason": dados.get("erro"),
            "dados": None,
        }

    logger.info(
        "fila_recebida | acao=preparar_insert id_msg=%s cliente=%s phone_number_id=%s tipo=%s",
        short_value(dados["id_hash_msg"]),
        short_value(dados["cliente_telefone"]),
        short_value(dados["id_phone_unidade"]),
        dados["tipo_mensagem"],
    )
    return {
        "status": "ready",
        "reason": None,
        "dados": dados,
    }


def povoando_fila(dados, cursor):
    return inserir_dados_na_tabela_fila(dados, cursor)
