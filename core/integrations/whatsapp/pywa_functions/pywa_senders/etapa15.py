from core.integrations.whatsapp.messages.etapa15_messages import (
    montar_cabecalho_etapa15,
    montar_mensagem_cliente_contexto_invalido_etapa15,
    montar_mensagem_cliente_etapa15,
    montar_mensagem_dependente_contexto_invalido_etapa15,
    montar_mensagem_dependente_etapa15,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import (
    TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    enviar_pergunta_triagem,
)


ID_ETAPA15 = 15
# CENARIO NORMAL: PERGUNTA 4 SOBRE O PROPRIO CLIENTE
def enviar_etapa15_cliente(cliente_telefone, phone_id_unidade):
    return _enviar_etapa15(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_etapa15(),
        evento_log="enviar_etapa15_cliente",
    )


# CENARIO NORMAL: PERGUNTA 4 SOBRE O DEPENDENTE
def enviar_etapa15_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
    idade_dependente,
):
    return _enviar_etapa15(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_etapa15(
            nome_dependente,
            idade_dependente,
        ),
        evento_log="enviar_etapa15_dependente",
    )


# RESPOSTA INVALIDA: ORIENTACAO PROPRIA PARA A PERGUNTA 4 DO CLIENTE
def enviar_etapa15_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_etapa15(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_contexto_invalido_etapa15(),
        evento_log="enviar_etapa15_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


# RESPOSTA INVALIDA: ORIENTACAO PROPRIA PARA A PERGUNTA 4 DO DEPENDENTE
def enviar_etapa15_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
    idade_dependente,
):
    return _enviar_etapa15(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_contexto_invalido_etapa15(
            nome_dependente,
            idade_dependente,
        ),
        evento_log="enviar_etapa15_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


def _enviar_etapa15(
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
        id_etapa=ID_ETAPA15,
        cabecalho=montar_cabecalho_etapa15(),
        mensagem_bot=mensagem_bot,
        evento_log=evento_log,
        tipo_tratamento=tipo_tratamento,
    )
