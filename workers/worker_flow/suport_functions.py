import logging

from core.repositories.inserts import (
    inserindo_em_cliente_caso_seja_novo,
    inserindo_em_conversa_caso_seja_nova,
)
from core.repositories.querys import buscar_estado_conversa


logger = logging.getLogger("worker.support")


def valida_cliente(wa_id_telefone, cursor):
    id_cliente, inserido = inserindo_em_cliente_caso_seja_novo(wa_id_telefone, cursor)

    if inserido:
        logger.info("cliente_criado | id_cliente=%s", id_cliente)
    else:
        logger.info("cliente_existente | id_cliente=%s", id_cliente)

    return id_cliente, inserido

def valida_conversa(id_cliente, id_unidade, inserido, cursor):

    ## PRIMEIRA VEZ QUE O CLIENTE CONVERSA COM UMA UNIDADE SUPERA
    if inserido:
        id_conversa = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        logger.info("conversa_criada | id_conversa=%s estado=nova", id_conversa)
        return id_conversa, "nova"

    estado_conversa = buscar_estado_conversa(id_cliente, id_unidade, cursor)

    ## AQUI SIGNIFICA QUE É A PRIMEIRA CONVERSA DO CLIENTE COM A UNIDADE
    if not estado_conversa:
        id_conversa = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        logger.info("conversa_criada | id_conversa=%s estado=liberada_sem_historico", id_conversa)
        return id_conversa, "liberada"

    (
        id_conversa,
        id_etapa_atual,
        status_ativa,
        finalizou_em,
        estado,
    ) = estado_conversa

    ## AQUI O CLIENTE JÁ TEM UMA CONVERSA EM ANDAMENTO COM A UNIDADE
    if estado == "ativa":
        logger.info("conversa_ativa | id_conversa=%s", id_conversa)
        return id_conversa, estado

    ## O CLIENTE JÁ FINALIZOU UMA CONVERSA COM A UNIDADE NOS ÚLTIMOS 30 DIAS
    if estado == "bloqueada":
        logger.info(
            "conversa_bloqueada | id_conversa=%s id_etapa=%s finalizou_em=%s",
            id_conversa,
            id_etapa_atual,
            finalizou_em,
        )
        return id_conversa, estado

    ## O CLIENTE JÁ TEVE OUTRA CONVERSA COM A UNIDADE POREM FOI FINALIZADA A MAIS DE 30 DIAS
    if estado == "liberada":
        id_conversa_nova = inserindo_em_conversa_caso_seja_nova(
            id_cliente,
            id_unidade,
            cursor,
        )
        logger.info(
            "conversa_criada | id_conversa=%s conversa_anterior=%s estado=liberada",
            id_conversa_nova,
            id_conversa,
        )
        return id_conversa_nova, estado

    raise ValueError(
        f"Estado de conversa inválido: {estado} "
        f"(id_cliente={id_cliente}, id_unidade={id_unidade}, status_ativa={status_ativa})"
    )
