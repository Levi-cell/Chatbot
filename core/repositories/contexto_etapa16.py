import logging


logger = logging.getLogger("db.contexto_etapa16")


def buscar_contexto_etapa16(id_conversa, id_unidade, cursor):
    """Carrega o link de agendamento da unidade vinculada à conversa."""
    cursor.execute(
        """
        SELECT u.link_agendamento
        FROM chatbot.conversa c
        JOIN chatbot.unidade u
          ON u.id_unidade = c.id_unidade
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 16 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    link_agendamento = resultado[0]

    if not link_agendamento or not str(link_agendamento).strip():
        raise ValueError(
            "Unidade sem link de agendamento configurado "
            f"(id_unidade={id_unidade})"
        )

    logger.debug(
        "contexto_etapa16_consultado | id_conversa=%s id_unidade=%s "
        "link_agendamento_configurado=%s",
        id_conversa,
        id_unidade,
        True,
    )

    return {
        "link_agendamento_unidade": str(link_agendamento).strip(),
    }
