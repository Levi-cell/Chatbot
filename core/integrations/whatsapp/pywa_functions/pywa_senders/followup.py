"""Envia texto proativo sem fila fictícia, prefixo de retorno ou transição."""

import httpx

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.followup_messages import MENSAGEM_FOLLOWUP
from core.integrations.whatsapp.pywa_functions.cliente import (
    conta_wa,
    usar_prefixo_mensagem_bot,
)
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)


def enviar_followup(cliente_telefone, phone_id_unidade, *, mensagem=MENSAGEM_FOLLOWUP):
    try:
        # Sem retry HTTP automático: resultado incerto exige observação no worker.
        with httpx.Client(timeout=httpx.Timeout(20, connect=5)) as session:
            with usar_prefixo_mensagem_bot(None):
                cliente = conta_wa(phone_id_unidade, session=session)
                retorno = cliente.send_message(
                    to=cliente_telefone, text=mensagem
                )
        return {
            "enviou": True,
            "id_hash_msg_bot": extrair_id_hash_msg_bot(retorno),
            "mensagem_bot": mensagem,
            "tipo_mensagem": "text",
        }
    except Exception as exc:
        raise ErroEnvioMeta(
            "Falha no envio proativo de follow-up",
            id_etapa=None,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from exc
