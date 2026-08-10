import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.etapa9_messages import (
    montar_botoes_etapa9,
    montar_mensagem_retorno_cliente_contexto_invalido_etapa9,
    montar_mensagem_retorno_cliente_etapa9,
    montar_mensagem_retorno_cliente_financeiro_etapa9,
    montar_mensagem_retorno_cliente_midia_etapa9,
    montar_mensagem_retorno_cliente_reforco_escolar_etapa9,
    montar_mensagem_retorno_dependente_contexto_invalido_etapa9,
    montar_mensagem_retorno_dependente_etapa9,
    montar_mensagem_retorno_dependente_financeiro_etapa9,
    montar_mensagem_retorno_dependente_midia_etapa9,
    montar_mensagem_retorno_dependente_reforco_escolar_etapa9,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa9")

ID_ETAPA9 = 9
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"


# CENARIO NORMAL: RETORNO PARA O AGENDAMENTO DO PROPRIO CLIENTE
def enviar_etapa9_cliente(
    cliente_telefone,
    phone_id_unidade,
    nome_cliente,
):
    mensagem_bot = montar_mensagem_retorno_cliente_etapa9(
        nome_cliente
    )

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_cliente",
    )


# CENARIO NORMAL: RETORNO PARA O AGENDAMENTO DO DEPENDENTE
def enviar_etapa9_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_cliente,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_retorno_dependente_etapa9(
        nome_cliente,
        nome_dependente,
    )

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_dependente",
    )


# CLIENTE RESPONDE AO RETORNO PROPRIO COM MIDIA
def enviar_etapa9_cliente_midia(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_retorno_cliente_midia_etapa9()

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_cliente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE COM MIDIA
def enviar_etapa9_dependente_midia(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_retorno_dependente_midia_etapa9(
        nome_dependente
    )

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_dependente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE AO RETORNO PROPRIO COM PERGUNTA FINANCEIRA
def enviar_etapa9_cliente_financeiro(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_retorno_cliente_financeiro_etapa9()

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_cliente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE COM PERGUNTA FINANCEIRA
def enviar_etapa9_dependente_financeiro(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_retorno_dependente_financeiro_etapa9(
        nome_dependente
    )

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_dependente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR
def enviar_etapa9_cliente_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_retorno_cliente_reforco_escolar_etapa9()

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_cliente_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


def enviar_etapa9_dependente_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = (
        montar_mensagem_retorno_dependente_reforco_escolar_etapa9(
            nome_dependente
        )
    )

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_dependente_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


# CLIENTE RESPONDE AO RETORNO PROPRIO FORA DO CONTEXTO
def enviar_etapa9_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = (
        montar_mensagem_retorno_cliente_contexto_invalido_etapa9()
    )

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CLIENTE RESPONDE AO RETORNO DO DEPENDENTE FORA DO CONTEXTO
def enviar_etapa9_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = (
        montar_mensagem_retorno_dependente_contexto_invalido_etapa9(
            nome_dependente
        )
    )

    return _enviar_texto_etapa9(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa9_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CONSTRUTOR DE ENVIO DA ETAPA 9 COM BOTOES
def _enviar_texto_etapa9(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
    tipo_tratamento=None,
):
    try:
        mensagem_enviada = montar_texto_com_rodape(
            mensagem_bot,
            RODAPE_OPCAO_UNICA,
        )
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_enviada,
            buttons=_montar_botoes_pywa_etapa9(),
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
            "mensagem_bot": mensagem_enviada,
            "rodape_mensagem": RODAPE_OPCAO_UNICA,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA9,
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
            "Meta falhou ao enviar mensagem da etapa 9",
            id_etapa=ID_ETAPA9,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa9():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa9()
    ]
