"""Leitura do snapshot completo de uma conversa elegível ao Funil."""


def buscar_dados_lead_funil(id_conversa, cursor):
    """Retorna o snapshot da conversa, inclusive sua profissão histórica.

    ``cliente.profissao`` é mutável entre atendimentos e não participa do lead.
    """
    cursor.execute(
        """
        SELECT
            c.id_conversa,
            c.id_unidade,
            u.nome_unidade,
            COALESCE(c.status_dependente, FALSE) AS status_dependente,
            cl.nome AS nome_cliente,
            cl.waid_telefone AS telefone_cliente,
            cl.email AS email_cliente,
            cl.idade AS idade_cliente,
            c.profissao,
            d.nome_dependente,
            d.idade AS idade_dependente,
            triagem.respostas,
            coleta_email.conteudo_texto AS resposta_email_conversa,
            NULLIF(BTRIM(u.link_agendamento), '') AS link_agendamento,
            c.turno
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
                COALESCE(
                    JSONB_AGG(
                        JSONB_BUILD_OBJECT(
                            'id_etapa', r.id_etapa,
                            'resposta', r.resposta
                        )
                        ORDER BY r.id_etapa
                    ),
                    '[]'::JSONB
                ) AS respostas
            FROM chatbot.respostas_desafios r
            WHERE r.id_conversa = c.id_conversa
              AND r.id_etapa BETWEEN 12 AND 17
        ) AS triagem
        LEFT JOIN LATERAL (
            SELECT mensagem_cliente.conteudo_texto
            FROM chatbot.historico_mensagens mensagem_bot
            JOIN chatbot.historico_mensagens mensagem_cliente
              ON mensagem_cliente.id_conversa = mensagem_bot.id_conversa
             AND mensagem_cliente.quem_enviou = 'cliente'
             AND mensagem_cliente.id_etapa = 10
             AND mensagem_cliente.id_mensagem_fila
                 = mensagem_bot.id_mensagem_fila
             AND mensagem_cliente.id_hash_msg
                 = mensagem_bot.id_hash_cliente_origem
            WHERE mensagem_bot.id_conversa = c.id_conversa
              AND mensagem_bot.quem_enviou = 'bot'
              AND mensagem_bot.status_envio = 'sent'
              AND mensagem_bot.id_etapa = 11
            ORDER BY
                mensagem_bot.received_data_hora DESC,
                mensagem_bot.id_mensagem DESC
            LIMIT 1
        ) AS coleta_email ON TRUE
        WHERE c.id_conversa = %s
          AND etapa_atual.elegivel_funil = TRUE
          AND (
                (NULLIF(BTRIM(u.link_agendamento), '') IS NOT NULL
                 AND c.id_etapa_atual >= 20)
                OR (NULLIF(BTRIM(u.link_agendamento), '') IS NULL
                    AND (c.id_etapa_atual = 19 OR c.id_etapa_atual >= 21))
              )
          AND c.lead_no_funil IS NOT TRUE
        LIMIT 1;
        """,
        (id_conversa,),
    )

    resultado = cursor.fetchone()
    if resultado is None:
        return None

    return {
        "link_agendamento": resultado[13],
        "turno": resultado[14],
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
        "triagem_respostas": resultado[11],
        "resposta_email_conversa": (
            resultado[12] if len(resultado) > 12 else None
        ),
    }
