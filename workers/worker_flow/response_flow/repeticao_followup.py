"""Repetição neutra para retorno sem resposta válida nem tratamento específico.

A validação fica nos resolvers normais. Mantém também a recuperação sem envio
de respostas já confirmadas e a compatibilidade do retorno especial 8 -> 9.
"""

from core.integrations.whatsapp.messages.componentes_compartilhados import montar_texto_com_cabecalho
from core.integrations.whatsapp.messages.tratamentos.retorno_followup import montar_saudacao_retomada_followup
from core.integrations.whatsapp.pywa_functions.cliente import aplicar_prefixo_mensagem_bot, usar_prefixo_mensagem_bot
from workers.worker_flow.response_flow.etapas.resolver_etapa8 import resolve_etapa8
from workers.worker_flow.response_flow.transicoes.eventos import ETAPA_1_NOME_CLIENTE, ETAPA_8_OFERTA_ADIADA
from workers.worker_flow.response_flow.repeticao_etapa import (
    SENDERS_TRIAGEM, selecionar_sender_repeticao as _selecionar_sender,
)


def _texto(dados, chave):
    valor = dados.get(chave)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"Dado persistido ausente para repetição: {chave}")
    return valor.strip()


def enviar_repeticao_followup(contexto):
    resposta = contexto.get("resposta_bot_para_mensagem_atual")
    if resposta:
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta["id_hash_msg"],
            "id_etapa_resultante": resposta.get("id_etapa", contexto["id_etapa_atual"]),
        }
    mensagem = contexto["mensagem_cliente_atual"]
    # Na etapa 1, o nome ainda não foi coletado neste atendimento. O cadastro
    # pode ter um nome de conversa anterior e não autoriza essa personalização.
    nome_titular = (
        None
        if contexto["id_etapa_atual"] == ETAPA_1_NOME_CLIENTE
        else contexto["dados_repeticao"].get("nome_titular")
    )
    saudacao = montar_saudacao_retomada_followup(nome_titular)
    # Fora da triagem, a etapa possui uma repetição neutra. As perguntas
    # canônicas da triagem já são iguais na apresentação e na reapresentação.
    opcoes_envio = (
        {} if contexto["id_etapa_atual"] in SENDERS_TRIAGEM else {"repeticao": True}
    )
    with usar_prefixo_mensagem_bot(saudacao):
        if contexto["id_etapa_atual"] == ETAPA_8_OFERTA_ADIADA:
            envio = _enviar_retorno_etapa8(contexto, saudacao)
        else:
            sender, extras = _selecionar_sender(
                contexto["id_etapa_atual"], contexto["dados_repeticao"]
            )
            envio = sender(
                mensagem["cliente_telefone"],
                mensagem["id_phone_unidade"],
                *extras,
                **opcoes_envio,
            )
    # O cabeçalho já foi ao WhatsApp no corpo. O histórico recebe o mesmo texto.
    texto = envio["mensagem_bot"]
    if envio.get("cabecalho_mensagem"):
        texto = montar_texto_com_cabecalho(texto, envio["cabecalho_mensagem"])
    texto = aplicar_prefixo_mensagem_bot(texto, saudacao)
    resultado = {
        "enviou": envio["enviou"],
        "resposta_ja_existia": False,
        "id_hash_msg_bot": envio["id_hash_msg_bot"],
        "mensagem_bot": texto,
        "tipo_mensagem": envio["tipo_mensagem"],
        "id_etapa_resultante": envio["id_etapa_resultante"],
    }
    if contexto["id_etapa_atual"] == ETAPA_8_OFERTA_ADIADA:
        resultado.update(
            id_etapa_origem_transicao=envio["id_etapa_origem_transicao"],
            evento_transicao=envio["evento_transicao"],
        )
    return resultado


def _enviar_retorno_etapa8(contexto, saudacao):
    """Qualquer reação retoma a oferta; não interpreta aceite nem envia a etapa 8."""
    dados = contexto["dados_repeticao"]
    dependente = dados.get("status_dependente")
    if not isinstance(dependente, bool):
        raise ValueError("Destino de atendimento ausente para retorno da etapa 8")
    contexto_retorno = dict(
        contexto,
        status_dependente=dependente,
        nome_titular=_texto(dados, "nome_titular"),
        nome_dependente=_texto(dados, "nome_dependente") if dependente else None,
        # Suprime a saudação própria da etapa 9; o prefixo de follow-up já a acolhe.
        saudacao_retorno=saudacao,
    )
    return resolve_etapa8(contexto_retorno)
