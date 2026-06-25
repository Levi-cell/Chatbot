import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.tratamentos import (
    montar_mensagem_financeira,
)
from core.integrations.whatsapp.pywa_functions.envios import (
    enviar_mensagem_texto,
)
from core.integrations.whatsapp.pywa_functions.saudacao import (
    obter_saudacao_por_horario,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender_tratamento")


def sender_tratamento_financeiro(
    cliente_telefone,
    phone_id_unidade,
    id_etapa,
    conversa_nova,
):
    saudacao = obter_saudacao_por_horario()
    mensagem_bot = montar_mensagem_financeira(id_etapa, conversa_nova, saudacao)

    try:
        id_hash_msg_bot = enviar_mensagem_texto(
            to=cliente_telefone,
            text=mensagem_bot,
            phone_id_unidade=phone_id_unidade,
        )

        logger.info(
            "sender_tratamento_financeiro_ok | acao=enviar_meta cliente=%s phone_number_id=%s etapa=%s conversa_nova=%s id_hash_msg_bot=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_etapa,
            conversa_nova,
            id_hash_msg_bot,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": id_etapa,
            "tipo_mensagem": "text",
            "canal": "meta_whatsapp",
            "tratamento": True,
            "tipo_tratamento": "pergunta_financeira",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

    except Exception as erro:
        logger.exception(
            "sender_tratamento_financeiro_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s etapa=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_etapa,
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar tratamento financeiro",
            id_etapa=id_etapa,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
