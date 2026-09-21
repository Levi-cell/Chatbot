import logging

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


logger = logging.getLogger("db.contexto_etapa6")


def buscar_contexto_etapa6(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            u.numero_comercial,
            u.bpa_ativo,
            u.idade_minima_suporte,
            cl.nome,
            d.nome_dependente,
            u.nome_agente,
            u.genero
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
        idade_minima_suporte,
        nome_cliente,
        nome_dependente,
        nome_agente,
        genero_agente,
    ) = resultado

    logger.debug(
        "contexto_etapa6_consultado | id_conversa=%s id_unidade=%s "
        "numero_comercial_configurado=%s bpa_ativo=%s idade_minima_suporte=%s "
        "cliente_nomeado=%s dependente_nomeado=%s",
        id_conversa,
        id_unidade,
        bool(numero_comercial),
        bool(bpa_ativo),
        idade_minima_suporte,
        bool(nome_cliente),
        bool(nome_dependente),
    )

    validar_idade_minima_suporte(idade_minima_suporte)

    return {
        "numero_comercial_unidade": numero_comercial,
        "bpa_ativo_unidade": bool(bpa_ativo),
        "idade_minima_suporte": idade_minima_suporte,
        "nome_cliente": nome_cliente,
        "nome_dependente": nome_dependente,
        "nome_agente_unidade": nome_agente,
        "genero_agente_unidade": genero_agente,
    }
