import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa10 import (
    enviar_etapa10_contexto_email_invalido,
    enviar_etapa10_financeiro,
    enviar_etapa10_midia,
    enviar_etapa10_reforco_escolar,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa11 import (
    enviar_etapa11,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa10 import (
    TIPO_TRATAMENTO_EMAIL_INVALIDO,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
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
    ETAPA_11_INTRODUCAO_TRIAGEM,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- APLICAR OS TRATAMENTOS UNIVERSAIS DA ETAPA 10
- ENCAMINHAR PARA A ETAPA 11 AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa10")


def resolve_etapa10(contexto_historico):
    """
    Preserva tratamentos e aplica a política efetiva antes de resolver 10 -> 11.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

# CAMPOS QUE VALIDAM MIDIA NA ETAPA 10
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        return enviar_etapa10_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )

        return enviar_etapa10_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
        )

# CAMPOS QUE VALIDAM FINANCEIRO NA ETAPA 10
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_etapa10_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

# CAMPOS QUE VALIDAM O CONTEXTO DE EMAIL NA ETAPA 10
    email_obrigatorio_efetivo = calcular_email_obrigatorio_efetivo(
        contexto_historico.get("email_obrigatorio_unidade", True),
        contexto_historico.get("status_dependente"),
        contexto_historico.get("idade_cliente"),
    )
    resultado_email = classificar_resposta_email(
        texto_cliente,
        email_obrigatorio=email_obrigatorio_efetivo,
    )

    if not resultado_email.aceita:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_EMAIL_INVALIDO,
            motivo_detalhado=resultado_email.motivo,
        )

        return enviar_etapa10_contexto_email_invalido(
            cliente_telefone,
            phone_id_unidade,
        )

    evento_transicao = resultado_email.evento

    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados={ETAPA_11_INTRODUCAO_TRIAGEM},
    )

    logger.info(
        "etapa10_email_recebido | acao=enviar_etapa11 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s "
        "email_obrigatorio_efetivo=%s resultado_coleta=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        evento_transicao,
        etapa_destino,
        email_obrigatorio_efetivo,
        resultado_email.classificacao,
    )

    contexto_envio = enviar_etapa11(
        cliente_telefone,
        phone_id_unidade,
    )
    contexto_envio["email_cliente"] = resultado_email.email
    contexto_envio["resultado_coleta_email"] = (
        resultado_email.classificacao
    )
    contexto_envio["email_obrigatorio_efetivo"] = (
        email_obrigatorio_efetivo
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )


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


def _logar_tratamento_texto(
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
