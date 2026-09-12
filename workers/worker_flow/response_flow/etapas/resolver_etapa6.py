import logging

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa6 import (
    enviar_etapa6_cliente_contexto_idade_invalida,
    enviar_etapa6_cliente_financeiro,
    enviar_etapa6_cliente_menor_18,
    enviar_etapa6_cliente_midia,
    enviar_etapa6_cliente_reforco_escolar,
    enviar_etapa6_dependente_contexto_idade_invalida,
    enviar_etapa6_dependente_financeiro,
    enviar_etapa6_dependente_menor_5,
    enviar_etapa6_dependente_midia,
    enviar_etapa6_dependente_reforco_escolar,
    enviar_etapa6_idade_acima_99,
    enviar_etapa6_suporte_idoso,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa7 import (
    enviar_etapa7_cliente,
    enviar_etapa7_dependente,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    obter_idade_minima_dependente,
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_7_OFERTA_AULA,
    EVENTO_IDADE_VALIDA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa6")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"
MOTIVO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


def resolve_etapa6(contexto_historico):
    """
    Valida a idade do aluno e decide tratamento, encerramento ou 6 -> 7.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )
    bpa_ativo = bool(contexto_historico.get("bpa_ativo_unidade"))
    nome_dependente = contexto_historico.get("nome_dependente")
    nome_cliente = contexto_historico.get("nome_cliente")
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

    # A dúvida sobre reforço é mais específica que o financeiro e a idade.
    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )
        return _enviar_tratamento_reforco_escolar(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

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

    resultado_idade = validar_idade(texto_cliente)

    if not resultado_idade.valida and not resultado_idade.acima_limite:
        _logar_tratamento(
            contexto_historico,
            "idade_invalida",
            motivo_detalhado=resultado_idade.motivo,
        )
        return _enviar_tratamento_idade_invalida(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    if resultado_idade.acima_limite:
        contexto_envio = enviar_etapa6_idade_acima_99(
            cliente_telefone,
            phone_id_unidade,
            contexto_historico.get("numero_comercial_unidade"),
        )
        return _anexar_encerramento(
            contexto_envio,
            resultado_idade.idade,
            MOTIVO_IDADE_ACIMA_99,
        )

    idade = resultado_idade.idade

    # A chave ausente é erro; None é a configuração explicitamente desativada.
    idade_minima = validar_idade_minima_suporte(
        contexto_historico["idade_minima_suporte"]
    )

    # O tratamento universal de 100+ já ocorreu. Dependentes seguem seu fluxo.
    if (
        not status_dependente
        and idade_minima is not None
        and idade >= idade_minima
    ):
        contexto_envio = enviar_etapa6_suporte_idoso(
            cliente_telefone,
            phone_id_unidade,
            contexto_historico.get("numero_comercial_unidade"),
            idade_minima,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_SUPORTE_IDOSO,
        )

    if not status_dependente and idade < 18:
        contexto_envio = enviar_etapa6_cliente_menor_18(
            cliente_telefone,
            phone_id_unidade,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_CLIENTE_MENOR_18,
        )

    idade_minima_dependente = obter_idade_minima_dependente(
        bpa_ativo
    )

    if status_dependente and idade < idade_minima_dependente:
        contexto_envio = enviar_etapa6_dependente_menor_5(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
            idade_minima_dependente,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_DEPENDENTE_MENOR_5,
            excluir_dependente=True,
        )

    # VALIDANDO DESTINO(S)
    # A resposta passou pelos tratamentos; agora o mapa autoriza 6 -> 7.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_IDADE_VALIDA,
        destinos_esperados={ETAPA_7_OFERTA_AULA},
    )

    logger.info(
        "etapa6_idade_validada | acao=enviar_etapa7 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s idade=%s status_dependente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_IDADE_VALIDA,
        etapa_destino,
        idade,
        status_dependente,
    )

    if status_dependente:
        contexto_envio = enviar_etapa7_dependente(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )
    else:
        contexto_envio = enviar_etapa7_cliente(
            cliente_telefone,
            phone_id_unidade,
            nome_cliente,
        )

    contexto_envio["idade_aluno"] = idade

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_IDADE_VALIDA,
        etapa_destino,
    )


def _enviar_tratamento_midia(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa6_dependente_midia(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_midia(
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
        return enviar_etapa6_dependente_financeiro(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_financeiro(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_reforco_escolar(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa6_dependente_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_reforco_escolar(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_idade_invalida(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa6_dependente_contexto_idade_invalida(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_contexto_idade_invalida(
        cliente_telefone,
        phone_id_unidade,
    )


def _anexar_encerramento(
    contexto_envio,
    idade,
    motivo,
    *,
    excluir_dependente=False,
):
    contexto_envio.update(
        {
            "idade_aluno": idade,
            "encerrar_atendimento": True,
            "motivo_encerramento": motivo,
            "excluir_dependente": excluir_dependente,
        }
    )
    return contexto_envio


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
