import logging

from core.logging_config import short_value


logger = logging.getLogger("db.turno_cliente")


def avaliar_turno_cliente_para_fila(
    cursor,
    cliente_telefone,
    id_phone_unidade,
    usar_lock=False,
):
    if not cliente_telefone or not id_phone_unidade:
        logger.warning(
            "turno_cliente_invalido | motivo=dados_invalidos acao=bloquear_turno cliente=%s phone_number_id=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
        )
        return {
            "pode_enfileirar": False,
            "motivo": "dados_invalidos",
        }

    if usar_lock:
        adquirir_lock_turno_cliente(cursor, cliente_telefone, id_phone_unidade)

    if fila_tem_mensagem_aberta_turno(
        cursor,
        cliente_telefone,
        id_phone_unidade,
    ):
        logger.info(
            "turno_cliente_bloqueado | motivo=fila_aberta acao=nao_enfileirar cliente=%s phone_number_id=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
        )
        return {
            "pode_enfileirar": False,
            "motivo": "fila_aberta",
        }

    logger.debug(
        "turno_cliente_liberado | motivo=sem_fila_aberta acao=enfileirar cliente=%s phone_number_id=%s",
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
    )
    return {
        "pode_enfileirar": True,
        "motivo": "sem_fila_aberta",
    }


def adquirir_lock_turno_cliente(cursor, cliente_telefone, id_phone_unidade):
    cursor.execute("""
        SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s));
    """, (str(id_phone_unidade), str(cliente_telefone)))

    logger.debug(
        "turno_cliente_lock | acao=advisory_xact_lock cliente=%s phone_number_id=%s",
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
    )


def fila_tem_mensagem_aberta_turno(cursor, cliente_telefone, id_phone_unidade):
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM chatbot.fila_mensagens
            WHERE cliente_telefone = %s
              AND id_phone_unidade = %s
              AND status IN ('pending', 'processing')
            LIMIT 1
        );
    """, (cliente_telefone, id_phone_unidade))

    resultado = bool(cursor.fetchone()[0])
    logger.debug(
        "turno_cliente_fila_consultada | acao=verificar_aberta cliente=%s phone_number_id=%s existe=%s",
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
        resultado,
    )
    return resultado
