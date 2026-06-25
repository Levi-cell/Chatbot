import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapas import (
    montar_mensagem_etapa_1,
)
from core.integrations.whatsapp.pywa_functions.envios import (
    enviar_mensagem_texto,
)
from core.integrations.whatsapp.pywa_functions.saudacao import (
    obter_saudacao_por_horario,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender")


def sender_etapa1(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_etapa_1(saudacao)

    try:
        id_hash_msg_bot = enviar_mensagem_texto(
            to=cliente_telefone,
            text=mensagem_bot,
            phone_id_unidade=phone_id_unidade,
        )

        logger.info(
            "sender_etapa1_ok | acao=enviar_meta cliente=%s phone_number_id=%s id_hash_msg_bot=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": 1,
            "tipo_mensagem": "text",
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
