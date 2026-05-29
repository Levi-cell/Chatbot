import logging

from core.cache.cache_cliente import buscar_cliente_cache
from core.repositories.inserts import (
    inserindo_em_cliente_caso_seja_novo,
    inserindo_em_conversa_caso_seja_nova,
)
from core.repositories.querys import buscar_estado_conversa


logger = logging.getLogger("worker.support")


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

    ## PRIMEIRA VEZ QUE O CLIENTE CONVERSA COM UMA UNIDADE SUPERA
    if inserido:
        id_conversa = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        logger.info(
            "conversa_criada | motivo=cliente_novo acao=usar_conversa id_cliente=%s id_unidade=%s id_conversa=%s estado=nova",
            id_cliente,
            id_unidade,
            id_conversa,
        )
        return id_conversa, "nova", None

    estado_conversa = buscar_estado_conversa(id_cliente, id_unidade, cursor)

    ## AQUI SIGNIFICA QUE É A PRIMEIRA CONVERSA DO CLIENTE COM A UNIDADE
    if not estado_conversa:
        id_conversa = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        logger.info(
            "conversa_criada | motivo=sem_historico_unidade acao=usar_conversa id_cliente=%s id_unidade=%s id_conversa=%s estado=liberada",
            id_cliente,
            id_unidade,
            id_conversa,
        )
        return id_conversa, "liberada", None

    (
        id_conversa,
        id_etapa_atual,
        status_ativa,
        finalizou_em,
        estado,
    ) = estado_conversa

    ## AQUI O CLIENTE JÁ TEM UMA CONVERSA EM ANDAMENTO COM A UNIDADE
    if estado == "ativa":
        logger.info(
            "conversa_ativa | acao=usar_conversa id_cliente=%s id_unidade=%s id_conversa=%s",
            id_cliente,
            id_unidade,
            id_conversa,
        )
        return id_conversa, estado, None

    ## O CLIENTE JÁ FINALIZOU UMA CONVERSA COM A UNIDADE NOS ÚLTIMOS 30 DIAS
    if estado == "bloqueada":
        logger.info(
            "conversa_bloqueada | motivo=finalizada_30_dias acao=bloquear_mensagem id_cliente=%s id_unidade=%s id_conversa=%s id_etapa=%s finalizou_em=%s",
            id_cliente,
            id_unidade,
            id_conversa,
            id_etapa_atual,
            finalizou_em,
        )
        return id_conversa, estado, id_etapa_atual

    ## O CLIENTE JÁ TEVE OUTRA CONVERSA COM A UNIDADE POREM FOI FINALIZADA A MAIS DE 30 DIAS
    if estado == "liberada":
        id_conversa_nova = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        logger.info(
            "conversa_criada | motivo=bloqueio_expirado acao=usar_conversa id_cliente=%s id_unidade=%s id_conversa=%s conversa_anterior=%s estado=liberada",
            id_cliente,
            id_unidade,
            id_conversa_nova,
            id_conversa,
        )
        return id_conversa_nova, estado, None

    raise ValueError(
        f"Estado de conversa inválido: {estado} "
        f"(id_cliente={id_cliente}, id_unidade={id_unidade}, status_ativa={status_ativa})"
    )
