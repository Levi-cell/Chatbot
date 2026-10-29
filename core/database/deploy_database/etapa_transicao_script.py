import logging

from core.database.deploy_database.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.etapa_transicao")


TRANSICOES_INICIAIS = (
    (1, "nome_cliente_valido", 2),
    (2, "destino_atendimento_definido", 3),
    (3, "destino_atendimento_confirmado", 4),
    # A profissão é obrigatória para titular e dependente. Somente depois dela
    # o status salvo escolhe nome do dependente (5) ou idade do titular (6).
    (4, "profissao_dependente_valida", 5),
    (4, "profissao_titular_valida", 6),
    (5, "nome_dependente_valido", 6),
    (6, "idade_valida", 7),
    (7, "oferta_aceita", 10),
    (7, "oferta_aceita_email_fireads", 11),
    (7, "oferta_adiada", 8),
    (8, "cliente_retornou", 9),
    (9, "retorno_confirmado", 10),
    (9, "retorno_confirmado_email_fireads", 11),
    (9, "retorno_adiado", 8),
    (10, "email_valido", 11),
    (11, "triagem_iniciada", 12),
    (12, "triagem_pergunta_1_respondida", 13),
    (13, "triagem_pergunta_2_respondida", 14),
    (14, "triagem_pergunta_3_respondida", 15),
    (15, "triagem_pergunta_4_respondida", 16),
    (16, "triagem_pergunta_5_respondida", 17),
    (17, "triagem_pergunta_6_respondida", 20),
    (17, "triagem_concluida_sem_link", 18),
    (18, "turno_escolhido", 19),
    (19, "avaliacao_solicitada", 21),
    (20, "agendamento_confirmado", 21),
    (21, "satisfacao_avaliada", 22),
    (22, "comentario_satisfacao_aceito", 23),
    (22, "comentario_satisfacao_recusado", 24),
    (23, "comentario_satisfacao_recebido", 24),
    # Arestas acrescentadas pelas migrações de coleta. Mantidas no fim para
    # conservar os IDs históricos também na reexecução do setup.
    (1, "nome_cliente_valido_destino_coletado", 4),
    (17, "triagem_concluida_turno_coletado", 19),
)

# O mapa declara o fluxo completo conhecido. Resolvers e senders continuam
# responsáveis por produzir somente eventos já implementados na aplicação.


def criar_e_povoar_transicoes_etapa(*, incluir_coleta=True):
    # O bootstrap passa primeiro pelo contrato histórico de 30 arestas.
    # Depois das migrações, sincroniza o catálogo atual completo.
    eventos_coleta = {'nome_cliente_valido_destino_coletado', 'triagem_concluida_turno_coletado'}
    transicoes = tuple(
        t for t in TRANSICOES_INICIAIS if incluir_coleta or t[1] not in eventos_coleta
    )
    with transacao_deploy("sincronizar_mapa_transicoes", logger) as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chatbot.etapa_transicao (
                id_transicao SERIAL PRIMARY KEY,
                id_etapa_origem INT NOT NULL,
                evento VARCHAR(100) NOT NULL,
                id_etapa_destino INT NOT NULL,

                CONSTRAINT etapa_transicao_origem_fkey
                    FOREIGN KEY (id_etapa_origem)
                    REFERENCES chatbot.etapa(id_etapa)
                    ON DELETE RESTRICT,

                CONSTRAINT etapa_transicao_destino_fkey
                    FOREIGN KEY (id_etapa_destino)
                    REFERENCES chatbot.etapa(id_etapa)
                    ON DELETE RESTRICT,

                CONSTRAINT etapa_transicao_sem_auto_salto
                    CHECK (id_etapa_origem <> id_etapa_destino),

                CONSTRAINT etapa_transicao_origem_evento_unique
                    UNIQUE (id_etapa_origem, evento),

                CONSTRAINT etapa_transicao_origem_destino_unique
                    UNIQUE (id_etapa_origem, id_etapa_destino)
            );
            """
        )

        # Preserva IDs existentes (inclusive os atribuídos pelas migrações).
        # Na fase histórica, as arestas atuais de coleta já existentes ficam
        # intactas; migrações marcadas como aplicadas não as recriariam.
        placeholders = ','.join('(%s,%s)' for _ in TRANSICOES_INICIAIS)
        cursor.execute(
            'DELETE FROM chatbot.etapa_transicao '
            f'WHERE (id_etapa_origem,evento) NOT IN (VALUES {placeholders})',
            tuple(valor for origem, evento, _ in TRANSICOES_INICIAIS for valor in (origem, evento)),
        )

        cursor.executemany(
            """
            INSERT INTO chatbot.etapa_transicao (
                id_etapa_origem,
                evento,
                id_etapa_destino
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (id_etapa_origem,evento) DO UPDATE
            SET id_etapa_destino=EXCLUDED.id_etapa_destino;
            """,
            transicoes,
        )

    logger.info(
        "etapa_transicao_setup_ok | acao=sincronizar_mapa quantidade=%s",
        len(transicoes),
    )
