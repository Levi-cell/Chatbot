def listar_conversas_pendentes_funil(
    id_etapa_final,
    cursor,
    *,
    limite=100,
):
    if not isinstance(id_etapa_final, int) or id_etapa_final <= 0:
        raise ValueError("id_etapa_final deve ser um inteiro positivo")

    if not isinstance(limite, int) or limite <= 0:
        raise ValueError("limite deve ser um inteiro positivo")

    cursor.execute(
        """
        SELECT id_conversa
        FROM chatbot.conversa
        WHERE id_etapa_atual = %s
          AND status_ativa = FALSE
          AND finalizou_em IS NOT NULL
          AND lead_no_funil IS NOT TRUE
        ORDER BY finalizou_em ASC, id_conversa ASC
        LIMIT %s;
        """,
        (id_etapa_final, limite),
    )

    return [linha[0] for linha in cursor.fetchall()]


def marcar_conversa_como_enviada_ao_funil(id_conversa, cursor):
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET lead_no_funil = TRUE
        WHERE id_conversa = %s
          AND lead_no_funil IS NOT TRUE
        RETURNING id_conversa;
        """,
        (id_conversa,),
    )

    return cursor.fetchone() is not None
