import logging


logger = logging.getLogger("db.contexto_triagem")


def buscar_contexto_triagem(id_conversa, id_unidade, cursor):
    """Carrega o nome do dependente usado nas perguntas da triagem."""
    cursor.execute(
        """
        SELECT d.nome_dependente
        FROM chatbot.conversa c
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

    nome_dependente = resultado[0]

    logger.debug(
        "contexto_triagem_consultado | id_conversa=%s id_unidade=%s "
        "dependente_nomeado=%s",
        id_conversa,
        id_unidade,
        bool(nome_dependente),
    )

    return {
        "nome_dependente": nome_dependente,
    }
