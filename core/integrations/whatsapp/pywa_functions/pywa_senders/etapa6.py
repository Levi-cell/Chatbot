import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_botoes_etapa6,
    montar_mensagem_oferta_cliente_contexto_invalido_etapa6,
    montar_mensagem_oferta_cliente_etapa6,
    montar_mensagem_oferta_cliente_financeiro_etapa6,
    montar_mensagem_oferta_cliente_midia_etapa6,
    montar_mensagem_oferta_dependente_contexto_invalido_etapa6,
    montar_mensagem_oferta_dependente_etapa6,
    montar_mensagem_oferta_dependente_financeiro_etapa6,
    montar_mensagem_oferta_dependente_midia_etapa6,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa6")

ID_ETAPA6 = 6

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_invalida"


# CENARIO NORMAL: OFERTA PARA O PROPRIO CLIENTE
def enviar_etapa6_cliente(
    cliente_telefone,
    phone_id_unidade,
    nome_cliente,
):
    mensagem_bot = montar_mensagem_oferta_cliente_etapa6(nome_cliente)

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente",
    )


# CENARIO NORMAL: OFERTA PARA O DEPENDENTE
def enviar_etapa6_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_oferta_dependente_etapa6(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente",
    )


# CLIENTE RESPONDE A OFERTA PROPRIA COM MIDIA
def enviar_etapa6_cliente_midia(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_oferta_cliente_midia_etapa6()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A OFERTA DO DEPENDENTE COM MIDIA
def enviar_etapa6_dependente_midia(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_oferta_dependente_midia_etapa6(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A OFERTA PROPRIA COM PERGUNTA FINANCEIRA
def enviar_etapa6_cliente_financeiro(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_oferta_cliente_financeiro_etapa6()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A OFERTA DO DEPENDENTE COM PERGUNTA FINANCEIRA
def enviar_etapa6_dependente_financeiro(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_oferta_dependente_financeiro_etapa6(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A OFERTA PROPRIA COM MENSAGEM FORA DE CONTEXTO
def enviar_etapa6_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = (
        montar_mensagem_oferta_cliente_contexto_invalido_etapa6()
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CLIENTE RESPONDE A OFERTA DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO
def enviar_etapa6_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = (
        montar_mensagem_oferta_dependente_contexto_invalido_etapa6(
            nome_dependente
        )
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CONSTRUTOR DE ENVIO DA ETAPA 6 COM BOTOES
def _enviar_texto_etapa6(
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
            buttons=_montar_botoes_pywa_etapa6(),
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
            "id_etapa_resultante": ID_ETAPA6,
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
            "Meta falhou ao enviar mensagem da etapa 6",
            id_etapa=ID_ETAPA6,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa6():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa6()
    ]
