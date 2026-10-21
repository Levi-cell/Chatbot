import logging

from pywa.types import Button

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    RODAPE_OPCAO_UNICA,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.etapa3_messages import (
    montar_botoes_etapa3,
    montar_mensagem_contexto_etapa3,
    montar_mensagem_etapa3,
    montar_mensagem_financeiro_etapa3,
    montar_mensagem_midia_etapa3,
    montar_mensagem_reforco_escolar_etapa3,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa3")

ID_ETAPA3 = 3

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "confirmacao_destino_invalida"


def enviar_etapa3(
    cliente_telefone,
    phone_id_unidade,
    status_dependente,
    *,
    repeticao=False,
):
    return _enviar_botoes_etapa3(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_etapa3(status_dependente, repeticao=repeticao),
        evento="enviar_etapa3",
        status_dependente=status_dependente,
    )


def enviar_etapa3_midia(
    cliente_telefone,
    phone_id_unidade,
    status_dependente,
):
    return _enviar_botoes_etapa3(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_midia_etapa3(status_dependente),
        evento="enviar_etapa3_midia",
        status_dependente=status_dependente,
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


def enviar_etapa3_financeiro(
    cliente_telefone,
    phone_id_unidade,
    status_dependente,
):
    return _enviar_botoes_etapa3(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_financeiro_etapa3(status_dependente),
        evento="enviar_etapa3_financeiro",
        status_dependente=status_dependente,
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


def enviar_etapa3_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
    status_dependente,
):
    return _enviar_botoes_etapa3(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_reforco_escolar_etapa3(status_dependente),
        evento="enviar_etapa3_reforco_escolar",
        status_dependente=status_dependente,
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


def enviar_etapa3_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    status_dependente,
):
    return _enviar_botoes_etapa3(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_contexto_etapa3(status_dependente),
        evento="enviar_etapa3_contexto_invalido",
        status_dependente=status_dependente,
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


def _enviar_botoes_etapa3(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
    status_dependente,
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
            buttons=_montar_botoes_pywa_etapa3(),
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s "
            "id_hash_msg_bot=%s tratamento=%s status_dependente=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            tipo_tratamento,
            bool(status_dependente),
        )

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_enviada,
            "rodape_mensagem": RODAPE_OPCAO_UNICA,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA3,
            "tipo_mensagem": "interactive_button",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

        if tipo_tratamento:
            contexto_envio.update(
                {
                    "tratamento": True,
                    "tipo_tratamento": tipo_tratamento,
                }
            )

        return contexto_envio

    except Exception as erro:
        logger.exception(
            "%s_erro | motivo=meta_falhou acao=levantar_erro "
            "cliente=%s phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 3",
            id_etapa=ID_ETAPA3,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _montar_botoes_pywa_etapa3():
    return [
        Button(
            title=titulo,
            callback_data=titulo,
        )
        for titulo in montar_botoes_etapa3()
    ]
