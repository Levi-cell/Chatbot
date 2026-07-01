import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_etapa2_contexto_opcao_invalida,
    enviar_etapa2_financeiro,
    enviar_etapa2_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import (
    enviar_etapa3,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    OPCAO_PARA_MIM,
    OPCAO_PARA_OUTRA_PESSOA,
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_etapa2,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_IDADE_ALUNO,
    ETAPA_NOME_DEPENDENTE,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A SEGUNDA ETAPA
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA, QUE É a 3 ou 4
"""


logger = logging.getLogger("worker.etapa2")


def resolve_etapa2(contexto_historico):
    """
    Mídia, financeiro e contexto inválido recebem tratamento sem avançar.

    para_mim resolve 2 -> 4.
    para_outra_pessoa resolve 2 -> 3.

    A etapa 3 possui sender real. A etapa 4 continua simulada até seu sender
    existir. A simulação não altera a autorização da transição.
    """
    id_conversa = contexto_historico["id_conversa"]
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    ## CAMPOS QUE VALIDAM MIDIA NA ETAPA 2

    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        return enviar_etapa2_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    ## CAMPOS QUE VALIDAM FINANCEIRO NA ETAPA 2

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_etapa2_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )


    ### VALIDANDO OPCOES
    evento_transicao = validar_etapa2(texto_cliente)

    if evento_transicao is None:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )

        return enviar_etapa2_contexto_opcao_invalida(
            cliente_telefone,
            phone_id_unidade,
        )

    destinos_esperados = _destinos_esperados_por_evento(evento_transicao)
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados=destinos_esperados,
    )
    status_dependente = (
        evento_transicao == OPCAO_PARA_OUTRA_PESSOA
    )

    # O mapa autoriza o destino antes de qualquer envio externo.
    if evento_transicao == OPCAO_PARA_OUTRA_PESSOA:
        contexto_envio = enviar_etapa3(
            cliente_telefone,
            phone_id_unidade,
        )
        contexto_envio["opcao_atendimento"] = evento_transicao
        contexto_envio["status_dependente"] = status_dependente
    else:
        # TEMPORARIO: a etapa 4 ainda nao possui sender real.
        logger.info(
            "nesse momento a futura etapa %s foi enviada | acao=simular_envio_etapa id_conversa=%s id_mensagem_fila=%s evento=%s status_dependente=%s",
            etapa_destino,
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            evento_transicao,
            status_dependente,
        )

        contexto_envio = _montar_contexto_etapa_simulada(
            contexto_historico,
            etapa_destino,
            evento_transicao,
            status_dependente,
        )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


def _destinos_esperados_por_evento(evento_transicao):
    if evento_transicao == OPCAO_PARA_MIM:
        return {ETAPA_IDADE_ALUNO}

    if evento_transicao == OPCAO_PARA_OUTRA_PESSOA:
        return {ETAPA_NOME_DEPENDENTE}

    return set()


def _montar_contexto_etapa_simulada(
    contexto_historico,
    etapa_destino,
    evento_transicao,
    status_dependente,
):
    # TEMPORARIO: remover esta simulacao quando o sender da etapa 4 existir.
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    id_mensagem_fila = mensagem_cliente["id_mensagem_fila"]

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
        "opcao_atendimento": evento_transicao,
        "status_dependente": status_dependente,
    }


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        None,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
