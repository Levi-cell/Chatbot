import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa3_messages import (
    montar_mensagem_contexto_nome_invalido_etapa3,
    montar_mensagem_etapa3,
    montar_mensagem_financeiro_etapa3,
    montar_mensagem_midia_etapa3,
)

from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa3")

ID_ETAPA3 = 3

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_NOME_INVALIDO = "nome_invalido"


# CENARIO NORMAL: ATENDIMENTO PARA OUTRA PESSOA
def enviar_etapa3(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_etapa3()

    return _enviar_texto_etapa3(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa3",
    )


# CLIENTE RESPONDE A ETAPA 3 COM MIDIA
def enviar_etapa3_midia(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_midia_etapa3()

    return _enviar_texto_etapa3(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa3_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A ETAPA 3 COM PERGUNTA FINANCEIRA
def enviar_etapa3_financeiro(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_financeiro_etapa3()

    return _enviar_texto_etapa3(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa3_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A ETAPA 3 COM NOME INVALIDO
def enviar_etapa3_contexto_nome_invalido(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_contexto_nome_invalido_etapa3()

    return _enviar_texto_etapa3(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa3_contexto_nome_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_NOME_INVALIDO,
    )


# CONSTRUTOR DE ENVIO DE TEXTO DA ETAPA 3
def _enviar_texto_etapa3(
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
            "id_etapa_resultante": ID_ETAPA3,
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
            "Meta falhou ao enviar mensagem da etapa 3",
            id_etapa=ID_ETAPA3,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
