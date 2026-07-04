import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa8 import (
    enviar_etapa8_contexto_email_invalido,
    enviar_etapa8_financeiro,
    enviar_etapa8_midia,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa8 import (
    TIPO_TRATAMENTO_EMAIL_INVALIDO,
    validar_etapa8,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_9_LINK_AGENDAMENTO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- APLICAR OS TRATAMENTOS UNIVERSAIS DA ETAPA 8
- ENCAMINHAR PARA A ETAPA 9 AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa8")


def resolve_etapa8(contexto_historico):
    """
    Mídia, financeiro e email inválido recebem tratamento sem avançar.

    Um email estruturalmente válido produz email_valido para resolver 8 -> 9.
    O envio da etapa 9 permanece simulado enquanto seu sender não existe.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # CAMPOS QUE VALIDAM MIDIA NA ETAPA 8
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        return enviar_etapa8_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    # CAMPOS QUE VALIDAM FINANCEIRO NA ETAPA 8
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_etapa8_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # CAMPOS QUE VALIDAM O CONTEXTO DE EMAIL NA ETAPA 8
    # O validador extrai um único email de respostas curtas ou frases.
    resultado_email = validar_etapa8(texto_cliente)

    if not resultado_email.valido:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_EMAIL_INVALIDO,
            motivo_detalhado=resultado_email.motivo,
        )

        return enviar_etapa8_contexto_email_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    evento_transicao = resultado_email.evento

    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados={ETAPA_9_LINK_AGENDAMENTO},
    )

    logger.info(
        "etapa8_email_recebido | acao=simular_envio_etapa9 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento_transicao,
        etapa_destino,
    )

    contexto_envio = _montar_contexto_etapa9_simulada(
        contexto_historico,
        etapa_destino,
    )
    contexto_envio["email_cliente"] = resultado_email.email

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


def _montar_contexto_etapa9_simulada(
    contexto_historico,
    etapa_destino,
):
    # TEMPORÁRIO: remover quando o sender real da etapa 9 existir.
    id_mensagem_fila = contexto_historico[
        "mensagem_cliente_atual"
    ]["id_mensagem_fila"]

    return {
        "enviou": True,
        "envio_simulado": True,
        "resposta_ja_existia": False,
        "mensagem_bot": (
            f"Nesse momento a futura etapa {etapa_destino} foi enviada."
        ),
        "id_hash_msg_bot": (
            f"simulacao.etapa{etapa_destino}.fila.{id_mensagem_fila}"
        ),
        "id_etapa_resultante": etapa_destino,
        "tipo_mensagem": "simulacao",
        "canal": "simulacao_worker",
        "atualizar_conversa": True,
        "atualizar_last_from_bot": True,
    }


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
