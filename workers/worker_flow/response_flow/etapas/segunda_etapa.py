import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_segunda_etapa_contexto_opcao_invalida,
    enviar_segunda_etapa_financeiro,
    enviar_segunda_etapa_midia,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_segunda_etapa import (
    OPCAO_PARA_OUTRA_PESSOA,
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_segunda_etapa,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A SEGUNDA ETAPA
- ENCAMINHAR PARA A TERCEIRA ETAPA
"""


logger = logging.getLogger("worker.segunda_etapa")


def resolve_segunda_etapa(contexto_historico):
    """
    Midia e pergunta financeira recebem tratamento sem avancar a conversa.

    As duas opcoes de contexto avancam para a etapa 3. Enquanto o sender da
    etapa 3 nao existe, o envio e representado por um contexto simulado e
    persistido, preservando a idempotencia do worker.
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

        return enviar_segunda_etapa_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    ## CAMPOS QUE VALIDAM FINANCEIRO NA ETAPA 2

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_segunda_etapa_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    ## VALIDACAO DE CONTEXTO ESPECIFICA DA ETAPA 2

    opcao_atendimento = validar_segunda_etapa(texto_cliente)

    if opcao_atendimento is None:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )

        return enviar_segunda_etapa_contexto_opcao_invalida(
            cliente_telefone,
            phone_id_unidade,
        )

    ## PONTE ENTRE A ETAPA 2 E A FUTURA ETAPA 3
    # TEMPORARIO: substituir este log e o contexto simulado pela chamada ao
    # sender real da etapa 3 quando ele existir. Depois disso, remover tambem
    # _montar_contexto_etapa_3_simulada().

    status_dependente = (
        opcao_atendimento == OPCAO_PARA_OUTRA_PESSOA
    )

    logger.info(
        "nesse momento a futura etapa 3 foi enviada | acao=simular_envio_etapa_3 id_conversa=%s id_mensagem_fila=%s opcao_atendimento=%s status_dependente=%s",
        id_conversa,
        mensagem_cliente_atual["id_mensagem_fila"],
        opcao_atendimento,
        status_dependente,
    )

    return _montar_contexto_etapa_3_simulada(
        contexto_historico,
        opcao_atendimento,
        status_dependente,
    )


def _montar_contexto_etapa_3_simulada(
    contexto_historico,
    opcao_atendimento,
    status_dependente,
):
    # TEMPORARIO: este contexto existe somente para testar a transicao 2 -> 3
    # antes da implementacao do sender da etapa 3. Nao representa envio Meta.
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    id_mensagem_fila = mensagem_cliente["id_mensagem_fila"]

    return {
        "enviou": True,
        "envio_simulado": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "Nesse momento a futura etapa 3 foi enviada.",
        "id_hash_msg_bot": f"simulacao.etapa3.fila.{id_mensagem_fila}",
        "id_etapa_resultante": 3,
        "tipo_mensagem": "simulacao",
        "canal": "simulacao_worker",
        "atualizar_conversa": True,
        "atualizar_last_from_bot": True,
        "opcao_atendimento": opcao_atendimento,
        "status_dependente": status_dependente,
    }


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s etapa_resposta=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s etapa_resposta=%s",
        motivo,
        None,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )
