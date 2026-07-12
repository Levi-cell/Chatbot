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


def encerrar_conversa(id_conversa, cursor):
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            status_ativa = FALSE,
            finalizou_em = NOW(),
            processing = FALSE,
            processing_started_at = NULL
        WHERE id_conversa = %s
          AND status_ativa = TRUE
        RETURNING finalizou_em;
        """,
        (id_conversa,),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise RuntimeError(
            "Conversa não encerrada "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return resultado[0]
