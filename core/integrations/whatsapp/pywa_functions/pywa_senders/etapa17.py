import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa17_messages import (
    montar_mensagem_etapa17,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa17")

ID_ETAPA17 = 17


# ETAPA TERMINAL: ENVIADA SOMENTE APÓS A CONFIRMAÇÃO DA ETAPA 16
def enviar_etapa17(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_etapa17()

    try:
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_bot,
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "enviar_etapa17_ok | acao=enviar_meta cliente=%s "
            "phone_number_id=%s id_hash_msg_bot=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA17,
            "tipo_mensagem": "text",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

    except Exception as erro:
        logger.exception(
            "enviar_etapa17_erro | motivo=meta_falhou "
            "acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 17",
            id_etapa=ID_ETAPA17,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
