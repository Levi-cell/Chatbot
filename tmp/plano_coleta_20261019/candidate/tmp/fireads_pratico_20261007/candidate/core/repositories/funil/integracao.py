def buscar_integracao_funil_por_unidade(id_unidade, cursor):
    """Busca a configuracao do Funil vinculada a uma unidade."""
    cursor.execute(
        """
        SELECT
            id_integracao_funil,
            id_unidade,
            nome_widget,
            data_salvamento_widget,
            codigo_widget,
            link_api_carrossel,
            codigo_canal_venda,
            widget_ativo,
            integracao_ativa,
            criado_em,
            atualizado_em
        FROM chatbot.integracao_funil_unidade
        WHERE id_unidade = %s
        LIMIT 1;
        """,
        (id_unidade,),
    )

    resultado = cursor.fetchone()

    if resultado is None:
        return None

    return {
        "id_integracao_funil": resultado[0],
        "id_unidade": resultado[1],
        "nome_widget": resultado[2],
        "data_salvamento_widget": resultado[3],
        "codigo_widget": resultado[4],
        "link_api_carrossel": resultado[5],
        "codigo_canal_venda": resultado[6],
        "widget_ativo": resultado[7],
        "integracao_ativa": resultado[8],
        "criado_em": resultado[9],
        "atualizado_em": resultado[10],
    }
