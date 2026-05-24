from core.database.connection_aws import get_conn


def criar_funcoes_lock():

    conn = None

    try:

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""

        CREATE OR REPLACE FUNCTION chatbot.lock_conversa(p_id_conversa INT)
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        AS $$

        DECLARE
            updated_rows INTEGER;

        BEGIN

            UPDATE chatbot.conversa
            SET
                processing = TRUE,
                processing_started_at = NOW(),
                lock_version = lock_version + 1
            WHERE
                id_conversa = p_id_conversa
                AND (
                    processing = FALSE
                    OR processing_started_at < NOW() - INTERVAL '110 seconds'
                );

            GET DIAGNOSTICS updated_rows = ROW_COUNT;

            RETURN updated_rows = 1;

        END;

        $$;

        """)

        cursor.execute("""

        CREATE OR REPLACE FUNCTION chatbot.unlock_conversa(p_id_conversa INT)
        RETURNS VOID
        LANGUAGE plpgsql
        AS $$

        BEGIN

            UPDATE chatbot.conversa
            SET
                processing = FALSE,
                processing_started_at = NULL
            WHERE id_conversa = p_id_conversa;

        END;

        $$;

        """)

        conn.commit()
        print("✅ Funções de lock/unlock criadas com sucesso!")

    except Exception as erro:
        if conn:
            conn.rollback()
        print("❌ Erro ao criar funções de lock:", erro)

    finally:
        if conn:
            conn.close()


def criar_funcao_dequeue_message():

    conn = None

    try:

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""

        CREATE OR REPLACE FUNCTION chatbot.dequeue_message()
        RETURNS TABLE (
            id_mensagem INT,
            cliente_telefone VARCHAR,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR,
            id_phone_unidade VARCHAR,
            unidade_telefone VARCHAR,
            received_data_hora TIMESTAMPTZ,
            id_hash_msg VARCHAR,
            retry_count INT
        )
        LANGUAGE plpgsql
        AS $$

        BEGIN

            RETURN QUERY

            WITH next_job AS (

                SELECT f.id_mensagem
                FROM chatbot.fila_mensagens f
                WHERE
                    (
                        f.status = 'pending'
                        AND f.next_attempt_at <= NOW()
                    )
                    OR
                    (
                        f.status = 'processing'
                        AND f.processing_started_at < NOW() - INTERVAL '2 minutes'
                    )
                ORDER BY 
                    CASE 
                        WHEN f.status = 'pending' THEN f.next_attempt_at
                        WHEN f.status = 'processing' THEN f.processing_started_at
                    END NULLS FIRST,
                    f.id_mensagem
                FOR UPDATE SKIP LOCKED
                LIMIT 1

            )

            UPDATE chatbot.fila_mensagens f
            SET
                status = 'processing',
                retry_count = f.retry_count + 1,
                processing_started_at = NOW()
            FROM next_job
            WHERE f.id_mensagem = next_job.id_mensagem

            RETURNING
                f.id_mensagem,
                f.cliente_telefone,
                f.conteudo_texto,
                f.tipo_mensagem,
                f.id_phone_unidade,
                f.unidade_telefone,
                f.received_data_hora,
                f.id_hash_msg,
                f.retry_count;

        END;

        $$;

        """)

        conn.commit()
        print("✅ Função dequeue_message criada com sucesso!")

    except Exception as erro:
        if conn:
            conn.rollback()
        print("❌ Erro ao criar função dequeue_message:", erro)
    finally:
        if conn:
            conn.close()


