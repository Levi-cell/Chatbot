def atualizar_idade_cliente(id_cliente, idade, cursor):
    cursor.execute(
        """
        UPDATE chatbot.cliente
        SET idade = %s
        WHERE id_cliente = %s;
        """,
        (idade, id_cliente),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Cliente não atualizado com idade "
            f"(id_cliente={id_cliente}, linhas={cursor.rowcount})"
        )


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
