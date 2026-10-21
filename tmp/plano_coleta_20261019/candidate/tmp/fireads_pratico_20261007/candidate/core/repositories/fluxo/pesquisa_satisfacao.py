import logging


logger = logging.getLogger("db.pesquisa_satisfacao")


def salvar_nota_satisfacao(id_conversa, nota, cursor):
    """Registra uma unica nota por conversa e rejeita retries divergentes."""
    if nota not in {1, 2, 3, 4, 5}:
        raise ValueError(
            "Nota de satisfacao fora do intervalo permitido "
            f"(id_conversa={id_conversa}, nota={nota})"
        )

    cursor.execute(
        """
        INSERT INTO chatbot.pesquisa_satisfacao (
            id_conversa,
            nota
        )
        VALUES (%s, %s)
        ON CONFLICT (id_conversa) DO NOTHING
        RETURNING id_pesquisa_satisfacao, nota, comentario;
        """,
        (id_conversa, nota),
    )
    resultado = cursor.fetchone()
    inserido = resultado is not None

    if resultado is None:
        resultado = _buscar_pesquisa_para_atualizacao(
            id_conversa,
            cursor,
        )

    if resultado is None:
        raise ValueError(
            "Pesquisa de satisfacao nao foi inserida nem encontrada "
            f"(id_conversa={id_conversa})"
        )

    nota_existente = resultado[1]

    if nota_existente is None:
        cursor.execute(
            """
            UPDATE chatbot.pesquisa_satisfacao
            SET nota = %s,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id_pesquisa_satisfacao = %s
            RETURNING id_pesquisa_satisfacao, nota, comentario;
            """,
            (nota, resultado[0]),
        )
        resultado = cursor.fetchone()
    elif nota_existente != nota:
        raise ValueError(
            "Nota divergente para a mesma pesquisa de satisfacao "
            f"(id_conversa={id_conversa}, existente={nota_existente}, "
            f"recebida={nota})"
        )

    logger.info(
        "nota_satisfacao_persistida | acao=registrar_nota "
        "id_pesquisa=%s id_conversa=%s nota=%s inserido=%s",
        resultado[0],
        id_conversa,
        nota,
        inserido,
    )

    return {
        "id_pesquisa_satisfacao": resultado[0],
        "nota_satisfacao": resultado[1],
        "inserido": inserido,
    }


def salvar_comentario_satisfacao(id_conversa, comentario, cursor):
    """Registra o comentario opcional sem sobrescrever um retry divergente."""
    comentario = _normalizar_comentario(comentario)

    cursor.execute(
        """
        INSERT INTO chatbot.pesquisa_satisfacao (
            id_conversa,
            comentario
        )
        VALUES (%s, %s)
        ON CONFLICT (id_conversa) DO NOTHING
        RETURNING id_pesquisa_satisfacao, nota, comentario;
        """,
        (id_conversa, comentario),
    )
    resultado = cursor.fetchone()
    inserido = resultado is not None

    if resultado is None:
        resultado = _buscar_pesquisa_para_atualizacao(
            id_conversa,
            cursor,
        )

    if resultado is None:
        raise ValueError(
            "Pesquisa de satisfacao nao foi inserida nem encontrada "
            f"(id_conversa={id_conversa})"
        )

    comentario_existente = resultado[2]

    if comentario_existente is None and comentario is not None:
        cursor.execute(
            """
            UPDATE chatbot.pesquisa_satisfacao
            SET comentario = %s,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id_pesquisa_satisfacao = %s
            RETURNING id_pesquisa_satisfacao, nota, comentario;
            """,
            (comentario, resultado[0]),
        )
        resultado = cursor.fetchone()
    elif comentario_existente != comentario:
        raise ValueError(
            "Comentario divergente para a mesma pesquisa de satisfacao "
            f"(id_conversa={id_conversa})"
        )

    logger.info(
        "comentario_satisfacao_persistido | acao=registrar_comentario "
        "id_pesquisa=%s id_conversa=%s comentario_preenchido=%s "
        "inserido=%s",
        resultado[0],
        id_conversa,
        bool(comentario),
        inserido,
    )

    return {
        "id_pesquisa_satisfacao": resultado[0],
        "comentario_satisfacao": resultado[2],
        "inserido": inserido,
    }


def _buscar_pesquisa_para_atualizacao(id_conversa, cursor):
    cursor.execute(
        """
        SELECT id_pesquisa_satisfacao, nota, comentario
        FROM chatbot.pesquisa_satisfacao
        WHERE id_conversa = %s
        FOR UPDATE;
        """,
        (id_conversa,),
    )
    return cursor.fetchone()


def _normalizar_comentario(comentario):
    if comentario is None:
        return None

    comentario = str(comentario).strip()
    return comentario or None
