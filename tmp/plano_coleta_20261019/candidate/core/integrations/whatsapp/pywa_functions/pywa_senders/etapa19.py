"""Transporte da entrega ao comercial com mensagem previamente preenchida."""

import logging
from pywa.types import URLButton

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa19_messages import (
    TITULO_BOTAO_COMERCIAL,
    montar_mensagem_etapa19,
)
from core.integrations.whatsapp.numero_comercial import (
    montar_link_numero_comercial_whatsapp,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)

logger = logging.getLogger("whatsapp.etapa19")


def enviar_etapa19(
    cliente_telefone,
    phone_id_unidade,
    numero_comercial,
    mensagem_comercial,
    nome_dependente=None,
    *,
    pedir_texto=False,
    repeticao=False,
):
    texto = montar_mensagem_etapa19(
        nome_dependente, pedir_texto=pedir_texto, repeticao=repeticao
    )
    botao = URLButton(
        title=TITULO_BOTAO_COMERCIAL,
        url=montar_link_numero_comercial_whatsapp(numero_comercial, mensagem_comercial),
    )
    try:
        resposta = conta_wa(phone_id_unidade).send_message(
            to=cliente_telefone, text=texto, buttons=botao
        )
        id_hash = extrair_id_hash_msg_bot(resposta)
    except Exception as erro:
        logger.exception("etapa19_envio_falhou")
        raise ErroEnvioMeta(
            "Meta falhou ao enviar contato comercial",
            id_etapa=19,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
    envio = {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": texto,
        "id_hash_msg_bot": id_hash,
        "id_etapa_resultante": 19,
        "tipo_mensagem": "interactive_cta_url",
        "canal": "meta_whatsapp",
        "atualizar_conversa": True,
        "atualizar_last_from_bot": True,
    }
    if pedir_texto:
        envio.update(tratamento=True, tipo_tratamento="tipo_mensagem_nao_suportado")
    logger.info("etapa19_envio_confirmado | tratamento=%s", pedir_texto)
    return envio
