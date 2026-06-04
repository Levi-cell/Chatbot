import logging

from core.cache.cache_cliente import buscar_cliente_cache
from core.cache.cache_unidade import obter_id_unidade_redis_ou_plsql
from core.logging_config import short_value
from core.repositories.inserts import (
    inserindo_em_cliente_caso_seja_novo,
    inserindo_em_conversa_caso_seja_nova,
)
from core.repositories.querys import buscar_estado_conversa


logger = logging.getLogger("worker.valida_banco")


def validar_banco_mensagem(mensagem, cursor):
    id_unidade = obter_id_unidade_redis_ou_plsql(
        mensagem["id_phone_unidade"],
        cursor,
    )
    logger.debug(
        "unidade_resolvida | acao=continuar phone_number_id=%s id_unidade=%s",
        short_value(mensagem["id_phone_unidade"]),
        id_unidade,
    )

    id_cliente, inserido, cliente_cache_pendente = valida_cliente(
        mensagem["cliente_telefone"],
        cursor,
    )

    contexto_conversa = valida_conversa(
        id_cliente,
        id_unidade,
        inserido,
        cursor,
    )

    return {
        "id_unidade": id_unidade,
        "id_cliente": id_cliente,
        "cliente_telefone": mensagem["cliente_telefone"],
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "cliente_inserido": inserido,
        "cliente_cache_pendente": cliente_cache_pendente,
        "conversa": contexto_conversa,
    }


def valida_cliente(wa_id_telefone, cursor):
    id_cliente_cache = buscar_cliente_cache(wa_id_telefone)

    if id_cliente_cache:
        logger.info(
            "cliente_cache_hit | acao=usar_cliente id_cliente=%s",
            id_cliente_cache,
        )
        return id_cliente_cache, False, False

    id_cliente, inserido = inserindo_em_cliente_caso_seja_novo(wa_id_telefone, cursor)

    if inserido:
        logger.info(
            "cliente_criado | origem=banco acao=usar_cliente id_cliente=%s",
            id_cliente,
        )
    else:
        logger.info(
            "cliente_existente | origem=banco acao=usar_cliente id_cliente=%s",
            id_cliente,
        )

    return id_cliente, inserido, True


