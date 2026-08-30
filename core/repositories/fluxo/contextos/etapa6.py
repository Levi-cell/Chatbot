import logging


logger = logging.getLogger("db.contexto_etapa6")


def buscar_contexto_etapa6(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            u.numero_comercial,
            u.bpa_ativo,
            u.suporte_idoso,
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
            "Contexto da etapa 6 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    (
        numero_comercial,
        bpa_ativo,
        suporte_idoso,
        nome_cliente,
        nome_dependente,
    ) = resultado

    logger.debug(
        "contexto_etapa6_consultado | id_conversa=%s id_unidade=%s "
        "numero_comercial_configurado=%s bpa_ativo=%s suporte_idoso=%s "
        "cliente_nomeado=%s dependente_nomeado=%s",
        id_conversa,
        id_unidade,
        bool(numero_comercial),
        bool(bpa_ativo),
        suporte_idoso,
        bool(nome_cliente),
        bool(nome_dependente),
    )

    if not isinstance(suporte_idoso, bool):
        raise ValueError(
            "Configuração suporte_idoso inválida "
            f"(id_unidade={id_unidade}, valor={suporte_idoso!r})"
        )

    return {
        "numero_comercial_unidade": numero_comercial,
        "bpa_ativo_unidade": bool(bpa_ativo),
        "suporte_idoso_unidade": suporte_idoso,
        "nome_cliente": nome_cliente,
        "nome_dependente": nome_dependente,
    }
