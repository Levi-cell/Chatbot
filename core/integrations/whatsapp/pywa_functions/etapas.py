import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapas import (
    TITULO_BOTAO_ETAPA_1,
    montar_mensagem_etapa_1,
)
from core.integrations.whatsapp.pywa_functions.envios import (
    enviar_mensagem_texto,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender")

FUSO_HORARIO_ATENDIMENTO = ZoneInfo("America/Sao_Paulo")


def sender_etapa1(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_etapa_1(saudacao)
    titulo_botao = TITULO_BOTAO_ETAPA_1

    try:
        id_hash_msg_bot = enviar_mensagem_texto(
            to=cliente_telefone,
            text=mensagem_bot,
            phone_id_unidade=phone_id_unidade,
            botoes=[
                {
                    "titulo": titulo_botao,
                    "callback_data": titulo_botao,
                }
            ],
        )

        logger.info(
            "sender_etapa1_ok | acao=enviar_meta cliente=%s phone_number_id=%s id_hash_msg_bot=%s botao=%s saudacao=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            titulo_botao,
            saudacao,
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


def obter_saudacao_por_horario(agora=None):
    agora = agora or datetime.now(FUSO_HORARIO_ATENDIMENTO)
    hora = agora.hour

    if 5 <= hora < 12:
        return "Bom dia"

    if 12 <= hora < 18:
        return "Boa tarde"

    return "Boa noite"
