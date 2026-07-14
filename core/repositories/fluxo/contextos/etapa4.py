import logging


logger = logging.getLogger("db.contexto_etapa4")


def buscar_contexto_etapa4(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            u.numero_comercial,
            u.bpa_ativo,
            cl.nome,
            d.nome_dependente
        FROM chatbot.unidade u
        JOIN chatbot.conversa c
          ON c.id_conversa = %s
         AND c.id_unidade = u.id_unidade
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE u.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 4 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    (
        numero_comercial,
        bpa_ativo,
        nome_cliente,
        nome_dependente,
    ) = resultado

    logger.debug(
        "contexto_etapa4_consultado | id_conversa=%s id_unidade=%s "
        "numero_comercial_configurado=%s bpa_ativo=%s "
        "cliente_nomeado=%s dependente_nomeado=%s",
        id_conversa,
        id_unidade,
        bool(numero_comercial),
        bool(bpa_ativo),
        bool(nome_cliente),
        bool(nome_dependente),
    )

    return {
        "numero_comercial_unidade": numero_comercial,
        "bpa_ativo_unidade": bool(bpa_ativo),
        "nome_cliente": nome_cliente,
        "nome_dependente": nome_dependente,
    }
