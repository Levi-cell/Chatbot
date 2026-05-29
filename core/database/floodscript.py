import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.flood_setup")


def criar_tabelas_bloqueio_flood():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SET TIME ZONE 'America/Sao_Paulo';

            CREATE UNIQUE INDEX IF NOT EXISTS uq_unidade_id_phone_number_id
            ON chatbot.unidade (id_unidade, phone_number_id);

            CREATE TABLE IF NOT EXISTS chatbot.cliente_bloqueado_meta (
                id_bloqueio SERIAL PRIMARY KEY,
                id_cliente INT NULL,
                wa_id_cliente VARCHAR(50) NOT NULL,
                id_unidade INT NOT NULL,
                phone_id_unidade VARCHAR(100) NOT NULL,

                CONSTRAINT fk_cliente_bloqueado_meta_cliente
                    FOREIGN KEY (id_cliente)
                    REFERENCES chatbot.cliente(id_cliente)
                    ON DELETE SET NULL,

                CONSTRAINT fk_cliente_bloqueado_meta_unidade_phone
                    FOREIGN KEY (id_unidade, phone_id_unidade)
                    REFERENCES chatbot.unidade(id_unidade, phone_number_id)
                    ON UPDATE CASCADE
                    ON DELETE CASCADE,

                CONSTRAINT uq_cliente_bloqueado_meta_wa_unidade
                    UNIQUE (wa_id_cliente, id_unidade)
            );

            CREATE INDEX IF NOT EXISTS idx_cliente_bloqueado_meta_id_cliente
            ON chatbot.cliente_bloqueado_meta (id_cliente)
            WHERE id_cliente IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_cliente_bloqueado_meta_wa_id
            ON chatbot.cliente_bloqueado_meta (wa_id_cliente);

            CREATE INDEX IF NOT EXISTS idx_cliente_bloqueado_meta_id_unidade
            ON chatbot.cliente_bloqueado_meta (id_unidade);

            CREATE INDEX IF NOT EXISTS idx_cliente_bloqueado_meta_phone_id
            ON chatbot.cliente_bloqueado_meta (phone_id_unidade);

            CREATE TABLE IF NOT EXISTS chatbot.webhook_flood_evento (
                id_evento BIGSERIAL PRIMARY KEY,
                wa_id_cliente VARCHAR(50) NOT NULL,
                phone_id_unidade VARCHAR(100) NOT NULL,
                id_hash_msg VARCHAR(255) NOT NULL UNIQUE,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_webhook_flood_evento_janela
            ON chatbot.webhook_flood_evento (
                wa_id_cliente,
                phone_id_unidade,
                received_at DESC
            );

            CREATE INDEX IF NOT EXISTS idx_webhook_flood_evento_limpeza
            ON chatbot.webhook_flood_evento (received_at);
        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_tabelas_bloqueio_flood")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=criar_tabelas_bloqueio_flood erro=%s", erro)

    finally:
        if conn:
            conn.close()
