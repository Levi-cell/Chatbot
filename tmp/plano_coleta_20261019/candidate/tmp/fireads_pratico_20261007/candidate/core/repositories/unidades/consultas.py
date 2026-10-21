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
