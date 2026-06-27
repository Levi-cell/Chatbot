import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.primeira_etapa_messages import (
    montar_mensagem_contexto_nome_invalido_etapa_1,
    montar_mensagem_etapa_1,
    montar_mensagem_financeiro_etapa_1,
    montar_mensagem_financeiro_inicio,
    montar_mensagem_midia_etapa_1,
    montar_mensagem_midia_inicio,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.saudacao import (
    obter_saudacao_por_horario,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa1")

ID_ETAPA_1 = 1

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_NOME_INVALIDO = "nome_invalido"


###  CENARIO NORMAL

def enviar_primeira_etapa(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_etapa_1(saudacao)

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa",
    )

### PARA O WORKER QUANDO O CLIENTE INICIA COM MIDIA

def enviar_primeira_etapa_midia_inicio(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_midia_inicio(saudacao)

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_midia_inicio",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )

### PARA O WORKER QUANDO O CLIENTE INICIA COM FINANCEIRO

def enviar_primeira_etapa_financeiro_inicio(cliente_telefone, phone_id_unidade):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_financeiro_inicio(saudacao)

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_financeiro_inicio",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )

## FUNCAO PARA O WORKER QUANDO O CLIENTE RESPONDE AO NOME ERRADO. com midia

def enviar_primeira_etapa_midia(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_midia_etapa_1()

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )

## FUNCAO PARA O WORKER QUANDO O CLIENTE RESPONDE AO NOME ERRADO, com financeiro

def enviar_primeira_etapa_financeiro(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_financeiro_etapa_1()

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )

## FUNCAO PARA O WORKER QUANDO O CLIENTE RESPONDE AO NOME ERRADO, fora do contexto

def enviar_primeira_etapa_contexto_nome_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_contexto_nome_invalido_etapa_1()

    return _enviar_texto_etapa_1(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_primeira_etapa_contexto_nome_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_NOME_INVALIDO,
    )


"""AQUI É UM CONSTRUTOR SIMPLES DE ENVIO, A MENSAGEM QUE ELE ENVIA
 DEPENDE DO PARAMETRO QUE ELE RECEBE, ELE NÃO SUPORTA BOTÕES POIS FOI
 FEITO SÓ PARA ETAPA 1, CADA ETAPA TERÁ SEU CONSTRUTOR"""

def _enviar_texto_etapa_1(
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
            "id_etapa_resultante": ID_ETAPA_1,
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
            "Meta falhou ao enviar mensagem da etapa 1",
            id_etapa=ID_ETAPA_1,
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
