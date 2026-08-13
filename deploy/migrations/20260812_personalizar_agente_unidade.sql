-- Renomeia unidade.nome e adiciona a configuracao de apresentacao do agente.
--
-- Pre-requisitos operacionais:
--   1. parar webhook, worker-flow e worker-funil e confirmar que estao inativos;
--   2. criar e aguardar um snapshot recente do RDS;
--   3. executar este arquivo inteiro como script UTF-8 no DBeaver;
--   4. publicar o codigo correspondente antes de religar os servicos.
--
-- As unidades existentes recebem Suh/feminino, preservando a apresentacao
-- anterior. Novas unidades continuam sendo cadastradas exclusivamente pelo
-- Django Admin. O script aceita apenas o schema legado canonico ou o schema
-- final canonico; estados parciais geram excecao e rollback integral.
-- Depois do COMMIT, o rollback suportado e restaurar o snapshot junto com a
-- versao anterior da aplicacao, pois o rename nao e compativel com ambos os
-- codigos simultaneamente.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

LOCK TABLE chatbot.unidade IN ACCESS EXCLUSIVE MODE;

DO $migracao_agente_unidade$
DECLARE
    v_tem_nome BOOLEAN;
    v_tem_nome_unidade BOOLEAN;
    v_tem_nome_agente BOOLEAN;
    v_tem_genero BOOLEAN;
    v_estado_legado BOOLEAN;
    v_estado_final BOOLEAN;
    v_dado_invalido BOOLEAN;
    v_total BIGINT;
    v_atualizadas BIGINT;
    v_qtd_unique INTEGER;
    v_nome_unique TEXT;
