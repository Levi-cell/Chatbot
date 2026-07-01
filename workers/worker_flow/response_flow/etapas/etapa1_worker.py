import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa1 import (
    enviar_etapa1,
    enviar_etapa1_contexto_nome_invalido,
    enviar_etapa1_financeiro,
    enviar_etapa1_financeiro_inicio,
    enviar_etapa1_midia,
    enviar_etapa1_midia_inicio,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_etapa2,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    TIPO_TRATAMENTO_TIPO_NAO_SUPORTADO,
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_DESTINO_ATENDIMENTO,
    EVENTO_NOME_CLIENTE_VALIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR PRIMEIRA ETAPA
- ENCAMINHAR PARA SEGUNDA ETAPA
"""


logger = logging.getLogger("worker.etapa1")


def resolve_etapa1(contexto_historico):
    """
    id_etapa_atual is None não é uma etapa separada.
    É apenas o primeiro contato antes da etapa 1 ser persistida.

    Nome inválido, mídia e pergunta financeira possuem tratamento próprio.
    Somente nome válido produz o evento nome_cliente_valido.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    conversa_sem_etapa = id_etapa_atual is None

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        if conversa_sem_etapa:
            return enviar_etapa1_midia_inicio(
                cliente_telefone,
                phone_id_unidade,
            )

        return enviar_etapa1_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    # Pergunta financeira tem prioridade sobre a validação de nome.
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        if conversa_sem_etapa:
            return enviar_etapa1_financeiro_inicio(
                cliente_telefone,
                phone_id_unidade,
            )

        return enviar_etapa1_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # Primeiro contato normal: inicializa a conversa na etapa 1.
    if conversa_sem_etapa:
        return enviar_etapa1(
            cliente_telefone,
            phone_id_unidade,
        )

    resultado_nome = validar_nome_cliente(texto_cliente)

    if not resultado_nome.valido:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
            motivo_detalhado=resultado_nome.motivo,
        )

        return enviar_etapa1_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # A tabela precisa autorizar 1 + nome_cliente_valido -> 2 antes da
    # comunicação externa. Mapa ausente ou incorreto impede o envio.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_NOME_CLIENTE_VALIDO,
        destinos_esperados={ETAPA_DESTINO_ATENDIMENTO},
    )

    logger.debug(
        "etapa1_nome_validado | acao=enviar_etapa_destino id_conversa=%s evento=%s etapa_destino=%s primeiro_nome=%s",
        id_conversa,
        EVENTO_NOME_CLIENTE_VALIDO,
        etapa_destino,
        short_value(resultado_nome.primeiro_nome),
    )

    contexto_envio = enviar_etapa2(
        cliente_telefone,
        phone_id_unidade,
        nome=resultado_nome.primeiro_nome,
    )
    contexto_envio["primeiro_nome_cliente"] = resultado_nome.primeiro_nome

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_NOME_CLIENTE_VALIDO,
        etapa_destino,
    )


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


def _logar_tratamento_texto(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
