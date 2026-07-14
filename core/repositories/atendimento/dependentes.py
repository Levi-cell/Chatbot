import logging


logger = logging.getLogger("db.atendimento.dependentes")


def inserir_dependente_para_conversa(id_conversa, cursor):
    cursor.execute("""
        WITH conversa_cliente AS (
            SELECT id_cliente
            FROM chatbot.conversa
            WHERE id_conversa = %s
        ),
        existente AS (
            SELECT id_dependente, id_cliente, id_conversa
            FROM chatbot.dependente
            WHERE id_conversa = %s
            LIMIT 1
        ),
        inserido AS (
            INSERT INTO chatbot.dependente (
                id_cliente,
                id_conversa
            )
            SELECT
                id_cliente,
                %s
            FROM conversa_cliente
            WHERE NOT EXISTS (SELECT 1 FROM existente)
            RETURNING id_dependente, id_cliente, id_conversa
        )
        SELECT
            id_dependente,
            id_cliente,
            id_conversa,
            TRUE AS inserido
        FROM inserido

        UNION ALL

        SELECT
            id_dependente,
            id_cliente,
            id_conversa,
            FALSE AS inserido
        FROM existente

        LIMIT 1;
    """, (id_conversa, id_conversa, id_conversa))

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Dependente nao foi inserido nem encontrado "
            f"(id_conversa={id_conversa})"
        )

    logger.info(
        "dependente_insert_resultado | acao=vincular_dependente_conversa id_dependente=%s id_cliente=%s id_conversa=%s inserido=%s",
        resultado[0],
        resultado[1],
        resultado[2],
        bool(resultado[3]),
    )

    return {
        "id_dependente": resultado[0],
        "id_cliente": resultado[1],
        "id_conversa": resultado[2],
        "inserido": bool(resultado[3]),
    }


def atualizar_nome_dependente_por_conversa(id_conversa, nome, cursor):
    if not id_conversa:
        raise ValueError(
            "id_conversa nao informado para atualizar nome do dependente"
        )

    if not nome:
        raise ValueError("nome nao informado para atualizar dependente")

    cursor.execute(
        """
        UPDATE chatbot.dependente
        SET nome_dependente = %s
        WHERE id_conversa = %s;
        """,
        (nome, id_conversa),
    )

    logger.debug(
        "dependente_update | acao=atualizar_nome id_conversa=%s linhas=%s",
        id_conversa,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Dependente nao foi atualizado com nome "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_idade_dependente(id_conversa, idade, cursor):
    cursor.execute(
        """
        UPDATE chatbot.dependente
        SET idade = %s
        WHERE id_conversa = %s;
        """,
        (idade, id_conversa),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Dependente não atualizado com idade "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )


def excluir_dependente_da_conversa(id_conversa, cursor):
    cursor.execute(
        """
        DELETE FROM chatbot.dependente
        WHERE id_conversa = %s;
        """,
        (id_conversa,),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Dependente não excluído no encerramento "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )
