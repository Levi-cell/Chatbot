import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa2_messages import (
    montar_botoes_etapa2,
    montar_mensagem_contexto_etapa2,
    montar_mensagem_etapa2,
    montar_mensagem_financeiro_etapa2,
    montar_mensagem_midia_etapa2,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa2")

ID_ETAPA2 = 2

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"


### CENARIO NORMAL: NOME VALIDADO NA ETAPA 1

def enviar_etapa2(cliente_telefone, phone_id_unidade, nome):
    mensagem_bot = montar_mensagem_etapa2(nome)

    return _enviar_texto_etapa2(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa2",
    )


### PARA O WORKER QUANDO O CLIENTE RESPONDE A ETAPA 2 COM MIDIA

def enviar_etapa2_midia(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_midia_etapa2()

    return _enviar_texto_etapa2(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa2_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


### PARA O WORKER QUANDO O CLIENTE RESPONDE A ETAPA 2 COM PERGUNTA FINANCEIRA

def enviar_etapa2_financeiro(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_financeiro_etapa2()

    return _enviar_texto_etapa2(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa2_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


### PARA O WORKER QUANDO O CLIENTE RESPONDE A ETAPA 2 FORA DO CONTEXTO

def enviar_etapa2_contexto_opcao_invalida(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_contexto_etapa2()

    return _enviar_texto_etapa2(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa2_contexto_opcao_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


### CONSTRUTOR DE ENVIO DA ETAPA 2 COM BOTOES

def _enviar_texto_etapa2(
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
            buttons=_montar_botoes_pywa_etapa2(),
        )
        id_hash_msg_bot = _extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s id_hash_msg_bot=%s tratamento=%s",
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
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA2,
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
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 2",
            id_etapa=ID_ETAPA2,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa2():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa2()
    ]


def _extrair_id_hash_msg_bot(sent_message):
    id_hash = getattr(sent_message, "id", None)
    if id_hash:
        return id_hash

    if isinstance(sent_message, dict):
        mensagens = sent_message.get("messages") or []
        if mensagens:
            id_hash = mensagens[0].get("id")
            if id_hash:
                return id_hash

    raise ValueError("Meta confirmou envio, mas nao retornou id da mensagem")
