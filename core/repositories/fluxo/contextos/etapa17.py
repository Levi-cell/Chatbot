import logging


logger = logging.getLogger("db.contexto_etapa17")


def buscar_contexto_etapa17(id_conversa, id_unidade, cursor):
    """Carrega o agendamento e o cliente vinculados à conversa."""
    cursor.execute(
        """
        SELECT
            u.link_agendamento,
            cl.nome
        FROM chatbot.conversa c
        JOIN chatbot.unidade u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 17 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    link_agendamento, nome_cliente = resultado

    if not link_agendamento or not str(link_agendamento).strip():
        raise ValueError(
            "Unidade sem link de agendamento configurado "
            f"(id_unidade={id_unidade})"
        )

    if not nome_cliente or not str(nome_cliente).strip():
        raise ValueError(
            "Cliente sem nome para iniciar a pesquisa de satisfação "
            f"(id_conversa={id_conversa})"
        )

    logger.debug(
        "contexto_etapa17_consultado | id_conversa=%s id_unidade=%s "
        "link_agendamento_configurado=%s nome_cliente_configurado=%s",
        id_conversa,
        id_unidade,
        True,
        True,
    )

    return {
        "link_agendamento_unidade": str(link_agendamento).strip(),
        "nome_cliente": str(nome_cliente).strip(),
    }
