import logging


logger = logging.getLogger("db.unidades.consultas")


def pegar_unidades(cursor):
    cursor.execute("""
        SELECT phone_number_id, id_unidade
        FROM chatbot.unidade
        WHERE status_pagamento = TRUE
    """)

    resultado = {row[0]: row[1] for row in cursor.fetchall()}

    logger.debug("unidades_consultadas | total=%s", len(resultado))

    return resultado


def buscar_unidades_para_listagem_bloqueios(cursor):
    cursor.execute("""
        SELECT id_unidade, nome, phone_number_id
        FROM chatbot.unidade
        WHERE phone_number_id IS NOT NULL
          AND phone_number_id <> ''
        ORDER BY id_unidade;
    """)

    return cursor.fetchall()


def buscar_unidades_para_reconciliacao_meta(cursor):
    cursor.execute("""
        SELECT id_unidade, nome, waba_id, phone_number_id
        FROM chatbot.unidade
        WHERE waba_id IS NOT NULL
          AND waba_id <> ''
          AND phone_number_id IS NOT NULL
          AND phone_number_id <> ''
        ORDER BY id_unidade;
    """)

    return cursor.fetchall()


def buscar_id_unidade_por_phone_id(phone_number_id, cursor):
    cursor.execute("""
        SELECT id_unidade
        FROM chatbot.unidade
        WHERE phone_number_id = %s
          AND status_pagamento = TRUE
    """, (phone_number_id,))

    resultado = cursor.fetchone()
    logger.debug(
        "unidade_consulta | acao=buscar_por_phone phone_number_id=%s encontrada=%s",
        phone_number_id,
        bool(resultado),
    )
    return resultado[0] if resultado else None
