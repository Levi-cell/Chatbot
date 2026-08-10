import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa18_messages import (
    RODAPE_ETAPA18_AGENDAMENTO,
    montar_botoes_etapa18,
    montar_mensagem_contexto_invalido_etapa18,
    montar_mensagem_etapa18,
    montar_mensagem_financeiro_etapa18,
    montar_mensagem_midia_etapa18,
    montar_mensagem_reforco_escolar_etapa18,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa18")

ID_ETAPA18 = 18
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "agendamento_nao_confirmado"


# CENARIO NORMAL: A PERGUNTA 6 DA TRIAGEM FOI RESPONDIDA
def enviar_etapa18(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_etapa18(link_agendamento)

    return _enviar_texto_etapa18(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa18",
    )


# CLIENTE RESPONDE À ETAPA 18 COM MIDIA
def enviar_etapa18_midia(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_midia_etapa18(link_agendamento)

    return _enviar_texto_etapa18(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa18_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE À ETAPA 18 COM PERGUNTA FINANCEIRA
def enviar_etapa18_financeiro(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_financeiro_etapa18(
        link_agendamento
    )

    return _enviar_texto_etapa18(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa18_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR
def enviar_etapa18_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_reforco_escolar_etapa18(
        link_agendamento
    )

    return _enviar_texto_etapa18(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa18_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


# CLIENTE RESPONDE À ETAPA 18 FORA DO CONTEXTO
def enviar_etapa18_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    link_agendamento,
):
    mensagem_bot = montar_mensagem_contexto_invalido_etapa18(
        link_agendamento
    )

    return _enviar_texto_etapa18(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa18_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CONSTRUTOR DE ENVIO DA ETAPA 18 COM UM BOTAO DE RESPOSTA
def _enviar_texto_etapa18(
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
            buttons=_montar_botoes_pywa_etapa18(),
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
            "rodape_mensagem": RODAPE_ETAPA18_AGENDAMENTO,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA18,
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
            "Meta falhou ao enviar mensagem da etapa 18",
            id_etapa=ID_ETAPA18,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa18():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa18()
    ]
