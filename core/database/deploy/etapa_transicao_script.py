import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.etapa_transicao")


TRANSICOES_INICIAIS = (
    (1, "nome_cliente_valido", 2),
    (2, "para_mim", 4),
    (2, "para_outra_pessoa", 3),
    (3, "nome_dependente_valido", 4),
    (4, "idade_valida", 5),
    (5, "oferta_aceita", 8),
    (5, "oferta_adiada", 6),
    (6, "cliente_retornou", 7),
    (7, "retorno_confirmado", 8),
    (7, "retorno_adiado", 6),
    (8, "email_valido", 9),
    (9, "triagem_iniciada", 10),
)

# O mapa declara o fluxo completo conhecido. Resolvers e senders continuam
# responsáveis por produzir somente eventos já implementados na aplicação.


def criar_e_povoar_transicoes_etapa():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

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

        # O deploy mantém uma whitelist exata e IDs previsíveis. Transições
        # antigas não sobrevivem e a sequência sempre recomeça em 1.
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

        conn.commit()
        logger.info(
            "etapa_transicao_setup_ok | acao=sincronizar_mapa quantidade=%s",
            len(TRANSICOES_INICIAIS),
        )

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "etapa_transicao_setup_erro | acao=sincronizar_mapa erro=%s",
            erro,
        )
        raise

    finally:
        if conn:
            conn.close()
