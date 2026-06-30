import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
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


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A SEGUNDA ETAPA
- ENCAMINHAR PARA A TERCEIRA ETAPA
"""


logger = logging.getLogger("worker.segunda_etapa")


def resolve_segunda_etapa(contexto_historico):
    """
    Midia e pergunta financeira recebem tratamento sem avancar a conversa.

    A validacao das opcoes "Para mim" e "Para outra pessoa", assim como a
    ponte para a etapa 3, sera implementada no proximo passo.
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

    ## PROXIMO PASSO
    # Validar se o cliente escolheu "Para mim" ou "Para outra pessoa".
    # Se a opcao for valida, chamar o sender da etapa 3 e avancar a conversa.
    # Se a opcao for invalida, reenviar a etapa 2 com tratamento de contexto.

    logger.warning(
        "segunda_etapa_contexto_pendente | acao=nao_enviar id_conversa=%s etapa_atual=%s etapa_resposta=%s",
        id_conversa,
        contexto_historico.get("id_etapa_atual"),
        contexto_historico.get("id_etapa_resposta"),
    )
    raise NotImplementedError(
        "Validacao das opcoes da etapa 2 ainda nao implementada"
    )


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
