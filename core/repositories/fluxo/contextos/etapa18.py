"""Contexto da escolha de turno e da entrega ao comercial, por conversa/unidade."""


def buscar_contexto_etapa18(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT NULLIF(BTRIM(u.link_agendamento), ''), u.numero_comercial,
               u.nome_agente, u.genero, cl.nome, cl.idade,
               d.nome_dependente, d.idade, c.status_dependente, c.turno
        FROM chatbot.conversa c
        JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s AND c.id_unidade = %s;
        """,
        (id_conversa, id_unidade),
    )
    row = cursor.fetchone()
    if row is None:
        raise ValueError("Conversa/unidade ausente no contexto de sua reserva")
    if not isinstance(row[8], bool):
        raise ValueError("Destino de atendimento ausente no contexto de sua reserva")
    if not row[4] or (row[8] and not row[6]):
        raise ValueError("Nome do titular ou do dependente ausente")
    return dict(
        zip(
            (
                "link_agendamento_unidade",
                "numero_comercial_unidade",
                "nome_agente_unidade",
                "genero_agente_unidade",
                "nome_cliente",
                "idade_cliente",
                "nome_dependente",
                "idade_dependente",
                "status_dependente_reserva",
                "turno",
            ),
            row,
        )
    )
