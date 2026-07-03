import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa5 import (
    enviar_etapa5_cliente_contexto_invalido,
    enviar_etapa5_cliente_financeiro,
    enviar_etapa5_cliente_midia,
    enviar_etapa5_dependente_contexto_invalido,
    enviar_etapa5_dependente_financeiro,
    enviar_etapa5_dependente_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa6 import (
    enviar_etapa6,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa5 import (
    OPCAO_QUERO_AGENDAR,
    OPCAO_TALVEZ_MAIS_TARDE,
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_etapa5,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_6_OFERTA_ADIADA,
    ETAPA_8_EMAIL,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A ETAPA 5
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa5")


def resolve_etapa5(contexto_historico):
    """
    Mídia, financeiro e contexto inválido recebem tratamento sem avançar.

    oferta_aceita resolve 5 -> 8.
    oferta_adiada resolve 5 -> 6.

    A etapa 6 possui sender real. O envio da etapa 8 permanece simulado
    somente enquanto seu sender ainda não existe.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )
    nome_dependente = contexto_historico.get("nome_dependente")
    link_instagram = contexto_historico.get(
        "link_instagram_unidade"
    )
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tratamento(
            contexto_historico,
            "tipo_mensagem_nao_suportado",
        )
        return _enviar_tratamento_midia(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    # Pergunta financeira tem prioridade sobre a decisão da oferta.
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )
        return _enviar_tratamento_financeiro(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    # VALIDANDO OPÇÕES
    evento_transicao = validar_etapa5(texto_cliente)

    if evento_transicao is None:
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )
        return _enviar_tratamento_contexto_invalido(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    # VALIDANDO DESTINO(S)
    # A resposta passou pelos tratamentos; agora o mapa autoriza a aresta.
    destinos_esperados = _destinos_esperados_por_evento(
        evento_transicao
    )
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados=destinos_esperados,
    )

    logger.info(
        "etapa5_oferta_validada | acao=%s "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "status_dependente=%s",
        (
            "enviar_etapa6"
            if evento_transicao == OPCAO_TALVEZ_MAIS_TARDE
            else "simular_envio_etapa8"
        ),
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento_transicao,
        etapa_destino,
        status_dependente,
    )

    if evento_transicao == OPCAO_TALVEZ_MAIS_TARDE:
        contexto_envio = enviar_etapa6(
            cliente_telefone,
            phone_id_unidade,
            link_instagram,
        )
    else:
        contexto_envio = _montar_contexto_etapa8_simulada(
            contexto_historico,
            etapa_destino,
        )
    contexto_envio["decisao_oferta"] = evento_transicao

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


def _enviar_tratamento_midia(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa5_dependente_midia(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa5_cliente_midia(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_financeiro(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa5_dependente_financeiro(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa5_cliente_financeiro(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_contexto_invalido(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa5_dependente_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa5_cliente_contexto_invalido(
        cliente_telefone,
        phone_id_unidade,
    )


def _destinos_esperados_por_evento(evento_transicao):
    if evento_transicao == OPCAO_QUERO_AGENDAR:
        return {ETAPA_8_EMAIL}

    if evento_transicao == OPCAO_TALVEZ_MAIS_TARDE:
        return {ETAPA_6_OFERTA_ADIADA}

    return set()


def _montar_contexto_etapa8_simulada(
    contexto_historico,
    etapa_destino,
):
    # TEMPORÁRIO: remover quando o sender real da etapa 8 existir.
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


def _logar_tratamento(
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
