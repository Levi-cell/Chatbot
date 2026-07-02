import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_cliente_menor_18_etapa4,
    montar_mensagem_contexto_idade_dependente_invalida_etapa4,
    montar_mensagem_contexto_idade_invalida_etapa4,
    montar_mensagem_dependente_menor_5_etapa4,
    montar_mensagem_idade_dependente_etapa4,
    montar_mensagem_idade_dependente_etapa4_financeiro,
    montar_mensagem_idade_dependente_etapa4_midia,
    montar_mensagem_idade_etapa4,
    montar_mensagem_idade_etapa4_financeiro,
    montar_mensagem_idade_etapa4_midia,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa4")

ID_ETAPA4 = 4

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_IDADE_INVALIDA = "idade_invalida"


# CENARIO NORMAL: PERGUNTAR A IDADE DO PROPRIO CLIENTE
def enviar_etapa4_cliente(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_idade_etapa4()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente",
    )


# CENARIO NORMAL: PERGUNTAR A IDADE DO DEPENDENTE
def enviar_etapa4_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa4(
        nome_dependente
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente",
    )


# CLIENTE RESPONDE A ETAPA 4 COM MIDIA
def enviar_etapa4_cliente_midia(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_idade_etapa4_midia()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM MIDIA
def enviar_etapa4_dependente_midia(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa4_midia(
        nome_dependente
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A IDADE COM PERGUNTA FINANCEIRA
def enviar_etapa4_cliente_financeiro(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_idade_etapa4_financeiro()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA
def enviar_etapa4_dependente_financeiro(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa4_financeiro(
        nome_dependente
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A ETAPA 4 COM IDADE INVALIDA
def enviar_etapa4_cliente_contexto_idade_invalida(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_contexto_idade_invalida_etapa4()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente_contexto_idade_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_IDADE_INVALIDA,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM IDADE INVALIDA
def enviar_etapa4_dependente_contexto_idade_invalida(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = (
        montar_mensagem_contexto_idade_dependente_invalida_etapa4(
            nome_dependente
        )
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente_contexto_idade_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_IDADE_INVALIDA,
    )


# CLIENTE COM MENOS DE 18 ANOS
def enviar_etapa4_cliente_menor_18(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_cliente_menor_18_etapa4()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente_menor_18",
    )


# DEPENDENTE COM MENOS DE 5 ANOS
def enviar_etapa4_dependente_menor_5(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_dependente_menor_5_etapa4(
        nome_dependente
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente_menor_5",
    )


# CONSTRUTOR DE ENVIO DE TEXTO DA ETAPA 4
def _enviar_texto_etapa4(
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
            "id_etapa_resultante": ID_ETAPA4,
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
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 4",
            id_etapa=ID_ETAPA4,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


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
