def extrair_id_hash_msg_bot(sent_message):
    """
    Extrai o identificador retornado pela PyWa ou pela resposta bruta da Meta.

    A ausência do ID após confirmação de envio é uma falha de contrato: sem
    ele, o worker não consegue registrar a resposta com segurança.
    """
    id_hash = getattr(sent_message, "id", None)
    if id_hash:
        return id_hash

    if isinstance(sent_message, dict):
        mensagens = sent_message.get("messages") or []
        if mensagens:
            id_hash = mensagens[0].get("id")
            if id_hash:
                return id_hash

    raise ValueError("Meta confirmou envio, mas nao retornou id da mensagem")
