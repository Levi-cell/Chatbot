def listar_conversas_pendentes_funil(
    cursor,
    *,
    limite=100,
):
    if not isinstance(limite, int) or limite <= 0:
        raise ValueError("limite deve ser um inteiro positivo")

    cursor.execute(
        """
        SELECT c.id_conversa
        FROM chatbot.conversa c
        JOIN chatbot.etapa e
          ON e.id_etapa = c.id_etapa_atual
        WHERE c.status_ativa = FALSE
          AND c.finalizou_em IS NOT NULL
          AND e.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        ORDER BY c.finalizou_em ASC, c.id_conversa ASC
        LIMIT %s;
        """,
        (limite,),
    )

    return [linha[0] for linha in cursor.fetchall()]


def marcar_conversa_como_enviada_ao_funil(id_conversa, cursor):
    cursor.execute(
        """
        UPDATE chatbot.conversa AS c
        SET lead_no_funil = TRUE
        FROM chatbot.etapa AS e
        WHERE c.id_conversa = %s
          AND e.id_etapa = c.id_etapa_atual
          AND c.status_ativa = FALSE
          AND c.finalizou_em IS NOT NULL
          AND e.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        RETURNING c.id_conversa;
        """,
        (id_conversa,),
    )

    return cursor.fetchone() is not None
