import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa5 import (
    enviar_etapa5_contexto_nome_invalido,
    enviar_etapa5_financeiro,
    enviar_etapa5_midia,
    enviar_etapa5_reforco_escolar,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa6 import (
    enviar_etapa6_dependente,
)
from core.logging_config import short_value
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
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_6_IDADE_ALUNO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
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
    Mídia, financeiro e nome inválido recebem tratamento sem avançar.

    Nome válido resolve 5 -> 6, envia a etapa 6 e carrega o primeiro nome do
    dependente para a persistência transacional.
    """
    id_conversa = contexto_historico["id_conversa"]
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        return enviar_etapa5_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    # A dúvida sobre reforço é mais específica que o financeiro e o nome.
    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )
        return enviar_etapa5_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_etapa5_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    ### VALIDACAO DE NOME

    resultado_nome = validar_nome_cliente(texto_cliente)

    if not resultado_nome.valido:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
            motivo_detalhado=resultado_nome.motivo,
        )

        return enviar_etapa5_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )


    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.

    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_NOME_DEPENDENTE_VALIDO,
        destinos_esperados={ETAPA_6_IDADE_ALUNO},
    )

    logger.info(
        "etapa5_nome_dependente_validado | acao=enviar_etapa6 id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s primeiro_nome=%s",
        id_conversa,
        mensagem_cliente_atual["id_mensagem_fila"],
        EVENTO_NOME_DEPENDENTE_VALIDO,
        etapa_destino,
        short_value(resultado_nome.primeiro_nome),
    )

    contexto_envio = enviar_etapa6_dependente(
        cliente_telefone,
        phone_id_unidade,
        resultado_nome.primeiro_nome,
    )
    contexto_envio["primeiro_nome_dependente"] = resultado_nome.primeiro_nome

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_NOME_DEPENDENTE_VALIDO,
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