BEGIN
    SELECT
        EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'chatbot'
              AND table_name = 'unidade'
              AND column_name = 'nome'
        ),
        EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'chatbot'
              AND table_name = 'unidade'
              AND column_name = 'nome_unidade'
        ),
        EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'chatbot'
              AND table_name = 'unidade'
              AND column_name = 'nome_agente'
        ),
        EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'chatbot'
              AND table_name = 'unidade'
              AND column_name = 'genero'
        )
    INTO
        v_tem_nome,
        v_tem_nome_unidade,
        v_tem_nome_agente,
        v_tem_genero;

    v_estado_legado :=
        v_tem_nome
        AND NOT v_tem_nome_unidade
        AND NOT v_tem_nome_agente
        AND NOT v_tem_genero;

    v_estado_final :=
        NOT v_tem_nome
        AND v_tem_nome_unidade
        AND v_tem_nome_agente
        AND v_tem_genero;

    IF NOT v_estado_legado AND NOT v_estado_final THEN
        RAISE EXCEPTION
            'chatbot.unidade esta fora dos estados legado/final suportados; migracao cancelada';
    END IF;

    IF v_estado_final THEN
        RAISE NOTICE
            'Schema final de unidade ja presente; nenhum backfill sera repetido';
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'unidade'
          AND column_name = 'nome'
          AND data_type = 'character varying'
          AND character_maximum_length = 300
          AND is_nullable = 'NO'
    ) THEN
        RAISE EXCEPTION
            'Coluna legada chatbot.unidade.nome possui contrato inesperado';
    END IF;

    EXECUTE $sql$
        SELECT EXISTS (
            SELECT 1
            FROM chatbot.unidade
            WHERE nome IS NULL OR nome !~ '[^[:space:]]'
        )
    $sql$
    INTO v_dado_invalido;

    IF v_dado_invalido THEN
        RAISE EXCEPTION
            'Existem unidades com nome nulo ou vazio; corrija os dados antes da migracao';
    END IF;

    EXECUTE $sql$
        CREATE TEMP TABLE migracao_agente_unidade_antes
        ON COMMIT DROP
        AS
        SELECT id_unidade, nome AS nome_unidade
        FROM chatbot.unidade
    $sql$;

    SELECT COUNT(*)
    INTO v_total
    FROM migracao_agente_unidade_antes;

    ALTER TABLE chatbot.unidade
        RENAME COLUMN nome TO nome_unidade;

    ALTER TABLE chatbot.unidade
        ADD COLUMN nome_agente VARCHAR(100),
        ADD COLUMN genero VARCHAR(9);

    UPDATE chatbot.unidade
    SET
        nome_agente = 'Suh',
        genero = 'feminino';

    GET DIAGNOSTICS v_atualizadas = ROW_COUNT;

    IF v_atualizadas <> v_total THEN
        RAISE EXCEPTION
            'Backfill atualizou % unidades; esperado: %',
            v_atualizadas,
            v_total;
    END IF;

    SELECT
        COUNT(*),
        MIN(constraint_info.conname::TEXT)
    INTO
        v_qtd_unique,
        v_nome_unique
    FROM (
        SELECT constraint_row.conname
        FROM pg_constraint AS constraint_row
        INNER JOIN pg_class AS tabela
            ON tabela.oid = constraint_row.conrelid
        INNER JOIN pg_namespace AS schema_info
            ON schema_info.oid = tabela.relnamespace
        INNER JOIN pg_attribute AS coluna
            ON coluna.attrelid = tabela.oid
           AND coluna.attname = 'nome_unidade'
           AND NOT coluna.attisdropped
        WHERE schema_info.nspname = 'chatbot'
          AND tabela.relname = 'unidade'
          AND constraint_row.contype = 'u'
          AND constraint_row.conkey = ARRAY[coluna.attnum]::SMALLINT[]
    ) AS constraint_info;

    IF v_qtd_unique <> 1 THEN
        RAISE EXCEPTION
            'Era esperada uma unica constraint UNIQUE para nome_unidade; encontradas: %',
            v_qtd_unique;
    END IF;

    IF v_nome_unique <> 'uq_unidade_nome_unidade' THEN
        IF EXISTS (
            SELECT 1
            FROM pg_constraint
            WHERE conrelid = 'chatbot.unidade'::REGCLASS
              AND conname = 'uq_unidade_nome_unidade'
        ) THEN
            RAISE EXCEPTION
                'Nome final uq_unidade_nome_unidade ja esta ocupado por outra constraint';
        END IF;

        EXECUTE FORMAT(
            'ALTER TABLE chatbot.unidade RENAME CONSTRAINT %I TO uq_unidade_nome_unidade',
            v_nome_unique
        );
    END IF;

    ALTER TABLE chatbot.unidade
        ADD CONSTRAINT ck_unidade_nome_unidade_nao_vazio
            CHECK (nome_unidade ~ '[^[:space:]]'),
        ADD CONSTRAINT ck_unidade_nome_agente_nao_vazio
            CHECK (nome_agente ~ '[^[:space:]]'),
        ADD CONSTRAINT ck_unidade_genero
            CHECK (genero IN ('masculino', 'feminino'));

    ALTER TABLE chatbot.unidade
        ALTER COLUMN nome_agente SET NOT NULL,
        ALTER COLUMN genero SET NOT NULL;

    IF EXISTS (
        SELECT id_unidade, nome_unidade
        FROM migracao_agente_unidade_antes
        EXCEPT
        SELECT id_unidade, nome_unidade
        FROM chatbot.unidade
    ) OR EXISTS (
        SELECT id_unidade, nome_unidade
        FROM chatbot.unidade
        EXCEPT
        SELECT id_unidade, nome_unidade
        FROM migracao_agente_unidade_antes
    ) THEN
        RAISE EXCEPTION
            'O rename alterou ids ou nomes das unidades; migracao cancelada';
    END IF;
END
$migracao_agente_unidade$;

-- Gera as definições canônicas no próprio PostgreSQL. A comparação por
-- pg_get_constraintdef evita aceitar uma constraint homônima com outra regra.
CREATE TEMP TABLE contrato_agente_unidade_esperado (
    nome_unidade VARCHAR(300),
    nome_agente VARCHAR(100),
    genero VARCHAR(9),

    CONSTRAINT uq_unidade_nome_unidade
        UNIQUE (nome_unidade),

    CONSTRAINT ck_unidade_nome_unidade_nao_vazio
        CHECK (nome_unidade ~ '[^[:space:]]'),

    CONSTRAINT ck_unidade_nome_agente_nao_vazio
        CHECK (nome_agente ~ '[^[:space:]]'),

    CONSTRAINT ck_unidade_genero
        CHECK (genero IN ('masculino', 'feminino'))
) ON COMMIT DROP;

