from core.integrations.whatsapp.messages.etapa16_messages import (
    montar_cabecalho_etapa16,
    montar_mensagem_cliente_contexto_invalido_etapa16,
    montar_mensagem_cliente_etapa16,
    montar_mensagem_dependente_contexto_invalido_etapa16,
    montar_mensagem_dependente_etapa16,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import (
    TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    enviar_pergunta_triagem,
)


ID_ETAPA16 = 16
# CENARIO NORMAL: PERGUNTA 5 SOBRE O PROPRIO CLIENTE
def enviar_etapa16_cliente(cliente_telefone, phone_id_unidade):
    return _enviar_etapa16(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_etapa16(),
        evento_log="enviar_etapa16_cliente",
    )


# CENARIO NORMAL: PERGUNTA 5 SOBRE O DEPENDENTE
def enviar_etapa16_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
    idade_dependente,
):
    return _enviar_etapa16(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_etapa16(
            nome_dependente,
            idade_dependente,
        ),
        evento_log="enviar_etapa16_dependente",
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 5 SOBRE O PROPRIO CLIENTE
def enviar_etapa16_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_etapa16(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_contexto_invalido_etapa16(),
        evento_log="enviar_etapa16_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 5 SOBRE O DEPENDENTE
def enviar_etapa16_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
    idade_dependente,
):
    return _enviar_etapa16(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_contexto_invalido_etapa16(
            nome_dependente,
            idade_dependente,
        ),
        evento_log="enviar_etapa16_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


def _enviar_etapa16(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento_log,
    tipo_tratamento=None,
):
    return enviar_pergunta_triagem(
        cliente_telefone,
        phone_id_unidade,
        id_etapa=ID_ETAPA16,
        cabecalho=montar_cabecalho_etapa16(),
        mensagem_bot=mensagem_bot,
        evento_log=evento_log,
        tipo_tratamento=tipo_tratamento,
    )
