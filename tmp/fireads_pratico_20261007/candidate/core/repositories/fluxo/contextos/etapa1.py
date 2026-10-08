def buscar_contexto_etapa1(id_unidade, cursor):
    cursor.execute(
        """
        SELECT nome_unidade, nome_agente, genero
        FROM chatbot.unidade_atendimento
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
    nome_agente = str(resultado[1] or "").strip()
    genero = str(resultado[2] or "").strip()

    if not nome_unidade:
        raise ValueError(
            "Unidade sem nome_unidade para montar a etapa 1 "
            f"(id_unidade={id_unidade})"
        )

    if not nome_agente:
        raise ValueError(
            "Unidade sem nome_agente para montar a etapa 1 "
            f"(id_unidade={id_unidade})"
        )

    if genero not in {"masculino", "feminino"}:
        raise ValueError(
            "Unidade com genero de agente invalido para montar a etapa 1 "
            f"(id_unidade={id_unidade}, genero={genero!r})"
        )

    return {
        "nome_unidade": nome_unidade,
        "nome_agente": nome_agente,
        "genero": genero,
    }
