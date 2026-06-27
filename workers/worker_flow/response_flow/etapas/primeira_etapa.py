import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa1 import (
    enviar_primeira_etapa,
    enviar_primeira_etapa_contexto_nome_invalido,
    enviar_primeira_etapa_financeiro,
    enviar_primeira_etapa_financeiro_inicio,
    enviar_primeira_etapa_midia,
    enviar_primeira_etapa_midia_inicio,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_segunda_etapa,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.detector_etapas.detector_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    detecta_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.detector_etapas.detector_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    detecta_midia,
)
from workers.worker_flow.response_flow.etapas.detector_etapas.detector_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_nome_cliente,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR PRIMEIRA ETAPA
- ENCAMINHAR PARA SEGUNDA ETAPA
"""


logger = logging.getLogger("worker.primeira_etapa")


def resolve_primeira_etapa(contexto_historico):
    """
    id_etapa_atual is None não é uma etapa separada.
    É apenas o primeiro contato antes da etapa 1 ser persistida.

    NotImplementedError não representa nome inválido, mídia ou pergunta
    financeira. Esses casos têm tratamento da etapa 1 e mantêm a conversa
    na etapa atual.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    conversa_sem_etapa = id_etapa_atual is None

    ## CAMPOS QUE VALIDAM MIDIA SEJA EM INICIO DE CONVERSA OU APOS NOME

    if detecta_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        if conversa_sem_etapa:
            return enviar_primeira_etapa_midia_inicio(
                cliente_telefone,
                phone_id_unidade,
            )

        return enviar_primeira_etapa_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    ## CAMPOS QUE VALIDAM FINANCEIRO SEJA EM INICIO DE CONVERSA OU APOS NOME

    if detecta_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        if conversa_sem_etapa:
            return enviar_primeira_etapa_financeiro_inicio(
                cliente_telefone,
                phone_id_unidade,
            )

        return enviar_primeira_etapa_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    ### CENARIO NORMAL

    if conversa_sem_etapa:
        return enviar_primeira_etapa(
            cliente_telefone,
            phone_id_unidade,
        )

    ## Aqui capturamos o resultado se o nome foi validado para ver se pode passar para etapa 2
    resultado_nome = validar_nome_cliente(texto_cliente)

    ## Se não for valido entra aqui e envia tratamento
    if not resultado_nome.valido:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
            motivo_detalhado=resultado_nome.motivo,
        )

        return enviar_primeira_etapa_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    ### Uma vez valido aqui fica a ponte entre etapa 1 e 2
    logger.debug(
        "primeira_etapa_nome_validado | acao=enviar_etapa_2 id_conversa=%s primeiro_nome=%s",
        id_conversa,
        short_value(resultado_nome.primeiro_nome),
    )

    contexto_envio = enviar_segunda_etapa(
        cliente_telefone,
        phone_id_unidade,
        nome=resultado_nome.primeiro_nome,
    )
    contexto_envio["primeiro_nome_cliente"] = resultado_nome.primeiro_nome

    return contexto_envio


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


def _logar_tratamento_texto(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s etapa_resposta=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
        contexto_historico["id_etapa_resposta"],
    )
