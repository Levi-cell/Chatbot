import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa7_messages import (
    montar_mensagem_oferta_adiada_etapa7,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa7")

ID_ETAPA7 = 7


# CENARIO NORMAL: CLIENTE ADIOU A OFERTA NA ETAPA 6
def enviar_etapa7(
    cliente_telefone,
    phone_id_unidade,
    link_instagram,
):
    mensagem_bot = montar_mensagem_oferta_adiada_etapa7(
        link_instagram
    )

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7",
    )


# CONSTRUTOR DE ENVIO DE TEXTO DA ETAPA 7
def _enviar_texto_etapa7(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
):
    try:
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_bot,
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s "
            "id_hash_msg_bot=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA7,
            "tipo_mensagem": "text",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

    except Exception as erro:
        logger.exception(
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s "
            "phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 7",
            id_etapa=ID_ETAPA7,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
