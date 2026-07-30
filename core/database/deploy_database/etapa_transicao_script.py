import logging

from core.database.deploy_database.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.etapa_transicao")


TRANSICOES_INICIAIS = (
    (1, "nome_cliente_valido", 2),
    (2, "destino_atendimento_definido", 3),
    (3, "profissao_dependente_valida", 4),
    (3, "profissao_titular_valida", 5),
    (4, "nome_dependente_valido", 5),
    (5, "idade_valida", 6),
    (6, "oferta_aceita", 9),
    (6, "oferta_adiada", 7),
    (7, "cliente_retornou", 8),
    (8, "retorno_confirmado", 9),
    (8, "retorno_adiado", 7),
    (9, "email_valido", 10),
    (10, "triagem_iniciada", 11),
    (11, "triagem_pergunta_1_respondida", 12),
    (12, "triagem_pergunta_2_respondida", 13),
    (13, "triagem_pergunta_3_respondida", 14),
    (14, "triagem_pergunta_4_respondida", 15),
    (15, "triagem_pergunta_5_respondida", 16),
    (16, "triagem_pergunta_6_respondida", 17),
    (17, "agendamento_confirmado", 18),
    (18, "satisfacao_avaliada", 19),
    (19, "comentario_satisfacao_aceito", 20),
    (19, "comentario_satisfacao_recusado", 21),
    (20, "comentario_satisfacao_recebido", 21),
)

# O mapa declara o fluxo completo conhecido. Resolvers e senders continuam
# responsáveis por produzir somente eventos já implementados na aplicação.


def criar_e_povoar_transicoes_etapa():
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

        # Isto sincroniza dados de catálogo, não migra schema. A whitelist
        # precisa ser exata e manter IDs previsíveis após uma reexecução.
        cursor.execute(
            "TRUNCATE TABLE chatbot.etapa_transicao RESTART IDENTITY;"
        )

        cursor.executemany(
            """
            INSERT INTO chatbot.etapa_transicao (
                id_etapa_origem,
                evento,
                id_etapa_destino
            )
            VALUES (%s, %s, %s);
            """,
            TRANSICOES_INICIAIS,
        )

    logger.info(
        "etapa_transicao_setup_ok | acao=sincronizar_mapa quantidade=%s",
        len(TRANSICOES_INICIAIS),
    )
