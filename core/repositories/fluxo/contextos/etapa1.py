def buscar_contexto_etapa1(id_unidade, cursor):
    cursor.execute(
        """
        SELECT nome
        FROM chatbot.unidade
        WHERE id_unidade = %s;
        """,
        (id_unidade,),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Unidade nao encontrada para montar a etapa 1 "
            f"(id_unidade={id_unidade})"
        )

    nome_unidade = str(resultado[0] or "").strip()

    if not nome_unidade:
        raise ValueError(
            "Unidade sem nome para montar a etapa 1 "
            f"(id_unidade={id_unidade})"
        )

    return {"nome_unidade": nome_unidade}