def valida_conversa(id_cliente, id_unidade, inserido, cursor):
    if inserido:
        id_conversa = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        contexto = _montar_contexto_conversa_nova(
            id_conversa=id_conversa,
            id_cliente=id_cliente,
            id_unidade=id_unidade,
            estado="nova",
            motivo="cliente_novo",
        )
        logger.info(
            "conversa_criada | motivo=cliente_novo acao=usar_conversa id_cliente=%s id_unidade=%s id_conversa=%s estado=nova",
            id_cliente,
            id_unidade,
            id_conversa,
        )
        return contexto

    estado_conversa = buscar_estado_conversa(id_cliente, id_unidade, cursor)

    if not estado_conversa:
        id_conversa = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        contexto = _montar_contexto_conversa_nova(
            id_conversa=id_conversa,
            id_cliente=id_cliente,
            id_unidade=id_unidade,
            estado="liberada",
            motivo="sem_historico_unidade",
        )
        logger.info(
            "conversa_criada | motivo=sem_historico_unidade acao=usar_conversa id_cliente=%s id_unidade=%s id_conversa=%s estado=liberada",
            id_cliente,
            id_unidade,
            id_conversa,
        )
        return contexto

    (
        id_conversa,
        id_etapa_atual,
        status_ativa,
        finalizou_em,
        estado,
        status_dependente,
        last_message_from,
        followup_stage,
        followup_last_sent_at,
        lead_no_funil,
    ) = estado_conversa

    if estado == "ativa":
        contexto = _montar_contexto_conversa_existente(
            id_conversa=id_conversa,
            id_cliente=id_cliente,
            id_unidade=id_unidade,
            estado=estado,
            id_etapa_atual=id_etapa_atual,
            status_ativa=status_ativa,
            status_dependente=status_dependente,
            last_message_from=last_message_from,
            followup_stage=followup_stage,
            followup_last_sent_at=followup_last_sent_at,
            lead_no_funil=lead_no_funil,
            finalizou_em=finalizou_em,
            motivo="conversa_ativa",
        )
        logger.info(
            "conversa_ativa | acao=usar_conversa id_cliente=%s id_unidade=%s id_conversa=%s id_etapa=%s status_dependente=%s",
            id_cliente,
            id_unidade,
            id_conversa,
            id_etapa_atual,
            contexto["status_dependente"],
        )
        return contexto

    if estado == "bloqueada":
        contexto = _montar_contexto_conversa_existente(
            id_conversa=id_conversa,
            id_cliente=id_cliente,
            id_unidade=id_unidade,
            estado=estado,
            id_etapa_atual=id_etapa_atual,
            status_ativa=status_ativa,
            status_dependente=status_dependente,
            last_message_from=last_message_from,
            followup_stage=followup_stage,
            followup_last_sent_at=followup_last_sent_at,
            lead_no_funil=lead_no_funil,
            finalizou_em=finalizou_em,
            motivo="finalizada_30_dias",
        )
        logger.info(
            "conversa_bloqueada | motivo=finalizada_30_dias acao=bloquear_mensagem id_cliente=%s id_unidade=%s id_conversa=%s id_etapa=%s finalizou_em=%s",
            id_cliente,
            id_unidade,
            id_conversa,
            id_etapa_atual,
            finalizou_em,
        )
        return contexto

    if estado == "liberada":
        id_conversa_nova = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        contexto = _montar_contexto_conversa_nova(
            id_conversa=id_conversa_nova,
            id_cliente=id_cliente,
            id_unidade=id_unidade,
            estado="liberada",
            motivo="bloqueio_expirado",
            conversa_anterior=id_conversa,
        )
        logger.info(
            "conversa_criada | motivo=bloqueio_expirado acao=usar_conversa id_cliente=%s id_unidade=%s id_conversa=%s conversa_anterior=%s estado=liberada",
            id_cliente,
            id_unidade,
            id_conversa_nova,
            id_conversa,
        )
        return contexto

    raise ValueError(
        f"Estado de conversa invalido: {estado} "
        f"(id_cliente={id_cliente}, id_unidade={id_unidade}, status_ativa={status_ativa})"
    )


def _montar_contexto_conversa_nova(
    id_conversa,
    id_cliente,
    id_unidade,
    estado,
    motivo,
    conversa_anterior=None,
):
    return {
        "id_conversa": id_conversa,
        "id_cliente": id_cliente,
        "id_unidade": id_unidade,
        "estado": estado,
        "id_etapa_atual": None,
        "status_ativa": True,
        "status_dependente": False,
        "last_message_from": "cliente",
        "followup_stage": 0,
        "followup_last_sent_at": None,
        "lead_no_funil": False,
        "finalizou_em": None,
        "conversa_anterior": conversa_anterior,
        "motivo": motivo,
    }


def _montar_contexto_conversa_existente(
    id_conversa,
    id_cliente,
    id_unidade,
    estado,
    id_etapa_atual,
    status_ativa,
    status_dependente,
    last_message_from,
    followup_stage,
    followup_last_sent_at,
    lead_no_funil,
    finalizou_em,
    motivo,
):
    return {
        "id_conversa": id_conversa,
        "id_cliente": id_cliente,
        "id_unidade": id_unidade,
        "estado": estado,
        "id_etapa_atual": id_etapa_atual,
        "status_ativa": bool(status_ativa),
        "status_dependente": bool(status_dependente),
        "last_message_from": last_message_from,
        "followup_stage": int(followup_stage or 0),
        "followup_last_sent_at": followup_last_sent_at,
        "lead_no_funil": bool(lead_no_funil),
        "finalizou_em": finalizou_em,
        "conversa_anterior": None,
        "motivo": motivo,
    }
