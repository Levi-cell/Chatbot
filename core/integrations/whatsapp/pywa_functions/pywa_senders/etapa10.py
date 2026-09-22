import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa10_messages import (
    montar_mensagem_contexto_email_invalido_etapa10,
    montar_mensagem_email_etapa10,
    montar_mensagem_email_etapa10_financeiro,
    montar_mensagem_email_etapa10_midia,
    montar_mensagem_email_etapa10_reforco_escolar,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa10")

ID_ETAPA10 = 10
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_EMAIL_INVALIDO = "email_invalido"


# CENARIO NORMAL: PERGUNTA O EMAIL DO CLIENTE
def enviar_etapa10(
    cliente_telefone,
    phone_id_unidade,
    *,
    repeticao=False,
):
    mensagem_bot = montar_mensagem_email_etapa10(repeticao=repeticao)

    return _enviar_texto_etapa10(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa10",
    )


# CLIENTE RESPONDE AO EMAIL COM MIDIA
def enviar_etapa10_midia(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_email_etapa10_midia()

    return _enviar_texto_etapa10(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa10_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE AO EMAIL COM PERGUNTA FINANCEIRA
def enviar_etapa10_financeiro(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_email_etapa10_financeiro()

    return _enviar_texto_etapa10(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa10_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR
def enviar_etapa10_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_email_etapa10_reforco_escolar()

    return _enviar_texto_etapa10(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa10_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


# CLIENTE RESPONDE COM EMAIL FORA DO CONTEXTO
def enviar_etapa10_contexto_email_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_contexto_email_invalido_etapa10()

    return _enviar_texto_etapa10(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa10_contexto_email_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_EMAIL_INVALIDO,
    )


# CONSTRUTOR DE ENVIO DE TEXTO DA ETAPA 10
def _enviar_texto_etapa10(
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
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA10,
            "tipo_mensagem": "text",
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
            "Meta falhou ao enviar mensagem da etapa 10",
            id_etapa=ID_ETAPA10,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
