import logging


logger = logging.getLogger("db.unidades.consultas")


class UnidadeDesativada(Exception):
    """Suspensão administrativa; não é falha nem motivo para apagar a fila."""


def unidade_habilitada(id_unidade, cursor):
    """Leitura atual para lotes já carregados antes de uma desativação."""
    cursor.execute(
        "SELECT status_pagamento IS TRUE FROM chatbot.unidade WHERE id_unidade = %s",
        (id_unidade,),
    )
    row = cursor.fetchone()
    return bool(row and row[0])


def exigir_unidade_habilitada_por_phone_id(phone_number_id, cursor):
    """Não confiar em um cache positivo antes de iniciar ou enviar o atendimento."""
    cursor.execute(
        "SELECT status_pagamento IS TRUE FROM chatbot.unidade WHERE phone_number_id = %s",
        (phone_number_id,),
    )
    row = cursor.fetchone()
    if row is not None and not row[0]:
        raise UnidadeDesativada("Unidade desativada por status_pagamento")


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
