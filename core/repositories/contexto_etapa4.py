import logging


logger = logging.getLogger("db.contexto_etapa4")


def buscar_contexto_etapa4(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            u.numero_comercial,
            d.nome_dependente
        FROM chatbot.unidade u
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = %s
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

    numero_comercial, nome_dependente = resultado

    logger.debug(
        "contexto_etapa4_consultado | id_conversa=%s id_unidade=%s "
        "numero_comercial_configurado=%s dependente_nomeado=%s",
        id_conversa,
        id_unidade,
        bool(numero_comercial),
        bool(nome_dependente),
    )

    return {
        "numero_comercial_unidade": numero_comercial,
        "nome_dependente": nome_dependente,
    }