DO $validar_agente_unidade$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'unidade'
          AND column_name = 'nome'
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'unidade'
          AND column_name = 'nome_unidade'
          AND data_type = 'character varying'
          AND character_maximum_length = 300
          AND is_nullable = 'NO'
          AND column_default IS NULL
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'unidade'
          AND column_name = 'nome_agente'
          AND data_type = 'character varying'
          AND character_maximum_length = 100
          AND is_nullable = 'NO'
          AND column_default IS NULL
    ) OR NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'unidade'
          AND column_name = 'genero'
          AND data_type = 'character varying'
          AND character_maximum_length = 9
          AND is_nullable = 'NO'
          AND column_default IS NULL
    ) THEN
        RAISE EXCEPTION
            'Colunas finais de chatbot.unidade divergentes do contrato';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM chatbot.unidade
        WHERE nome_unidade !~ '[^[:space:]]'
           OR nome_agente !~ '[^[:space:]]'
           OR genero NOT IN ('masculino', 'feminino')
    ) THEN
        RAISE EXCEPTION
            'Dados finais de apresentacao da unidade sao invalidos';
    END IF;

    IF EXISTS (
        SELECT
            contrato.conname,
            contrato.contype,
            pg_get_constraintdef(contrato.oid)
        FROM pg_constraint AS contrato
        WHERE contrato.conrelid =
            'pg_temp.contrato_agente_unidade_esperado'::REGCLASS
        EXCEPT
        SELECT
            atual.conname,
            atual.contype,
            pg_get_constraintdef(atual.oid)
        FROM pg_constraint AS atual
        WHERE atual.conrelid = 'chatbot.unidade'::REGCLASS
          AND atual.conname IN (
              'uq_unidade_nome_unidade',
              'ck_unidade_nome_unidade_nao_vazio',
              'ck_unidade_nome_agente_nao_vazio',
              'ck_unidade_genero'
          )
    ) OR EXISTS (
        SELECT
            atual.conname,
            atual.contype,
            pg_get_constraintdef(atual.oid)
        FROM pg_constraint AS atual
        WHERE atual.conrelid = 'chatbot.unidade'::REGCLASS
          AND atual.conname IN (
              'uq_unidade_nome_unidade',
              'ck_unidade_nome_unidade_nao_vazio',
              'ck_unidade_nome_agente_nao_vazio',
              'ck_unidade_genero'
          )
        EXCEPT
        SELECT
            contrato.conname,
            contrato.contype,
            pg_get_constraintdef(contrato.oid)
        FROM pg_constraint AS contrato
        WHERE contrato.conrelid =
            'pg_temp.contrato_agente_unidade_esperado'::REGCLASS
    ) OR EXISTS (
        SELECT 1
        FROM pg_constraint AS atual
        WHERE atual.conrelid = 'chatbot.unidade'::REGCLASS
          AND atual.conname IN (
              'uq_unidade_nome_unidade',
              'ck_unidade_nome_unidade_nao_vazio',
              'ck_unidade_nome_agente_nao_vazio',
              'ck_unidade_genero'
          )
          AND NOT atual.convalidated
    ) OR EXISTS (
        SELECT 1
        FROM pg_constraint AS extra
        CROSS JOIN LATERAL UNNEST(extra.conkey) AS coluna_extra(attnum)
        WHERE extra.conrelid = 'chatbot.unidade'::REGCLASS
          AND extra.contype <> 'n'
          AND extra.conname NOT IN (
              'uq_unidade_nome_unidade',
              'ck_unidade_nome_unidade_nao_vazio',
              'ck_unidade_nome_agente_nao_vazio',
              'ck_unidade_genero'
          )
          AND coluna_extra.attnum IN (
              SELECT coluna.attnum
              FROM pg_attribute AS coluna
              WHERE coluna.attrelid = 'chatbot.unidade'::REGCLASS
                AND coluna.attname IN (
                    'nome_unidade',
                    'nome_agente',
                    'genero'
                )
                AND NOT coluna.attisdropped
          )
    ) THEN
        RAISE EXCEPTION
            'Constraints finais de chatbot.unidade divergem do contrato canonico';
    END IF;
END
$validar_agente_unidade$;

SELECT
    id_unidade,
    nome_unidade,
    nome_agente,
    genero
FROM chatbot.unidade
ORDER BY id_unidade;

COMMIT;
