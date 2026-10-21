import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_contexto_profissao_invalida_etapa4,
    montar_mensagem_etapa4,
    montar_mensagem_financeiro_etapa4,
    montar_mensagem_midia_etapa4,
    montar_mensagem_reforco_escolar_etapa4,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa4")

ID_ETAPA4 = 4
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_PROFISSAO_INVALIDA = "profissao_invalida"


def enviar_etapa4(
    cliente_telefone,
    phone_id_unidade,
    *,
    status_dependente=False,
    repeticao=False,
):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_etapa4(
            status_dependente=status_dependente,
            repeticao=repeticao,
        ),
        evento="enviar_etapa4",
    )


def enviar_etapa4_midia(cliente_telefone, phone_id_unidade):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_midia_etapa4(),
        evento="enviar_etapa4_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


def enviar_etapa4_financeiro(cliente_telefone, phone_id_unidade):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_financeiro_etapa4(),
        evento="enviar_etapa4_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


def enviar_etapa4_reforco_escolar(cliente_telefone, phone_id_unidade):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_reforco_escolar_etapa4(),
        evento="enviar_etapa4_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


def enviar_etapa4_contexto_profissao_invalida(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_contexto_profissao_invalida_etapa4(),
        evento="enviar_etapa4_contexto_profissao_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_PROFISSAO_INVALIDA,
    )


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
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s "
            "phone_number_id=%s erro=%s",
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


def enviar_abertura_fireads(contexto):
    from core.integrations.whatsapp.messages.etapa4_messages import montar_abertura_fireads
    mensagem = contexto['mensagem_cliente_atual']
    return _enviar_texto_etapa4(
        mensagem['cliente_telefone'], mensagem['id_phone_unidade'],
        montar_abertura_fireads(contexto), evento='fireads_abertura',
    )
