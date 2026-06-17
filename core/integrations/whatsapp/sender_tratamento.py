import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.senders import (
    enviar_mensagem_texto_com_botao,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender_tratamento")


def sender_tratamento_tipo_nao_suportado(
    cliente_telefone,
    phone_id_unidade,
    id_etapa,
    tipo_mensagem,
    mensagem_bot,
):
    titulo_botao = "Retornar ao atendimento"

    try:
        id_hash_msg_bot = enviar_mensagem_texto_com_botao(
            to=cliente_telefone,
            text=mensagem_bot,
            titulo_botao=titulo_botao,
            phone_id_unidade=phone_id_unidade,
            callback_data="retornar_atendimento",
        )

        logger.info(
            "sender_tratamento_tipo_nao_suportado_ok | acao=enviar_meta cliente=%s phone_number_id=%s etapa=%s tipo_cliente=%s id_hash_msg_bot=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_etapa,
            tipo_mensagem,
            id_hash_msg_bot,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": id_etapa,
            "tipo_mensagem": "interactive_button",
            "canal": "meta_whatsapp",
            "tratamento": True,
            "tipo_tratamento": "tipo_mensagem_nao_suportado",
            "atualizar_conversa": False,
        }

    except Exception as erro:
        logger.exception(
            "sender_tratamento_tipo_nao_suportado_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s etapa=%s tipo_cliente=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_etapa,
            tipo_mensagem,
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar tratamento de tipo de mensagem nao suportado",
            id_etapa=id_etapa,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
