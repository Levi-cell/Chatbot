import logging

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


logger = logging.getLogger("db.contexto_etapa6")


def buscar_contexto_etapa6(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            ac.numero_comercial,
            ac.bpa_ativo,
            ac.idade_minima_suporte,
            cl.nome,
            d.nome_dependente,
            ac.nome_agente,
            ac.genero,
            u.nome_unidade
        FROM chatbot.unidade u
        JOIN chatbot.atendimento_customizado ac ON ac.id_unidade = u.id_unidade
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
        nome_titular,
        nome_dependente,
        nome_agente,
        genero_agente,
        nome_unidade,
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
        bool(nome_titular),
        bool(nome_dependente),
    )

    validar_idade_minima_suporte(idade_minima_suporte)

    return {
        "numero_comercial_unidade": numero_comercial,
        "bpa_ativo_unidade": bool(bpa_ativo),
        "idade_minima_suporte": idade_minima_suporte,
        "nome_titular": nome_titular,
        "nome_dependente": nome_dependente,
        "nome_agente": nome_agente,
        "genero_agente_unidade": genero_agente,
        "nome_unidade": nome_unidade,
    }
