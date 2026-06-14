import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.senders import (
    enviar_mensagem_texto_com_botao,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender")


def sender_etapa1(cliente_telefone, phone_id_unidade):
    mensagem_bot = "Ola!"
    titulo_botao = "Aperte em mim"

    try:
        id_hash_msg_bot = enviar_mensagem_texto_com_botao(
            to=cliente_telefone,
            text=mensagem_bot,
            titulo_botao=titulo_botao,
            phone_id_unidade=phone_id_unidade,
        )

        logger.info(
            "sender_etapa1_ok | acao=enviar_meta cliente=%s phone_number_id=%s id_hash_msg_bot=%s botao=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            titulo_botao,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": 1,
            "tipo_mensagem": "interactive_button",
            "canal": "meta_whatsapp",
        }

    except Exception as erro:
        logger.exception(
            "sender_etapa1_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 1",
            id_etapa=1,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
