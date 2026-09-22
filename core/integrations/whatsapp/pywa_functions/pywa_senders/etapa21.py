import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_PESQUISA_SATISFACAO,
    montar_texto_com_cabecalho,
)
from core.integrations.whatsapp.messages.etapa21_messages import (
    montar_mensagem_etapa21,
    montar_mensagem_midia_etapa21,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa21")

ID_ETAPA21 = 21
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"


# CENARIO NORMAL: SOLICITA O TEXTO DO COMENTARIO
def enviar_etapa21(
    cliente_telefone,
    phone_id_unidade,
    *,
    repeticao=False,
):
    return _enviar_texto_etapa21(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_etapa21(repeticao=repeticao),
        evento="enviar_etapa21",
    )


def enviar_etapa21_midia(cliente_telefone, phone_id_unidade):
    return _enviar_texto_etapa21(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_midia_etapa21(),
        evento="enviar_etapa21_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


def _enviar_texto_etapa21(
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
            "id_etapa_resultante": ID_ETAPA21,
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
            "%s_erro | motivo=meta_falhou "
            "acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 21",
            id_etapa=ID_ETAPA21,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
