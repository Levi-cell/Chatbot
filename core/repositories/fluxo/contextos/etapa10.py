import logging


logger = logging.getLogger("db.contexto_etapa10")


def buscar_contexto_etapa10(id_conversa, id_unidade, cursor):
    """Carrega a política de e-mail e a pessoa atendida no mesmo snapshot."""
    cursor.execute(
        """
        SELECT
            u.email_obrigatorio,
            c.status_dependente,
            cl.idade
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
            "Contexto da etapa 10 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    email_obrigatorio, status_dependente, idade_cliente = resultado

    if not isinstance(email_obrigatorio, bool):
        raise ValueError(
            "Configuração email_obrigatorio inválida "
            f"(id_unidade={id_unidade}, valor={email_obrigatorio!r})"
        )

    if not isinstance(status_dependente, bool):
        raise ValueError(
            "Etapa 10 sem destino de atendimento definido "
            f"(id_conversa={id_conversa}, valor={status_dependente!r})"
        )

    if (
        not status_dependente
        and (
            isinstance(idade_cliente, bool)
            or not isinstance(idade_cliente, int)
            or idade_cliente < 18
            or idade_cliente >= 100
        )
    ):
        raise ValueError(
            "Etapa 10 de titular sem idade válida persistida "
            f"(id_conversa={id_conversa}, idade={idade_cliente!r})"
        )

    logger.debug(
        "contexto_etapa10_consultado | id_conversa=%s id_unidade=%s "
        "email_obrigatorio=%s status_dependente=%s "
        "idade_cliente_definida=%s",
        id_conversa,
        id_unidade,
        email_obrigatorio,
        status_dependente,
        idade_cliente is not None,
    )

    return {
        "email_obrigatorio_unidade": email_obrigatorio,
        "status_dependente_contexto_email": status_dependente,
        "idade_cliente": idade_cliente,
    }
