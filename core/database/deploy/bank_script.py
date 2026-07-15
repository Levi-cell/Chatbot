import logging

from core.database.deploy.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.deploy")


def criar_funcoes_lock():
    with transacao_deploy("criar_funcoes_lock", logger) as cursor:
        cursor.execute("""
        CREATE OR REPLACE FUNCTION chatbot.lock_conversa(p_id_conversa INT)
        RETURNS TABLE (
            lock_ok BOOLEAN,
            lock_version_atual INT
        )
        LANGUAGE plpgsql
        AS $$

        DECLARE
            v_lock_version INT;

        BEGIN
            UPDATE chatbot.conversa c
            SET
                processing = TRUE,
                processing_started_at = NOW(),
                lock_version = COALESCE(c.lock_version, 0) + 1
            WHERE
                c.id_conversa = p_id_conversa
                AND (
                    c.processing = FALSE
                    OR c.processing_started_at
                        < NOW() - INTERVAL '110.0 seconds'
                )
            RETURNING c.lock_version INTO v_lock_version;

            IF v_lock_version IS NULL THEN
                RETURN QUERY SELECT FALSE, NULL::INT;
                RETURN;
            END IF;

            RETURN QUERY SELECT TRUE, v_lock_version;
        END;

        $$;
        """)

        cursor.execute("""
        CREATE OR REPLACE FUNCTION chatbot.unlock_conversa(
            p_id_conversa INT,
            p_lock_version INT
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        AS $$

        DECLARE
            updated_rows INTEGER;

        BEGIN
            UPDATE chatbot.conversa
            SET
                processing = FALSE,
                processing_started_at = NULL
            WHERE id_conversa = p_id_conversa
              AND lock_version = p_lock_version;

            GET DIAGNOSTICS updated_rows = ROW_COUNT;

            RETURN updated_rows = 1;
        END;

        $$;
        """)

    logger.info("banco_setup_ok | acao=criar_funcoes_lock")


def criar_funcao_dequeue_message():
    with transacao_deploy("criar_funcao_dequeue_message", logger) as cursor:
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
                        AND f.processing_started_at
                            < NOW() - INTERVAL '2 minutes'
                    )
                ORDER BY
                    CASE
                        WHEN f.status = 'pending' THEN f.next_attempt_at
                        WHEN f.status = 'processing'
                            THEN f.processing_started_at
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

    logger.info("banco_setup_ok | acao=criar_funcao_dequeue_message")