def criar_tabelas():

    conn = None
    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""

        SET TIME ZONE 'America/Sao_Paulo';

        CREATE SCHEMA IF NOT EXISTS chatbot;

        -- CLIENTE
        CREATE TABLE IF NOT EXISTS chatbot.cliente (
            id_cliente SERIAL PRIMARY KEY,
            nome VARCHAR(200),
            waid_telefone VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(200) UNIQUE
        );

        -- UNIDADE (corrigido)
        CREATE TABLE IF NOT EXISTS chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY,
            nome VARCHAR(300) UNIQUE NOT NULL,
            cnpj VARCHAR(50) UNIQUE NOT NULL,
            email_responsavel VARCHAR(255) UNIQUE NOT NULL,
            telefone VARCHAR(20) UNIQUE NOT NULL,
            phone_number_id VARCHAR(100) UNIQUE NOT NULL,
            link_agendamento VARCHAR(400) UNIQUE NOT NULL,
            status_ativo BOOLEAN DEFAULT TRUE
        );

        -- ETAPA
        CREATE TABLE IF NOT EXISTS chatbot.etapa (
            id_etapa SERIAL PRIMARY KEY,
            nome_etapa VARCHAR(100) UNIQUE NOT NULL
        );

        -- CONVERSA
        CREATE TABLE IF NOT EXISTS chatbot.conversa (
            id_conversa SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_unidade INT NOT NULL,
            id_etapa_atual INT,

            status_ativa BOOLEAN NOT NULL DEFAULT TRUE,
            status_dependente BOOLEAN DEFAULT FALSE,

            last_interaction_at TIMESTAMPTZ,

            last_message_from VARCHAR(10)
                CHECK (last_message_from IN ('cliente','bot')),

            followup_stage INTEGER DEFAULT 0,
            followup_last_sent_at TIMESTAMPTZ NULL,

            lead_no_funil BOOLEAN DEFAULT FALSE,

            processing BOOLEAN DEFAULT FALSE,
            processing_started_at TIMESTAMPTZ NULL,
            lock_version INTEGER DEFAULT 0,

            iniciou_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finalizou_em TIMESTAMPTZ,

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE,

            FOREIGN KEY (id_unidade)
                REFERENCES chatbot.unidade(id_unidade)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa_atual)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversa_unica_ativa
        ON chatbot.conversa (id_cliente, id_unidade)
        WHERE status_ativa = TRUE;

        CREATE INDEX IF NOT EXISTS idx_conversa_followup
        ON chatbot.conversa (last_message_from, followup_stage, last_interaction_at);

        CREATE INDEX IF NOT EXISTS idx_conversa_processing
        ON chatbot.conversa(processing, processing_started_at);

        CREATE INDEX IF NOT EXISTS idx_conversa_ativa
        ON chatbot.conversa (id_cliente, id_unidade)
        WHERE status_ativa = TRUE;

        CREATE INDEX IF NOT EXISTS idx_conversa_ultima_inativa
        ON chatbot.conversa (id_cliente, id_unidade, finalizou_em DESC)
        INCLUDE (id_conversa, id_etapa_atual)
        WHERE status_ativa = FALSE;

        -- HISTÓRICO
        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens (
            id_mensagem SERIAL,
            id_conversa INT NOT NULL,
            id_etapa INT,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT NOT NULL,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) NOT NULL,
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,

            PRIMARY KEY (id_mensagem, received_data_hora),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL
        )
        PARTITION BY RANGE (received_data_hora);

        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens_default
        PARTITION OF chatbot.historico_mensagens
        DEFAULT;

        -- FILA
        CREATE TABLE IF NOT EXISTS chatbot.fila_mensagens (
            id_mensagem SERIAL PRIMARY KEY,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            next_attempt_at TIMESTAMPTZ DEFAULT NOW(),
            processing_started_at TIMESTAMPTZ NULL,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) UNIQUE NOT NULL,
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,
            CHECK (status IN ('pending','processing','sent','failed'))
        );

        CREATE INDEX IF NOT EXISTS idx_fila_status_time
        ON chatbot.fila_mensagens (status, next_attempt_at);

        CREATE INDEX IF NOT EXISTS idx_fila_processing_timeout
        ON chatbot.fila_mensagens (processing_started_at);

        """)

        conn.commit()
        print("✅ Estrutura do banco criada com sucesso!")

    except Exception as erro:

        if conn:
            conn.rollback()
        print("❌ Erro ao criar tabelas:", erro)

    finally:
        if conn:
            conn.close()

def alterar_banco():

    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            ALTER TABLE chatbot.fila_mensagens
            ADD COLUMN IF NOT EXISTS last_error TEXT;
        """)

        conn.commit()
        print("✅ Coluna 'last_error' adicionada (ou já existente) com sucesso!")

    except Exception as erro:
        if conn:
            conn.rollback()
        print("❌ Erro ao alterar banco (last_error):", erro)

    finally:
        if conn:
            conn.close()


def definir_timezone_role():
    conn = None
    try:

        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            ALTER ROLE fushi
            SET timezone TO 'America/Sao_Paulo';
        """)

        conn.commit()
        print("✅ Timezone do ROLE 'fushi' definido com sucesso!")

    except Exception as e:

        if conn:
            conn.rollback()
        print("❌ Erro ao definir timezone do ROLE:", e)

    finally:
        if conn:
            conn.close()

def configurar_timeouts_avancados():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        # 🔥 essencial (perfeito)
        cursor.execute("""
            ALTER ROLE fushi
            SET idle_in_transaction_session_timeout = '30min';
        """)

        # 🔥 melhor escolha pro seu caso
        cursor.execute("""
            ALTER ROLE fushi
            SET statement_timeout = '10min';
        """)

        # 🔥 ajustado pro seu padrão
        cursor.execute("""
            ALTER ROLE fushi
            SET lock_timeout = '15s';
        """)

        conn.commit()
        print("✅ Timeouts avançados configurados com sucesso")

    except Exception as erro:
        if conn:
            conn.rollback()
        print(f"❌ Erro ao configurar timeouts: {erro}")

    finally:
        if conn:
            conn.close()
