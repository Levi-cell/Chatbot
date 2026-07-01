import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import (
    enviar_etapa3_contexto_nome_invalido,
    enviar_etapa3_financeiro,
    enviar_etapa3_midia,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_IDADE_ALUNO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A ETAPA 3
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa3")


def resolve_etapa3(contexto_historico):
    """
    Mídia, financeiro e nome inválido recebem tratamento sem avançar.

    Nome válido resolve 3 -> 4 e carrega o primeiro nome do dependente para
    a persistência transacional. A etapa 4 permanece simulada até seu sender
    real ser implementado.
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

        return enviar_etapa3_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    # Pergunta financeira tem prioridade sobre a validação de nome.
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_etapa3_financeiro(
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

        return enviar_etapa3_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_NOME_DEPENDENTE_VALIDO,
        destinos_esperados={ETAPA_IDADE_ALUNO},
    )

    logger.info(
        "etapa3_nome_dependente_validado | acao=simular_envio_etapa4 id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s primeiro_nome=%s",
        id_conversa,
        mensagem_cliente_atual["id_mensagem_fila"],
        EVENTO_NOME_DEPENDENTE_VALIDO,
        etapa_destino,
        short_value(resultado_nome.primeiro_nome),
    )

    contexto_envio = _montar_contexto_etapa4_simulada(
        contexto_historico,
        etapa_destino,
    )
    contexto_envio["primeiro_nome_dependente"] = resultado_nome.primeiro_nome

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_NOME_DEPENDENTE_VALIDO,
        etapa_destino,
    )


def _montar_contexto_etapa4_simulada(
    contexto_historico,
    etapa_destino,
):
    # TEMPORARIO: remover quando o sender real da etapa 4 existir.
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    id_mensagem_fila = mensagem_cliente["id_mensagem_fila"]

    return {
        "enviou": True,
        "envio_simulado": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "Nesse momento a futura etapa 4 foi enviada.",
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
