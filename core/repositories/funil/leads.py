"""Leitura do snapshot completo de uma conversa elegível ao Funil."""


def buscar_dados_lead_funil(id_conversa, cursor):
    """Retorna cliente, profissão, dependente e resumo da triagem."""
    cursor.execute(
        """
        SELECT
            c.id_conversa,
            c.id_unidade,
            u.nome AS nome_unidade,
            COALESCE(c.status_dependente, FALSE) AS status_dependente,
            cl.nome AS nome_cliente,
            cl.waid_telefone AS telefone_cliente,
            cl.email AS email_cliente,
            cl.idade AS idade_cliente,
            c.profissao,
            d.nome_dependente,
            d.idade AS idade_dependente,
            triagem.total,
            triagem.nunca,
            triagem.as_vezes,
            triagem.frequentemente,
            triagem.desconhecida
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.etapa etapa_atual
          ON etapa_atual.id_etapa = c.id_etapa_atual
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        CROSS JOIN LATERAL (
            SELECT
                COUNT(*)::INT AS total,
                COUNT(*) FILTER (
                    WHERE LOWER(BTRIM(r.resposta)) = 'nunca'
                )::INT AS nunca,
                COUNT(*) FILTER (
                    WHERE LOWER(BTRIM(r.resposta)) IN ('às vezes', 'as vezes')
                )::INT AS as_vezes,
                COUNT(*) FILTER (
                    WHERE LOWER(BTRIM(r.resposta)) = 'frequentemente'
                )::INT AS frequentemente,
                COUNT(*) FILTER (
                    WHERE LOWER(BTRIM(r.resposta)) NOT IN (
                        'nunca',
                        'às vezes',
                        'as vezes',
                        'frequentemente'
                    )
                )::INT AS desconhecida
            FROM chatbot.respostas_desafios r
            JOIN chatbot.etapa etapa_triagem
              ON etapa_triagem.id_etapa = r.id_etapa
            WHERE r.id_conversa = c.id_conversa
              AND etapa_triagem.nome_etapa
                  LIKE 'Triagem cognitiva - pergunta %%'
        ) AS triagem
        WHERE c.id_conversa = %s
          AND etapa_atual.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        LIMIT 1;
        """,
        (id_conversa,),
    )

    resultado = cursor.fetchone()
    if resultado is None:
        return None

    return {
        "id_conversa": resultado[0],
        "id_unidade": resultado[1],
        "nome_unidade": resultado[2],
        "status_dependente": bool(resultado[3]),
        "nome_cliente": resultado[4],
        "telefone_cliente": resultado[5],
        "email_cliente": resultado[6],
        "idade_cliente": resultado[7],
        "profissao": resultado[8],
        "nome_dependente": resultado[9],
        "idade_dependente": resultado[10],
        "triagem_total": resultado[11],
        "triagem_nunca": resultado[12],
        "triagem_as_vezes": resultado[13],
        "triagem_frequentemente": resultado[14],
        "triagem_desconhecida": resultado[15],
    }
