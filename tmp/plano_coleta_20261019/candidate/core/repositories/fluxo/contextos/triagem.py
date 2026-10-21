import logging


logger = logging.getLogger("db.contexto_triagem")


def buscar_contexto_triagem(id_conversa, id_unidade, cursor):
    """Relê a pessoa atendida usada nas perguntas da triagem."""
    cursor.execute(
        """
        SELECT
            c.status_dependente,
            d.nome_dependente,
            CASE
                WHEN c.status_dependente IS TRUE THEN d.idade
                WHEN c.status_dependente IS FALSE THEN cl.idade
            END AS idade_pessoa_triagem
        FROM chatbot.conversa c
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
            "Contexto da triagem nao encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    (
        status_dependente,
        nome_dependente,
        idade_pessoa_triagem,
    ) = resultado

    logger.debug(
        "contexto_triagem_consultado | id_conversa=%s id_unidade=%s "
        "status_dependente_definido=%s dependente_nomeado=%s "
        "idade_pessoa_triagem_definida=%s",
        id_conversa,
        id_unidade,
        isinstance(status_dependente, bool),
        bool(nome_dependente),
        idade_pessoa_triagem is not None,
    )

    return {
        "status_dependente_contexto_triagem": status_dependente,
        "nome_dependente": nome_dependente,
        "idade_pessoa_triagem": idade_pessoa_triagem,
    }
