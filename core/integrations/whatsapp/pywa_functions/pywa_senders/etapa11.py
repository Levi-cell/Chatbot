from core.integrations.whatsapp.messages.etapa11_messages import (
    montar_cabecalho_etapa11,
    montar_mensagem_cliente_contexto_invalido_etapa11,
    montar_mensagem_cliente_etapa11,
    montar_mensagem_dependente_contexto_invalido_etapa11,
    montar_mensagem_dependente_etapa11,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import (
    TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    enviar_pergunta_triagem,
)


ID_ETAPA11 = 11


# CENARIO NORMAL: PERGUNTA 1 SOBRE O PROPRIO CLIENTE
def enviar_etapa11_cliente(cliente_telefone, phone_id_unidade):
    return _enviar_etapa11(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_etapa11(),
        evento_log="enviar_etapa11_cliente",
    )


# CENARIO NORMAL: PERGUNTA 1 SOBRE O DEPENDENTE
def enviar_etapa11_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    return _enviar_etapa11(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_etapa11(nome_dependente),
        evento_log="enviar_etapa11_dependente",
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 1 SOBRE O PROPRIO CLIENTE
def enviar_etapa11_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_etapa11(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_contexto_invalido_etapa11(),
        evento_log="enviar_etapa11_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 1 SOBRE O DEPENDENTE
def enviar_etapa11_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    return _enviar_etapa11(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_contexto_invalido_etapa11(nome_dependente),
        evento_log="enviar_etapa11_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


def _enviar_etapa11(
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
        id_etapa=ID_ETAPA11,
        cabecalho=montar_cabecalho_etapa11(),
        mensagem_bot=mensagem_bot,
        evento_log=evento_log,
        tipo_tratamento=tipo_tratamento,
    )
