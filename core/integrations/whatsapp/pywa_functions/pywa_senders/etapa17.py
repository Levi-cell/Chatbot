import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa17_messages import (
    RODAPE_ETAPA17_AGENDAMENTO,
    montar_botoes_etapa17,
    montar_mensagem_contexto_invalido_etapa17,
    montar_mensagem_etapa17,
    montar_mensagem_financeiro_etapa17,
    montar_mensagem_midia_etapa17,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa17")

ID_ETAPA17 = 17

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "agendamento_nao_confirmado"


# CENARIO NORMAL: A PERGUNTA 6 DA TRIAGEM FOI RESPONDIDA
def enviar_etapa17(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_etapa17(link_agendamento)

    return _enviar_texto_etapa17(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa17",
    )


# CLIENTE RESPONDE À ETAPA 17 COM MIDIA
def enviar_etapa17_midia(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_midia_etapa17(link_agendamento)

    return _enviar_texto_etapa17(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa17_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE À ETAPA 17 COM PERGUNTA FINANCEIRA
def enviar_etapa17_financeiro(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_financeiro_etapa17(
        link_agendamento
    )

    return _enviar_texto_etapa17(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa17_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE À ETAPA 17 FORA DO CONTEXTO
def enviar_etapa17_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_contexto_invalido_etapa17(
        link_agendamento
    )

    return _enviar_texto_etapa17(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa17_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CONSTRUTOR DE ENVIO DA ETAPA 17 COM UM BOTAO DE RESPOSTA
def _enviar_texto_etapa17(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
    tipo_tratamento=None,
):
    try:
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_bot,
            buttons=_montar_botoes_pywa_etapa17(),
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s "
            "id_hash_msg_bot=%s tratamento=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            tipo_tratamento,
        )

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "rodape_mensagem": RODAPE_ETAPA17_AGENDAMENTO,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA17,
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
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s "
            "phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 17",
            id_etapa=ID_ETAPA17,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa17():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa17()
    ]
