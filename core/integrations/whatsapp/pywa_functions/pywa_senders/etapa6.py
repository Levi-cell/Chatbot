import logging
from pywa.types import URLButton

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_botao_idade_acima_99_etapa6,
    montar_botao_suporte_idoso_etapa6,
    montar_mensagem_cliente_menor_18_etapa6,
    montar_mensagem_contexto_idade_dependente_invalida_etapa6,
    montar_mensagem_contexto_idade_invalida_etapa6,
    montar_mensagem_dependente_menor_5_etapa6,
    montar_mensagem_idade_acima_99_etapa6,
    montar_mensagem_idade_dependente_etapa6,
    montar_mensagem_idade_dependente_etapa6_financeiro,
    montar_mensagem_idade_dependente_etapa6_midia,
    montar_mensagem_idade_dependente_etapa6_reforco_escolar,
    montar_mensagem_idade_etapa6,
    montar_mensagem_idade_etapa6_financeiro,
    montar_mensagem_idade_etapa6_midia,
    montar_mensagem_idade_etapa6_reforco_escolar,
    montar_mensagem_suporte_idoso_etapa6,
)
from core.integrations.whatsapp.numero_comercial import (
    montar_link_numero_comercial_whatsapp,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa6")

ID_ETAPA6 = 6
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_IDADE_INVALIDA = "idade_invalida"


# CENARIO NORMAL: PERGUNTAR A IDADE DO PROPRIO CLIENTE
def enviar_etapa6_cliente(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_idade_etapa6()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente",
    )


# CENARIO NORMAL: PERGUNTAR A IDADE DO DEPENDENTE
def enviar_etapa6_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa6(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente",
    )


# CLIENTE RESPONDE A ETAPA 6 COM MIDIA
def enviar_etapa6_cliente_midia(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_idade_etapa6_midia()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM MIDIA
def enviar_etapa6_dependente_midia(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa6_midia(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A IDADE COM PERGUNTA FINANCEIRA
def enviar_etapa6_cliente_financeiro(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_idade_etapa6_financeiro()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA
def enviar_etapa6_dependente_financeiro(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa6_financeiro(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR
def enviar_etapa6_cliente_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_idade_etapa6_reforco_escolar()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


def enviar_etapa6_dependente_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa6_reforco_escolar(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


# CLIENTE RESPONDE A ETAPA 6 COM IDADE INVALIDA
def enviar_etapa6_cliente_contexto_idade_invalida(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_contexto_idade_invalida_etapa6()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_contexto_idade_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_IDADE_INVALIDA,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM IDADE INVALIDA
def enviar_etapa6_dependente_contexto_idade_invalida(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = (
        montar_mensagem_contexto_idade_dependente_invalida_etapa6(
            nome_dependente
        )
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_contexto_idade_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_IDADE_INVALIDA,
    )


# CLIENTE COM MENOS DE 18 ANOS
def enviar_etapa6_cliente_menor_18(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_cliente_menor_18_etapa6()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_menor_18",
    )


# DEPENDENTE COM MENOS DE 5 ANOS
def enviar_etapa6_dependente_menor_5(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
    idade_minima=5,
):
    mensagem_bot = montar_mensagem_dependente_menor_5_etapa6(
        nome_dependente,
        idade_minima,
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_menor_5",
    )


# CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS
def enviar_etapa6_idade_acima_99(
    cliente_telefone,
    phone_id_unidade,
    numero_comercial,
):
    mensagem_bot = montar_mensagem_idade_acima_99_etapa6()
    botao_url = URLButton(
        title=montar_botao_idade_acima_99_etapa6(),
        url=montar_link_numero_comercial_whatsapp(numero_comercial),
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_idade_acima_99",
        botao_url=botao_url,
    )


def enviar_etapa6_suporte_idoso(
    cliente_telefone,
    phone_id_unidade,
    numero_comercial,
):
    mensagem_bot = montar_mensagem_suporte_idoso_etapa6()
    botao_url = URLButton(
        title=montar_botao_suporte_idoso_etapa6(),
        url=montar_link_numero_comercial_whatsapp(numero_comercial),
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_suporte_idoso",
        botao_url=botao_url,
    )


# CONSTRUTOR DE ENVIO DE TEXTO DA ETAPA 6
def _enviar_texto_etapa6(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
    tipo_tratamento=None,
    botao_url=None,
):
    try:
        cliente_wa = conta_wa(phone_id_unidade)
        parametros_envio = {
            "to": cliente_telefone,
            "text": mensagem_bot,
        }

        if botao_url is not None:
            parametros_envio["buttons"] = botao_url

        sent_message = cliente_wa.send_message(
            **parametros_envio,
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s id_hash_msg_bot=%s tratamento=%s",
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
            "id_etapa_resultante": ID_ETAPA6,
            "tipo_mensagem": (
                "interactive_cta_url" if botao_url else "text"
            ),
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
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 6",
            id_etapa=ID_ETAPA6,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
