import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_ETAPA11_TRIAGEM,
    montar_texto_com_cabecalho,
)
from core.integrations.whatsapp.messages.etapa11_messages import (
    montar_botoes_etapa11,
    montar_mensagem_contexto_invalido_etapa11,
    montar_mensagem_financeiro_etapa11,
    montar_mensagem_midia_etapa11,
    montar_mensagem_reforco_escolar_etapa11,
    montar_mensagem_triagem_cognitiva_etapa11,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa11")

ID_ETAPA11 = 11
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "confirmacao_triagem_invalida"


# CENARIO NORMAL: APRESENTA E INICIA A TRIAGEM COGNITIVA
def enviar_etapa11(
    cliente_telefone,
    phone_id_unidade,
    status_dependente=False,
    nome_dependente=None,
    *,
    repeticao=False,
):
    mensagem_bot = montar_mensagem_triagem_cognitiva_etapa11(
        status_dependente=status_dependente,
        nome_dependente=nome_dependente,
        repeticao=repeticao,
    )

    return _enviar_botoes_etapa11(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa11",
    )


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM COM MÍDIA
def enviar_etapa11_midia(
    cliente_telefone,
    phone_id_unidade,
    *,
    status_dependente=False,
    nome_dependente=None,
):
    mensagem_bot = montar_mensagem_midia_etapa11(
        status_dependente=status_dependente, nome_dependente=nome_dependente
    )

    return _enviar_botoes_etapa11(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa11_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM COM PERGUNTA FINANCEIRA
def enviar_etapa11_financeiro(
    cliente_telefone,
    phone_id_unidade,
    *,
    status_dependente=False,
    nome_dependente=None,
):
    mensagem_bot = montar_mensagem_financeiro_etapa11(
        status_dependente=status_dependente, nome_dependente=nome_dependente
    )

    return _enviar_botoes_etapa11(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa11_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR
def enviar_etapa11_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
    *,
    status_dependente=False,
    nome_dependente=None,
):
    mensagem_bot = montar_mensagem_reforco_escolar_etapa11(
        status_dependente=status_dependente, nome_dependente=nome_dependente
    )

    return _enviar_botoes_etapa11(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa11_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


# CLIENTE RESPONDE À INTRODUÇÃO DA TRIAGEM FORA DO CONTEXTO
def enviar_etapa11_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    *,
    status_dependente=False,
    nome_dependente=None,
):
    mensagem_bot = montar_mensagem_contexto_invalido_etapa11(
        status_dependente=status_dependente, nome_dependente=nome_dependente
    )

    return _enviar_botoes_etapa11(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa11_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CONSTRUTOR DE ENVIO DA ETAPA 11 COM UM BOTÃO DE RESPOSTA
def _enviar_botoes_etapa11(
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
            text=montar_texto_com_cabecalho(
                mensagem_bot,
                CABECALHO_ETAPA11_TRIAGEM,
            ),
            buttons=_montar_botoes_pywa_etapa11(),
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s "
            "phone_number_id=%s id_hash_msg_bot=%s "
            "tratamento=%s cabecalho=corpo_negrito",
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
            "cabecalho_mensagem": CABECALHO_ETAPA11_TRIAGEM,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA11,
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
            "%s_erro | motivo=meta_falhou "
            "acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 11",
            id_etapa=ID_ETAPA11,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa11():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa11()
    ]
