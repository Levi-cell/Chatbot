import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import (
    enviar_etapa3_contexto_profissao_invalida,
    enviar_etapa3_financeiro,
    enviar_etapa3_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import (
    enviar_etapa4,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa5 import (
    enviar_etapa5_cliente,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa3 import (
    validar_profissao_etapa3,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.validador_financeiro_etapa3 import (
    validar_pergunta_financeira_etapa3,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_4_NOME_DEPENDENTE,
    ETAPA_5_IDADE_ALUNO,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
    EVENTO_PROFISSAO_TITULAR_VALIDA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa3")

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_PROFISSAO_INVALIDA = "profissao_invalida"


def resolve_etapa3(contexto_historico):
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(contexto_historico.get("status_dependente"))
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    if validar_midia(tipo_mensagem):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_MIDIA,
        )
        return enviar_etapa3_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_pergunta_financeira_etapa3(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )
        return enviar_etapa3_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    resultado_profissao = validar_profissao_etapa3(
        texto_cliente,
        tipo_mensagem,
    )

    if not resultado_profissao.valida:
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_PROFISSAO_INVALIDA,
            motivo_detalhado=resultado_profissao.motivo,
        )
        return enviar_etapa3_contexto_profissao_invalida(
            cliente_telefone,
            phone_id_unidade,
        )

    if status_dependente:
        evento = EVENTO_PROFISSAO_DEPENDENTE_VALIDA
        destino_esperado = ETAPA_4_NOME_DEPENDENTE
    else:
        evento = EVENTO_PROFISSAO_TITULAR_VALIDA
        destino_esperado = ETAPA_5_IDADE_ALUNO

    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento,
        destinos_esperados={destino_esperado},
    )

    if status_dependente:
        contexto_envio = enviar_etapa4(
            cliente_telefone,
            phone_id_unidade,
        )
    else:
        contexto_envio = enviar_etapa5_cliente(
            cliente_telefone,
            phone_id_unidade,
        )

    contexto_envio["profissao"] = resultado_profissao.profissao

    logger.info(
        "etapa3_profissao_validada | acao=avancar_fluxo id_conversa=%s "
        "id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "status_dependente=%s profissao=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento,
        etapa_destino,
        status_dependente,
        short_value(resultado_profissao.profissao),
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento,
        etapa_destino,
    )


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
