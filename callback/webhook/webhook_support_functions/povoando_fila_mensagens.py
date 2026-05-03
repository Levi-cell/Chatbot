import logging
from datetime import datetime
from .Inserts import inserir_dados_na_tabela
from .Querys import buscar_timestamp_mensagem

logger = logging.getLogger(__name__)

def extrair_dados_whatsapp(data):
    try:
        entry = data.get("entry", [])[0]
        change = entry.get("changes", [])[0]
        value = change.get("value", {})

        # 🔒 Ignora se não for mensagem
        if not value.get("messages"):
            return {
                "erro": "evento_sem_mensagem",
                "raw": data
            }

        # 📌 Metadata
        metadata = value.get("metadata", {})
        unidade_telefone = metadata.get("display_phone_number")
        id_phone_unidade = metadata.get("phone_number_id")

        # 📌 Contato
        contacts = value.get("contacts", [{}])[0]
        cliente_telefone = contacts.get("wa_id")

        # 📌 Mensagem
        message = value.get("messages", [{}])[0]
        message_id = message.get("id")
        timestamp = message.get("timestamp")
        tipo = message.get("type")

        # 📌 Conteúdo (somente texto)
        conteudo_texto = None
        if tipo == "text":
            conteudo_texto = message.get("text", {}).get("body")

        # 📌 Converter timestamp
        received_data_hora = datetime.fromtimestamp(int(timestamp))

        # 🔥 Validação (agora correta)
        if not all([
            cliente_telefone,
            message_id,
            id_phone_unidade,
            unidade_telefone,
            tipo
        ]):
            return {
                "erro": "dados_incompletos",
                "raw": data
            }

        return {
            "status": "pending",
            "retry_count": 0,
            "next_attempt_at": received_data_hora,
            "processing_started_at": None,
            "received_data_hora": received_data_hora,
            "cliente_telefone": cliente_telefone,
            "conteudo_texto": conteudo_texto,
            "tipo_mensagem": tipo,  # 🔥 AGORA CORRETO
            "id_hash_msg": message_id,
            "id_phone_unidade": id_phone_unidade,
            "unidade_telefone": unidade_telefone,
        }

    except (IndexError, KeyError, TypeError, ValueError) as erro:
        return {
            "erro": "exception",
            "detalhe": str(erro),
            "raw": data
        }

def povoando_fila(data):
    dict_msg = extrair_dados_whatsapp(data)

    if dict_msg.get("erro"):
        logger.warning(
            f"Erro ao extrair dados | tipo={dict_msg.get('erro')}"
        )
        return False

    id_hash = dict_msg['id_hash_msg']

    logger.info(f"Iniciando enfileiramento | id_msg={id_hash}")

    sucesso = inserir_dados_na_tabela(dict_msg)

    if sucesso:
        logger.info(f"Mensagem enfileirada com sucesso | id_msg={id_hash}")
    else:
        logger.error(f"Falha ao inserir na fila | id_msg={id_hash}")

    buscar_timestamp_mensagem(id_hash) # APENAS PARA DEBUG

    return
