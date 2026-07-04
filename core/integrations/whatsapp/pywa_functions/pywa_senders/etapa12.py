from core.integrations.whatsapp.messages.etapa12_messages import (
    montar_cabecalho_etapa12,
    montar_mensagem_cliente_contexto_invalido_etapa12,
    montar_mensagem_cliente_etapa12,
    montar_mensagem_dependente_contexto_invalido_etapa12,
    montar_mensagem_dependente_etapa12,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import (
    TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    enviar_pergunta_triagem,
)


ID_ETAPA12 = 12


# CENARIO NORMAL: PERGUNTA 3 SOBRE O PROPRIO CLIENTE
def enviar_etapa12_cliente(cliente_telefone, phone_id_unidade):
    return _enviar_etapa12(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_etapa12(),
        evento_log="enviar_etapa12_cliente",
    )


# CENARIO NORMAL: PERGUNTA 3 SOBRE O DEPENDENTE
def enviar_etapa12_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    return _enviar_etapa12(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_etapa12(nome_dependente),
        evento_log="enviar_etapa12_dependente",
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 3 SOBRE O PROPRIO CLIENTE
def enviar_etapa12_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_etapa12(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_contexto_invalido_etapa12(),
        evento_log="enviar_etapa12_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 3 SOBRE O DEPENDENTE
def enviar_etapa12_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    return _enviar_etapa12(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_contexto_invalido_etapa12(nome_dependente),
        evento_log="enviar_etapa12_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


def _enviar_etapa12(
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
        id_etapa=ID_ETAPA12,
        cabecalho=montar_cabecalho_etapa12(),
        mensagem_bot=mensagem_bot,
        evento_log=evento_log,
        tipo_tratamento=tipo_tratamento,
    )
