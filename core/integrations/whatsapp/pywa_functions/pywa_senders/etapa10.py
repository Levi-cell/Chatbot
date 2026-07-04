from core.integrations.whatsapp.messages.etapa10_messages import (
    montar_cabecalho_etapa10,
    montar_mensagem_cliente_contexto_invalido_etapa10,
    montar_mensagem_cliente_etapa10,
    montar_mensagem_dependente_contexto_invalido_etapa10,
    montar_mensagem_dependente_etapa10,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import (
    TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    enviar_pergunta_triagem,
)


ID_ETAPA10 = 10


# CENARIO NORMAL: PERGUNTA 1 SOBRE O PROPRIO CLIENTE
def enviar_etapa10_cliente(cliente_telefone, phone_id_unidade):
    return _enviar_etapa10(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_etapa10(),
        evento_log="enviar_etapa10_cliente",
    )


# CENARIO NORMAL: PERGUNTA 1 SOBRE O DEPENDENTE
def enviar_etapa10_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    return _enviar_etapa10(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_etapa10(nome_dependente),
        evento_log="enviar_etapa10_dependente",
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 1 SOBRE O PROPRIO CLIENTE
def enviar_etapa10_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_etapa10(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_contexto_invalido_etapa10(),
        evento_log="enviar_etapa10_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 1 SOBRE O DEPENDENTE
def enviar_etapa10_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    return _enviar_etapa10(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_contexto_invalido_etapa10(nome_dependente),
        evento_log="enviar_etapa10_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


def _enviar_etapa10(
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
        id_etapa=ID_ETAPA10,
        cabecalho=montar_cabecalho_etapa10(),
        mensagem_bot=mensagem_bot,
        evento_log=evento_log,
        tipo_tratamento=tipo_tratamento,
    )
