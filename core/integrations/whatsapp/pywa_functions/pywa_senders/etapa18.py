"""Transporte da escolha de turno, sem validação da resposta ou persistência."""

import logging
from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa18_messages import (
    montar_botoes_etapa18,
    montar_mensagem_etapa18,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)

logger = logging.getLogger("whatsapp.etapa18")


def enviar_etapa18(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente=None,
    *,
    tratamento=None,
    repeticao=False,
):
    texto = montar_mensagem_etapa18(
        nome_dependente, tratamento=tratamento, repeticao=repeticao
    )
    try:
        resposta = conta_wa(phone_id_unidade).send_message(
            to=cliente_telefone,
            text=texto,
            buttons=[Button(title=t, callback_data=t) for t in montar_botoes_etapa18()],
        )
        id_hash = extrair_id_hash_msg_bot(resposta)
    except Exception as erro:
        logger.exception("etapa18_envio_falhou")
        raise ErroEnvioMeta(
            "Meta falhou ao enviar escolha de turno",
            id_etapa=18,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
    envio = {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": texto,
        "id_hash_msg_bot": id_hash,
        "id_etapa_resultante": 18,
        "tipo_mensagem": "interactive_button",
        "canal": "meta_whatsapp",
        "atualizar_conversa": True,
        "atualizar_last_from_bot": True,
    }
    if tratamento:
        envio.update(tratamento=True, tipo_tratamento=tratamento)
    logger.info("etapa18_envio_confirmado | tratamento=%s", tratamento)
    return envio