def criar_tabelas():
    """Cria o schema final da V1 em ordem de dependência, sem migrações."""
    with transacao_deploy("criar_tabelas", logger) as cursor:
        cursor.execute("""
        CREATE SCHEMA IF NOT EXISTS chatbot;

        -- 1. ENTIDADES SEM DEPENDÊNCIAS ENTRE TABELAS

        CREATE TABLE IF NOT EXISTS chatbot.cliente (
            id_cliente SERIAL PRIMARY KEY,
            nome VARCHAR(200),
            waid_telefone VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(200) UNIQUE,
            idade INTEGER
        );

        CREATE TABLE IF NOT EXISTS chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY,
            nome VARCHAR(300) UNIQUE NOT NULL,
            cnpj VARCHAR(50) UNIQUE NOT NULL,
            email_responsavel VARCHAR(255) UNIQUE NOT NULL,
            telefone VARCHAR(20) UNIQUE NOT NULL,
            numero_comercial VARCHAR(30),
            waba_id VARCHAR(100),
            phone_number_id VARCHAR(100) UNIQUE NOT NULL,
            link_agendamento VARCHAR(400) UNIQUE NOT NULL,
            link_instagram VARCHAR(400),
            bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE,
            status_pagamento BOOLEAN DEFAULT TRUE
        );

        CREATE TABLE IF NOT EXISTS chatbot.etapa (
            id_etapa SERIAL PRIMARY KEY,
            nome_etapa VARCHAR(100) UNIQUE NOT NULL,
            encerra_automaticamente BOOLEAN NOT NULL DEFAULT FALSE,
            bloqueio_dias INTEGER NOT NULL DEFAULT 0,
            elegivel_funil BOOLEAN NOT NULL DEFAULT FALSE,

            CONSTRAINT ck_etapa_bloqueio_dias
                CHECK (bloqueio_dias >= 0)
        );

        -- 2. CONFIGURACAO DO FUNIL POR UNIDADE

        CREATE TABLE IF NOT EXISTS chatbot.integracao_funil_unidade (
            id_integracao_funil SERIAL PRIMARY KEY,
            id_unidade INT NOT NULL UNIQUE,

            nome_widget VARCHAR(300) NOT NULL,
            data_salvamento_widget DATE,
            codigo_widget VARCHAR(100) UNIQUE NOT NULL,
            link_api_carrossel VARCHAR(500) UNIQUE NOT NULL,
            codigo_canal_venda VARCHAR(100) NOT NULL,

            widget_ativo BOOLEAN NOT NULL DEFAULT TRUE,
            integracao_ativa BOOLEAN NOT NULL DEFAULT TRUE,

            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT ck_integracao_funil_nome_widget
                CHECK (BTRIM(nome_widget) <> ''),

            CONSTRAINT ck_integracao_funil_codigo_widget
                CHECK (BTRIM(codigo_widget) <> ''),

            CONSTRAINT ck_integracao_funil_link_api
                CHECK (BTRIM(link_api_carrossel) <> ''),

            CONSTRAINT ck_integracao_funil_codigo_canal
                CHECK (BTRIM(codigo_canal_venda) <> ''),

            CONSTRAINT integracao_funil_unidade_id_unidade_fkey
                FOREIGN KEY (id_unidade)
                REFERENCES chatbot.unidade(id_unidade)
                ON DELETE CASCADE
        );

        -- 3. CONVERSA: RAIZ TRANSACIONAL DO ATENDIMENTO

        CREATE TABLE IF NOT EXISTS chatbot.conversa (
            id_conversa SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_unidade INT NOT NULL,
            id_etapa_atual INT,

            status_ativa BOOLEAN NOT NULL DEFAULT TRUE,
            status_dependente BOOLEAN DEFAULT FALSE,

            last_interaction_at TIMESTAMPTZ,

            last_message_from VARCHAR(10)
                CHECK (last_message_from IN ('cliente', 'bot')),

            followup_stage INTEGER DEFAULT 0,
            followup_last_sent_at TIMESTAMPTZ NULL,

            lead_no_funil BOOLEAN DEFAULT FALSE,

            processing BOOLEAN DEFAULT FALSE,
            processing_started_at TIMESTAMPTZ NULL,
            lock_version INTEGER DEFAULT 0,

            iniciou_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finalizou_em TIMESTAMPTZ,
            motivo_encerramento VARCHAR(30),

            CONSTRAINT ck_conversa_motivo_encerramento
                CHECK (
                    motivo_encerramento IS NULL
                    OR motivo_encerramento IN (
                        'idade_invalida',
                        'foi_agendado'
                    )
                ),

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
        ON chatbot.conversa (
            last_message_from,
            followup_stage,
            last_interaction_at
        );

        CREATE INDEX IF NOT EXISTS idx_conversa_processing
        ON chatbot.conversa (processing, processing_started_at);

        CREATE INDEX IF NOT EXISTS idx_conversa_ultima_inativa
        ON chatbot.conversa (id_cliente, id_unidade, finalizou_em DESC)
        INCLUDE (id_conversa, id_etapa_atual)
        WHERE status_ativa = FALSE;

        CREATE INDEX IF NOT EXISTS idx_conversa_funil_pendente
        ON chatbot.conversa (id_etapa_atual, id_conversa)
        WHERE lead_no_funil IS NOT TRUE;

        -- 4. DEPENDENTE: EXISTE SOMENTE DENTRO DE UMA CONVERSA

        CREATE TABLE IF NOT EXISTS chatbot.dependente (
            id_dependente SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_conversa INT,
            nome_dependente VARCHAR(200),
            idade INTEGER,

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE,

            CONSTRAINT dependente_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_dependente_cliente
        ON chatbot.dependente (id_cliente);

        CREATE UNIQUE INDEX IF NOT EXISTS uq_dependente_conversa
        ON chatbot.dependente (id_conversa)
        WHERE id_conversa IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_dependente_conversa
        ON chatbot.dependente (id_conversa);

        -- 5. FILA: CRIADA ANTES DO HISTÓRICO PARA A FK NASCER PRONTA

        CREATE TABLE IF NOT EXISTS chatbot.fila_mensagens (
            id_mensagem SERIAL PRIMARY KEY,
            id_conversa INT NULL,
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
            last_error TEXT,

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE SET NULL,

            CHECK (status IN ('pending', 'processing', 'sent', 'failed'))
        );

        CREATE INDEX IF NOT EXISTS idx_fila_pending_next_attempt
        ON chatbot.fila_mensagens (next_attempt_at, id_mensagem)
        WHERE status = 'pending';

        CREATE INDEX IF NOT EXISTS idx_fila_processing_timeout
        ON chatbot.fila_mensagens (processing_started_at, id_mensagem)
        WHERE status = 'processing';

        CREATE INDEX IF NOT EXISTS idx_fila_conversa_aberta_data
        ON chatbot.fila_mensagens (
            id_conversa,
            received_data_hora,
            id_mensagem
        )
        WHERE id_conversa IS NOT NULL
          AND status IN ('pending', 'processing');

        -- 6. HISTÓRICO PARTICIONADO E RESPOSTAS DA TRIAGEM

        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens (
            id_mensagem SERIAL,
            id_conversa INT NOT NULL,
            id_etapa INT,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) NOT NULL,
            id_mensagem_fila INT,
            id_hash_cliente_origem VARCHAR(255),
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,
            quem_enviou VARCHAR(10) NOT NULL,
            status_envio VARCHAR(20),

            PRIMARY KEY (id_mensagem, received_data_hora),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL,

            CONSTRAINT fk_historico_mensagem_fila
                FOREIGN KEY (id_mensagem_fila)
                REFERENCES chatbot.fila_mensagens(id_mensagem)
                ON DELETE SET NULL,

            CONSTRAINT chk_historico_quem_enviou
                CHECK (quem_enviou IN ('cliente', 'bot')),

            CONSTRAINT chk_historico_status_envio
                CHECK (
                    (quem_enviou = 'cliente' AND status_envio IS NULL)
                    OR
                    (
                        quem_enviou = 'bot'
                        AND status_envio IS NOT NULL
                        AND status_envio IN ('pending', 'sent', 'failed')
                    )
                )
        )
        PARTITION BY RANGE (received_data_hora);

        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens_default
        PARTITION OF chatbot.historico_mensagens
        DEFAULT;

        CREATE INDEX IF NOT EXISTS idx_historico_conversa_data
        ON chatbot.historico_mensagens (
            id_conversa,
            received_data_hora DESC,
            id_mensagem DESC
        );

        CREATE INDEX IF NOT EXISTS idx_historico_cliente_mensagem_fila
        ON chatbot.historico_mensagens (
            id_conversa,
            id_mensagem_fila,
            id_hash_msg,
            received_data_hora DESC,
            id_mensagem DESC
        )
        WHERE quem_enviou = 'cliente'
          AND id_mensagem_fila IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_historico_bot_mensagem_fila
        ON chatbot.historico_mensagens (
            id_conversa,
            id_mensagem_fila,
            id_hash_cliente_origem,
            received_data_hora DESC,
            id_mensagem DESC
        )
        WHERE quem_enviou = 'bot'
          AND id_mensagem_fila IS NOT NULL
          AND id_hash_cliente_origem IS NOT NULL;

        CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios (
            id_resposta_desafio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL,
            id_etapa INT NOT NULL,
            resposta VARCHAR(20) NOT NULL,
            id_historico_mensagem_cliente INT NULL,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa),

            CONSTRAINT uq_respostas_desafios_conversa_etapa
                UNIQUE (id_conversa, id_etapa)
        );

        -- 7. FILA OPERACIONAL DO WORKER DE FUNIL

        CREATE TABLE IF NOT EXISTS chatbot.funil_envios (
            id_funil_envio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL UNIQUE,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processing_started_at TIMESTAMPTZ,
            enviado_em TIMESTAMPTZ,
            ultimo_erro TEXT,
            resposta_funil TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT funil_envios_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            CONSTRAINT ck_funil_envios_status
                CHECK (status IN ('pending', 'processing', 'sent')),

            CONSTRAINT ck_funil_envios_attempt_count
                CHECK (attempt_count >= 0)
        );

        CREATE INDEX IF NOT EXISTS idx_funil_envios_disponiveis
        ON chatbot.funil_envios (
            status,
            next_attempt_at,
            processing_started_at,
            id_funil_envio
        )
        WHERE status IN ('pending', 'processing');
        """)

    logger.info("banco_setup_ok | acao=criar_tabelas")


def configurar_role_banco():
    """Aplica timezone e limites operacionais da role em uma transação."""
    with transacao_deploy("configurar_role_banco", logger) as cursor:
        cursor.execute("""
            ALTER ROLE fushi
            SET timezone TO 'America/Sao_Paulo';

            ALTER ROLE fushi
            SET idle_in_transaction_session_timeout = '30min';

            ALTER ROLE fushi
            SET statement_timeout = '10min';

            ALTER ROLE fushi
            SET lock_timeout = '15s';
        """)

    logger.info("banco_setup_ok | acao=configurar_role_banco role=fushi")
