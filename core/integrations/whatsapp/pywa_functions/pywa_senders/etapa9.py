import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA9_TRIAGEM,
)
from core.integrations.whatsapp.messages.etapa9_messages import (
    montar_botoes_etapa9,
    montar_mensagem_triagem_cognitiva_etapa9,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa9")

ID_ETAPA9 = 9


# CENARIO NORMAL: APRESENTA E INICIA A TRIAGEM COGNITIVA
def enviar_etapa9(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_triagem_cognitiva_etapa9()

    try:
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_bot,
            header=CABECALHO_ETAPA9_TRIAGEM,
            buttons=_montar_botoes_pywa_etapa9(),
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "enviar_etapa9_ok | acao=enviar_meta cliente=%s "
            "phone_number_id=%s id_hash_msg_bot=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "cabecalho_mensagem": CABECALHO_ETAPA9_TRIAGEM,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA9,
            "tipo_mensagem": "interactive_button",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

    except Exception as erro:
        logger.exception(
            "enviar_etapa9_erro | motivo=meta_falhou "
            "acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 9",
            id_etapa=ID_ETAPA9,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa9():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa9()
    ]
