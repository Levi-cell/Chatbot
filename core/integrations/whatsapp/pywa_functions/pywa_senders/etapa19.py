import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_PESQUISA_SATISFACAO,
    montar_texto_com_cabecalho,
)
from core.integrations.whatsapp.messages.etapa19_messages import (
    montar_botoes_etapa19,
    montar_mensagem_contexto_invalido_etapa19,
    montar_mensagem_etapa19,
    montar_mensagem_financeiro_etapa19,
    montar_mensagem_midia_etapa19,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa19")

ID_ETAPA19 = 19

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "opcao_comentario_invalida"


# CENARIO NORMAL: SOLICITA A DECISAO SOBRE COMENTAR OU NAO
def enviar_etapa19(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_botoes_etapa19(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_etapa19(),
        evento="enviar_etapa19",
    )


def enviar_etapa19_midia(cliente_telefone, phone_id_unidade):
    return _enviar_botoes_etapa19(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_midia_etapa19(),
        evento="enviar_etapa19_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


def enviar_etapa19_financeiro(cliente_telefone, phone_id_unidade):
    return _enviar_botoes_etapa19(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_financeiro_etapa19(),
        evento="enviar_etapa19_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


def enviar_etapa19_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_botoes_etapa19(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_contexto_invalido_etapa19(),
        evento="enviar_etapa19_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


def _enviar_botoes_etapa19(
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
                CABECALHO_PESQUISA_SATISFACAO,
            ),
            buttons=_montar_botoes_pywa_etapa19(),
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
            "cabecalho_mensagem": CABECALHO_PESQUISA_SATISFACAO,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA19,
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
            "Meta falhou ao enviar mensagem da etapa 19",
            id_etapa=ID_ETAPA19,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa19():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa19()
    ]
