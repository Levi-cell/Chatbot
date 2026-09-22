import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.etapa7_messages import (
    montar_botoes_etapa7,
    montar_mensagem_oferta_cliente_contexto_invalido_etapa7,
    montar_mensagem_oferta_cliente_etapa7,
    montar_mensagem_oferta_cliente_financeiro_etapa7,
    montar_mensagem_oferta_cliente_midia_etapa7,
    montar_mensagem_oferta_cliente_reforco_escolar_etapa7,
    montar_mensagem_oferta_dependente_contexto_invalido_etapa7,
    montar_mensagem_oferta_dependente_etapa7,
    montar_mensagem_oferta_dependente_financeiro_etapa7,
    montar_mensagem_oferta_dependente_midia_etapa7,
    montar_mensagem_oferta_dependente_reforco_escolar_etapa7,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa7")

ID_ETAPA7 = 7
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"


# CENARIO NORMAL: OFERTA PARA O PROPRIO CLIENTE
def enviar_etapa7_cliente(
    cliente_telefone,
    phone_id_unidade,
    nome_titular,
    *,
    repeticao=False,
):
    mensagem_bot = montar_mensagem_oferta_cliente_etapa7(
        nome_titular, repeticao=repeticao
    )

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_cliente",
    )


# CENARIO NORMAL: OFERTA PARA O DEPENDENTE
def enviar_etapa7_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_titular,
    nome_dependente,
    *,
    repeticao=False,
):
    mensagem_bot = montar_mensagem_oferta_dependente_etapa7(
        nome_titular=nome_titular,
        nome_dependente=nome_dependente,
        repeticao=repeticao,
    )

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_dependente",
    )


# CLIENTE RESPONDE A OFERTA PROPRIA COM MIDIA
def enviar_etapa7_cliente_midia(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_oferta_cliente_midia_etapa7()

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_cliente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A OFERTA DO DEPENDENTE COM MIDIA
def enviar_etapa7_dependente_midia(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_oferta_dependente_midia_etapa7(
        nome_dependente,
    )

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_dependente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A OFERTA PROPRIA COM PERGUNTA FINANCEIRA
def enviar_etapa7_cliente_financeiro(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_oferta_cliente_financeiro_etapa7()

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_cliente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A OFERTA DO DEPENDENTE COM PERGUNTA FINANCEIRA
def enviar_etapa7_dependente_financeiro(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_oferta_dependente_financeiro_etapa7(
        nome_dependente,
    )

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_dependente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR
def enviar_etapa7_cliente_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_oferta_cliente_reforco_escolar_etapa7()

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_cliente_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


def enviar_etapa7_dependente_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_oferta_dependente_reforco_escolar_etapa7(
        nome_dependente,
    )

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_dependente_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


# CLIENTE RESPONDE A OFERTA PROPRIA COM MENSAGEM FORA DE CONTEXTO
def enviar_etapa7_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_oferta_cliente_contexto_invalido_etapa7()

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CLIENTE RESPONDE A OFERTA DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO
def enviar_etapa7_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_oferta_dependente_contexto_invalido_etapa7(
        nome_dependente,
    )

    return _enviar_texto_etapa7(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa7_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CONSTRUTOR DE ENVIO DA ETAPA 7 COM BOTOES
def _enviar_texto_etapa7(
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
            buttons=_montar_botoes_pywa_etapa7(),
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
            "id_etapa_resultante": ID_ETAPA7,
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
            "Meta falhou ao enviar mensagem da etapa 7",
            id_etapa=ID_ETAPA7,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa7():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa7()
    ]
