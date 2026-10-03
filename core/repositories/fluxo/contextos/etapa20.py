import logging


logger = logging.getLogger("db.contexto_etapa20")


def buscar_contexto_etapa20(id_conversa, id_unidade, cursor):
    """Carrega link, cliente e participante para apresentar ou repetir sua reserva."""
    cursor.execute(
        """
        SELECT
            u.link_agendamento,
            cl.nome,
            c.status_dependente,
            d.nome_dependente
        FROM chatbot.conversa c
        JOIN chatbot.unidade u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 20 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    link_agendamento, nome_cliente, status_dependente, nome_dependente = resultado

    if not isinstance(status_dependente, bool):
        raise ValueError("Destino do atendimento ausente para sua reserva")
    if status_dependente and (
        not isinstance(nome_dependente, str) or not nome_dependente.strip()
    ):
        raise ValueError("Nome do dependente ausente para sua reserva")

    if not link_agendamento or not str(link_agendamento).strip():
        raise ValueError(
            "Unidade sem link de agendamento configurado " f"(id_unidade={id_unidade})"
        )

    if not nome_cliente or not str(nome_cliente).strip():
        raise ValueError(
            "Cliente sem nome para iniciar a pesquisa de satisfação "
            f"(id_conversa={id_conversa})"
        )

    logger.debug(
        "contexto_etapa20_consultado | id_conversa=%s id_unidade=%s "
        "link_agendamento_configurado=%s nome_cliente_configurado=%s",
        id_conversa,
        id_unidade,
        True,
        True,
    )

    return {
        "link_agendamento_unidade": str(link_agendamento).strip(),
        "nome_cliente": str(nome_cliente).strip(),
        "nome_dependente": nome_dependente.strip() if status_dependente else None,
    }
