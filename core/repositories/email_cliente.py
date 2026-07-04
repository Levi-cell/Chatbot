def atualizar_email_cliente(id_cliente, email, cursor):
    cursor.execute(
        """
        UPDATE chatbot.cliente
        SET email = %s
        WHERE id_cliente = %s;
        """,
        (email, id_cliente),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Cliente não atualizado com email "
            f"(id_cliente={id_cliente}, linhas={cursor.rowcount})"
        )
