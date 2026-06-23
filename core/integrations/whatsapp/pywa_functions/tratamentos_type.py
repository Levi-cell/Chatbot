import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.tratamentos import (
    CALLBACK_RETORNAR_ATENDIMENTO,
    TITULO_BOTAO_CONTINUAR,
    montar_mensagem_tipo_nao_suportado,
)
from core.integrations.whatsapp.pywa_functions.envios import (
    enviar_mensagem_texto,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender_tratamento")


def sender_tratamento_tipo_nao_suportado(
    cliente_telefone,
    phone_id_unidade,
    id_etapa,
    tipo_mensagem,
    conversa_nova,
):
    mensagem_bot = montar_mensagem_tipo_nao_suportado(conversa_nova)

    try:
        id_hash_msg_bot = enviar_mensagem_texto(
            to=cliente_telefone,
            text=mensagem_bot,
            phone_id_unidade=phone_id_unidade,
            botoes=[
                {
                    "titulo": TITULO_BOTAO_CONTINUAR,
                    "callback_data": CALLBACK_RETORNAR_ATENDIMENTO,
                }
            ],
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
            "atualizar_last_from_bot": True,
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
