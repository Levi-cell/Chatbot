import logging
from datetime import datetime

from core.database.connection_aws import get_conn
from core.logging_config import short_value


logger = logging.getLogger("webhook.fila")


def inserir_dados_na_tabela_fila(dados):
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        if not dados or dados.get("erro"):
            logger.warning("fila_insert_ignorado | motivo=dados_invalidos")
            return False

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
            ON CONFLICT (id_hash_msg) DO NOTHING
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

        conn.commit()

        if cursor.rowcount == 0:
            logger.info(
                "fila_duplicada | id_msg=%s cliente=%s unidade=%s",
                short_value(dados["id_hash_msg"]),
                dados["cliente_telefone"],
                dados["id_phone_unidade"],
            )
        else:
            logger.info(
                "fila_insert_ok | id_msg=%s cliente=%s unidade=%s tipo=%s",
                short_value(dados["id_hash_msg"]),
                dados["cliente_telefone"],
                dados["id_phone_unidade"],
                dados["tipo_mensagem"],
            )

        return True

    except Exception:
        if conn:
            conn.rollback()

        logger.exception(
            "fila_insert_erro | id_msg=%s",
            short_value(dados.get("id_hash_msg") if dados else None),
        )
        return False

    finally:
        if conn:
            conn.close()


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

        conteudo_texto = None
        if tipo == "text":
            conteudo_texto = message.get("text", {}).get("body")

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


def povoando_fila(data):
    dados = extrair_dados_whatsapp(data)

    if dados.get("erro"):
        logger.warning("fila_extracao_falhou | motivo=%s", dados.get("erro"))
        return False

    id_hash = dados["id_hash_msg"]

    logger.info(
        "fila_recebida | id_msg=%s cliente=%s unidade=%s tipo=%s",
        short_value(id_hash),
        dados["cliente_telefone"],
        dados["id_phone_unidade"],
        dados["tipo_mensagem"],
    )

    sucesso = inserir_dados_na_tabela_fila(dados)

    if not sucesso:
        logger.error("fila_enfileirar_falhou | id_msg=%s", short_value(id_hash))

    return sucesso
