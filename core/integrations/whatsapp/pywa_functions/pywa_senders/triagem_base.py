"""
Contrato PyWa compartilhado exclusivamente pelas etapas 10 a 15.

Este helper monta os componentes interativos, envia a pergunta pela Meta,
extrai o id_hash da resposta e devolve o contexto de envio. Ele não valida a
resposta do cliente, não produz eventos e não decide transições.
"""

import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.triagem_componentes import (
    montar_botoes_triagem,
    montar_rodape_triagem,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.triagem")

TIPO_TRATAMENTO_RESPOSTA_INVALIDA = "resposta_triagem_invalida"


def enviar_pergunta_triagem(
    cliente_telefone,
    phone_id_unidade,
    *,
    id_etapa,
    cabecalho,
    mensagem_bot,
    evento_log,
    tipo_tratamento=None,
):
    """Envia uma pergunta da triagem com o contrato comum das etapas 10–15."""
    try:
        rodape = montar_rodape_triagem()
        mensagem_enviada = montar_texto_com_rodape(
            mensagem_bot,
            rodape,
        )
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_enviada,
            header=cabecalho,
            buttons=_montar_botoes_pywa_triagem(),
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta etapa=%s cliente=%s "
            "phone_number_id=%s id_hash_msg_bot=%s tratamento=%s",
            evento_log,
            id_etapa,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            tipo_tratamento,
        )

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_enviada,
            "cabecalho_mensagem": cabecalho,
            "rodape_mensagem": rodape,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": id_etapa,
            "tipo_mensagem": "interactive_button",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

        if tipo_tratamento:
            contexto_envio["tratamento"] = True
            contexto_envio["tipo_tratamento"] = tipo_tratamento

        return contexto_envio

    except Exception as erro:
        logger.exception(
            "%s_erro | motivo=meta_falhou acao=levantar_erro etapa=%s "
            "cliente=%s phone_number_id=%s erro=%s",
            evento_log,
            id_etapa,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            f"Meta falhou ao enviar mensagem da etapa {id_etapa}",
            id_etapa=id_etapa,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_triagem():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_triagem()
    ]
