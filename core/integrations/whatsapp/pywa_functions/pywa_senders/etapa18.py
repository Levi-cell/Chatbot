import logging

from pywa.types import Section, SectionList, SectionRow

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.componentes_compartilhados import (
    CABECALHO_PESQUISA_SATISFACAO,
    RODAPE_OPCAO_UNICA,
    montar_texto_com_cabecalho,
    montar_texto_com_rodape,
)
from core.integrations.whatsapp.messages.etapa18_messages import (
    montar_mensagem_contexto_invalido_etapa18,
    montar_mensagem_etapa18,
    montar_opcoes_satisfacao_etapa18,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa18")

ID_ETAPA18 = 18

TIPO_TRATAMENTO_CONTEXTO_INVALIDO = "satisfacao_invalida"


# CENARIO NORMAL: SOLICITA UMA UNICA NOTA PARA O ATENDIMENTO
def enviar_etapa18(
    cliente_telefone,
    phone_id_unidade,
    nome_cliente,
):
    mensagem_bot = montar_mensagem_etapa18(nome_cliente)

    return _enviar_lista_etapa18(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa18",
    )


# CLIENTE RESPONDE A ETAPA 18 FORA DAS OPCOES DA PESQUISA
def enviar_etapa18_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_texto_com_rodape(
        montar_mensagem_contexto_invalido_etapa18(),
        RODAPE_OPCAO_UNICA,
    )

    return _enviar_lista_etapa18(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa18_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    )


# CONSTRUTOR DA LISTA INTERATIVA COMPARTILHADA PELA ETAPA 18
def _enviar_lista_etapa18(
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
            buttons=_montar_lista_pywa_etapa18(),
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s "
            "id_hash_msg_bot=%s tratamento=%s cabecalho=corpo_negrito",
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
            "id_etapa_resultante": ID_ETAPA18,
            "tipo_mensagem": "interactive_list",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

        if tipo_tratamento:
            contexto_envio["tratamento"] = True
            contexto_envio["tipo_tratamento"] = tipo_tratamento
            contexto_envio["rodape_mensagem"] = RODAPE_OPCAO_UNICA

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


def _montar_lista_pywa_etapa18():
    linhas = [
        SectionRow(
            title=titulo,
            callback_data=f"satisfacao_{nota}",
        )
        for nota, titulo in montar_opcoes_satisfacao_etapa18()
    ]

    return SectionList(
        button_title="Avaliar atendimento",
        sections=[
            Section(
                title="Escolha uma nota",
                rows=linhas,
            )
        ],
    )
