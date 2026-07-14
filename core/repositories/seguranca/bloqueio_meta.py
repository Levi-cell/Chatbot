import logging

from core.logging_config import short_value


logger = logging.getLogger("db.bloqueio_meta")


def registrar_evento_flood_banco(
    wa_id_cliente,
    phone_id_unidade,
    id_hash_msg,
    cursor,
):
    cursor.execute("""
        INSERT INTO chatbot.webhook_flood_evento (
            wa_id_cliente,
            phone_id_unidade,
            id_hash_msg,
            received_at
        )
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (id_hash_msg) DO NOTHING;
    """, (wa_id_cliente, phone_id_unidade, id_hash_msg))
    logger.debug(
        "flood_evento_insert | acao=registrar wa_id_cliente=%s phone_id_unidade=%s id_hash_msg=%s linhas=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        short_value(id_hash_msg),
        cursor.rowcount,
    )


def contar_eventos_flood_banco(
    wa_id_cliente,
    phone_id_unidade,
    cursor,
    janela_segundos=60,
):
    cursor.execute("""
        SELECT COUNT(*)
        FROM chatbot.webhook_flood_evento
        WHERE wa_id_cliente = %s
          AND phone_id_unidade = %s
          AND received_at >= NOW() - (%s * INTERVAL '1 second');
    """, (wa_id_cliente, phone_id_unidade, janela_segundos))

    resultado = cursor.fetchone()
    total = int(resultado[0]) if resultado else 0
    logger.debug(
        "flood_evento_count | acao=contar wa_id_cliente=%s phone_id_unidade=%s janela=%s total=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        janela_segundos,
        total,
    )
    return total


def limpar_eventos_flood_antigos(cursor, horas=2):
    cursor.execute("""
        DELETE FROM chatbot.webhook_flood_evento
        WHERE received_at < NOW() - (%s * INTERVAL '1 hour');
    """, (horas,))

    logger.debug(
        "flood_evento_limpeza | acao=limpar_antigos horas=%s linhas=%s",
        horas,
        cursor.rowcount,
    )
    return cursor.rowcount


def buscar_id_cliente_por_wa_id(wa_id_cliente, cursor):
    cursor.execute("""
        SELECT id_cliente
        FROM chatbot.cliente
        WHERE waid_telefone = %s
        LIMIT 1;
    """, (wa_id_cliente,))

    resultado = cursor.fetchone()
    id_cliente = resultado[0] if resultado else None
    logger.debug(
        "cliente_consulta | acao=buscar_por_wa_id wa_id_cliente=%s encontrado=%s",
        short_value(wa_id_cliente),
        bool(id_cliente),
    )
    return id_cliente


def buscar_unidade_bloqueio_por_phone_id(phone_id_unidade, cursor):
    cursor.execute("""
        SELECT id_unidade, phone_number_id
        FROM chatbot.unidade
        WHERE phone_number_id = %s
          AND status_pagamento = TRUE
        LIMIT 1;
    """, (phone_id_unidade,))

    resultado = cursor.fetchone()
    logger.debug(
        "unidade_consulta | acao=buscar_para_bloqueio phone_id_unidade=%s encontrada=%s",
        short_value(phone_id_unidade),
        bool(resultado),
    )
    return resultado


def registrar_cliente_bloqueado_meta_banco(
    id_cliente,
    wa_id_cliente,
    id_unidade,
    phone_id_unidade,
    cursor,
):
    cursor.execute("""
        INSERT INTO chatbot.cliente_bloqueado_meta (
            id_cliente,
            wa_id_cliente,
            id_unidade,
            phone_id_unidade
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (wa_id_cliente, id_unidade) DO UPDATE
        SET
            id_cliente = COALESCE(EXCLUDED.id_cliente, chatbot.cliente_bloqueado_meta.id_cliente),
            phone_id_unidade = EXCLUDED.phone_id_unidade
        RETURNING id_bloqueio;
    """, (
        id_cliente,
        wa_id_cliente,
        id_unidade,
        phone_id_unidade,
    ))

    resultado = cursor.fetchone()
    id_bloqueio = resultado[0] if resultado else None
    logger.debug(
        "bloqueio_meta_upsert | acao=registrar_bloqueio wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s id_bloqueio=%s linhas=%s",
        short_value(wa_id_cliente),
        id_cliente,
        id_unidade,
        short_value(phone_id_unidade),
        id_bloqueio,
        cursor.rowcount,
    )
    return id_bloqueio


def cliente_bloqueado_meta_existe_banco(
    wa_id_cliente,
    phone_id_unidade,
    cursor,
):
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM chatbot.cliente_bloqueado_meta
            WHERE wa_id_cliente = %s
              AND phone_id_unidade = %s
            LIMIT 1
        );
    """, (wa_id_cliente, phone_id_unidade))

    resultado = cursor.fetchone()
    existe = bool(resultado[0]) if resultado else False
    logger.debug(
        "bloqueio_meta_consulta | acao=existe wa_id_cliente=%s phone_id_unidade=%s existe=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        existe,
    )
    return existe


def listar_bloqueios_meta_banco_para_reconciliacao(cursor):
    cursor.execute("""
        SELECT
            cbm.id_bloqueio,
            cbm.wa_id_cliente,
            cbm.id_unidade,
            cbm.phone_id_unidade,
            u.nome
        FROM chatbot.cliente_bloqueado_meta cbm
        JOIN chatbot.unidade u
          ON u.id_unidade = cbm.id_unidade
        ORDER BY cbm.id_unidade, cbm.wa_id_cliente;
    """)

    resultados = cursor.fetchall()
    logger.debug(
        "bloqueio_meta_reconciliacao_consulta | acao=listar_banco total=%s",
        len(resultados),
    )
    return resultados
