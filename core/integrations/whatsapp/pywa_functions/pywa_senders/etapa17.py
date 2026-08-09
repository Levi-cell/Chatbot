from core.integrations.whatsapp.messages.etapa17_messages import (
    montar_cabecalho_etapa17,
    montar_mensagem_cliente_contexto_invalido_etapa17,
    montar_mensagem_cliente_etapa17,
    montar_mensagem_dependente_contexto_invalido_etapa17,
    montar_mensagem_dependente_etapa17,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.triagem_base import (
    TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    enviar_pergunta_triagem,
)


ID_ETAPA17 = 17
# CENARIO NORMAL: PERGUNTA 6 SOBRE O PROPRIO CLIENTE
def enviar_etapa17_cliente(cliente_telefone, phone_id_unidade):
    return _enviar_etapa17(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_etapa17(),
        evento_log="enviar_etapa17_cliente",
    )


# CENARIO NORMAL: PERGUNTA 6 SOBRE O DEPENDENTE
def enviar_etapa17_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    return _enviar_etapa17(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_etapa17(nome_dependente),
        evento_log="enviar_etapa17_dependente",
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 6 SOBRE O PROPRIO CLIENTE
def enviar_etapa17_cliente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
):
    return _enviar_etapa17(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_cliente_contexto_invalido_etapa17(),
        evento_log="enviar_etapa17_cliente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


# RESPOSTA INVALIDA: REPETE A PERGUNTA 6 SOBRE O DEPENDENTE
def enviar_etapa17_dependente_contexto_invalido(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    return _enviar_etapa17(
        cliente_telefone,
        phone_id_unidade,
        montar_mensagem_dependente_contexto_invalido_etapa17(nome_dependente),
        evento_log="enviar_etapa17_dependente_contexto_invalido",
        tipo_tratamento=TIPO_TRATAMENTO_RESPOSTA_INVALIDA,
    )


def _enviar_etapa17(
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
        id_etapa=ID_ETAPA17,
        cabecalho=montar_cabecalho_etapa17(),
        mensagem_bot=mensagem_bot,
        evento_log=evento_log,
        tipo_tratamento=tipo_tratamento,
    )
