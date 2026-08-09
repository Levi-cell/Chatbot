import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa8 import (
    enviar_etapa8,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa9 import (
    enviar_etapa9_cliente_contexto_invalido,
    enviar_etapa9_cliente_financeiro,
    enviar_etapa9_cliente_midia,
    enviar_etapa9_dependente_contexto_invalido,
    enviar_etapa9_dependente_financeiro,
    enviar_etapa9_dependente_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa10 import (
    enviar_etapa10,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa9 import (
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_etapa9,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_10_EMAIL,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A ETAPA 9
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa9")


def resolve_etapa9(contexto_historico):
    """
    Mídia, financeiro e contexto inválido recebem tratamento sem avançar.

    retorno_confirmado resolve 9 -> 10.
    retorno_adiado resolve 9 -> 8.

    As etapas 8 e 10 possuem senders reais.
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

# CAMPOS QUE VALIDAM MIDIA NA ETAPA 9
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        if status_dependente:
            return enviar_etapa9_dependente_midia(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa9_cliente_midia(
            cliente_telefone,
            phone_id_unidade,
        )

# CAMPOS QUE VALIDAM FINANCEIRO NA ETAPA 9
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        if status_dependente:
            return enviar_etapa9_dependente_financeiro(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa9_cliente_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO OPCOES
    # O validador contextual já devolve o evento pertencente à etapa 9.
    evento_transicao = validar_etapa9(texto_cliente)

    if evento_transicao is None:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )

        if status_dependente:
            return enviar_etapa9_dependente_contexto_invalido(
                cliente_telefone,
                phone_id_unidade,
                nome_dependente,
            )

        return enviar_etapa9_cliente_contexto_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
    destinos_esperados = _destinos_esperados_por_evento(
        evento_transicao
    )
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados=destinos_esperados,
    )

    logger.info(
        "etapa9_retorno_validado | acao=%s "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "status_dependente=%s",
        (
            "enviar_etapa8"
            if evento_transicao == EVENTO_RETORNO_ADIADO
            else "enviar_etapa10"
        ),
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento_transicao,
        etapa_destino,
        status_dependente,
    )

    if evento_transicao == EVENTO_RETORNO_ADIADO:
        contexto_envio = enviar_etapa8(
            cliente_telefone,
            phone_id_unidade,
            link_instagram,
        )
    else:
        contexto_envio = enviar_etapa10(
            cliente_telefone,
            phone_id_unidade,
        )

    contexto_envio["decisao_retorno"] = evento_transicao

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


def _destinos_esperados_por_evento(evento_transicao):
    if evento_transicao == EVENTO_RETORNO_CONFIRMADO:
        return {ETAPA_10_EMAIL}

    if evento_transicao == EVENTO_RETORNO_ADIADO:
        return {ETAPA_8_OFERTA_ADIADA}

    return set()


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        None,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
