import logging


logger = logging.getLogger("db.contexto_etapa9")


def buscar_contexto_etapa9(id_conversa, id_unidade, cursor):
    """
    Carrega os dados usados na entrada e nas respostas da etapa 9.

    A etapa 8 usa o mesmo contexto para construir a entrada real da etapa 9.
    """
    cursor.execute(
        """
        SELECT
            cl.nome,
            d.nome_dependente,
            u.link_instagram
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u
          ON u.id_unidade = c.id_unidade
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s
          AND c.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 9 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    nome_titular, nome_dependente, link_instagram = resultado

    logger.debug(
        "contexto_etapa9_consultado | id_conversa=%s id_unidade=%s "
        "cliente_nomeado=%s dependente_nomeado=%s "
        "instagram_configurado=%s",
        id_conversa,
        id_unidade,
        bool(nome_titular),
        bool(nome_dependente),
        bool(link_instagram),
    )

    return {
        "nome_titular": nome_titular,
        "nome_dependente": nome_dependente,
        "link_instagram_unidade": link_instagram,
    }
