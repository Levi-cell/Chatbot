"""Endereço público da unidade; leitura transacional, sem cache derivado."""


def buscar_localizacao_unidade(id_unidade, cursor):
    cursor.execute(
        "SELECT e.endereco, u.horarios_funcionamento "
        "FROM chatbot.unidade u "
        "LEFT JOIN chatbot.endereco_unidade e USING (id_unidade) "
        "WHERE u.id_unidade = %s",
        (id_unidade,),
    )
    row = cursor.fetchone()
    return {
        'endereco_unidade': row[0] if row else None,
        'horarios_funcionamento': row[1] if row else None,
    }
