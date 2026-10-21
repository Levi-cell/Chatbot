-- Executar o arquivo inteiro, com consumidores parados e backup validado.
-- Banco V1.2.0: TRUE -> 60; FALSE -> NULL. Não executar em instalação nova.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $precondicoes$
BEGIN
    IF to_regclass('chatbot.unidade') IS NULL THEN
        RAISE EXCEPTION 'Tabela chatbot.unidade ausente';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'chatbot' AND table_name = 'unidade'
           AND column_name = 'idade_minima_suporte'
    ) THEN
        RAISE EXCEPTION 'Migração já aplicada ou schema parcial: idade_minima_suporte já existe';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'chatbot' AND table_name = 'unidade'
           AND column_name = 'suporte_idoso' AND data_type = 'boolean'
           AND is_nullable = 'NO' AND column_default = 'false'
    ) THEN
        RAISE EXCEPTION 'Esperado suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE da V1.2.0';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'chatbot.unidade'::regclass
           AND conname = 'ck_unidade_idade_minima_suporte'
    ) THEN
        RAISE EXCEPTION 'Restrição de destino já existe; revisar schema parcial';
    END IF;
END;
$precondicoes$;

LOCK TABLE chatbot.unidade IN ACCESS EXCLUSIVE MODE;

-- Fotografia temporária apenas para provar a conversão; eliminada no commit.
CREATE TEMP TABLE suporte_idade_antes ON COMMIT DROP AS
SELECT u.id_unidade, u.suporte_idoso,
       to_jsonb(u) - 'suporte_idoso' AS outros_campos
  FROM chatbot.unidade u;

SELECT COUNT(*) AS unidades_antes,
       COUNT(*) FILTER (WHERE suporte_idoso) AS habilitadas_antes,
       COUNT(*) FILTER (WHERE NOT suporte_idoso) AS desativadas_antes
  FROM suporte_idade_antes;

ALTER TABLE chatbot.unidade
    ALTER COLUMN suporte_idoso DROP DEFAULT,
    ALTER COLUMN suporte_idoso DROP NOT NULL;

ALTER TABLE chatbot.unidade
    ALTER COLUMN suporte_idoso TYPE INTEGER
    USING CASE WHEN suporte_idoso THEN 60 ELSE NULL END;

ALTER TABLE chatbot.unidade RENAME COLUMN suporte_idoso TO idade_minima_suporte;

ALTER TABLE chatbot.unidade
    ALTER COLUMN idade_minima_suporte SET DEFAULT NULL,
    ADD CONSTRAINT ck_unidade_idade_minima_suporte CHECK (
        idade_minima_suporte IS NULL
        OR idade_minima_suporte IN (50, 60, 70, 80, 90)
    );

DO $poscondicoes$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'chatbot' AND table_name = 'unidade'
           AND column_name = 'idade_minima_suporte'
           AND data_type = 'integer' AND is_nullable = 'YES'
           AND (column_default IS NULL OR column_default = 'NULL::integer')
    ) OR EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'chatbot' AND table_name = 'unidade'
           AND column_name = 'suporte_idoso'
    ) THEN
        RAISE EXCEPTION 'Contrato final da coluna incorreto';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'chatbot.unidade'::regclass
           AND conname = 'ck_unidade_idade_minima_suporte'
           AND contype = 'c' AND convalidated
    ) THEN
        RAISE EXCEPTION 'Domínio final não está validado';
    END IF;
    IF EXISTS (
        SELECT 1 FROM suporte_idade_antes a
        FULL JOIN chatbot.unidade u USING (id_unidade)
         WHERE a.id_unidade IS NULL OR u.id_unidade IS NULL
            OR u.idade_minima_suporte IS DISTINCT FROM
               CASE WHEN a.suporte_idoso THEN 60 ELSE NULL END
            OR (to_jsonb(u) - 'idade_minima_suporte') IS DISTINCT FROM a.outros_campos
    ) THEN
        RAISE EXCEPTION 'Conversão não preservou configurações e demais dados das unidades';
    END IF;
END;
$poscondicoes$;

SELECT COUNT(*) AS unidades_depois,
       COUNT(*) FILTER (WHERE idade_minima_suporte = 60) AS habilitadas_60,
       COUNT(*) FILTER (WHERE idade_minima_suporte IS NULL) AS desativadas
  FROM chatbot.unidade;

COMMIT;
