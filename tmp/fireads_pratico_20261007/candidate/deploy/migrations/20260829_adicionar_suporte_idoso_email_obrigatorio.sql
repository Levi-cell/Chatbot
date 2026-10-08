BEGIN;

DO $migracao_unidade$
DECLARE
    quantidade_colunas INTEGER;
BEGIN
    IF TO_REGCLASS('chatbot.unidade') IS NULL
       OR TO_REGCLASS('chatbot.conversa') IS NULL THEN
        RAISE EXCEPTION
            'Migração recusada: chatbot.unidade e chatbot.conversa devem existir.';
    END IF;

    SELECT COUNT(*)
    INTO quantidade_colunas
    FROM information_schema.columns
    WHERE table_schema = 'chatbot'
      AND table_name = 'unidade'
      AND column_name IN ('suporte_idoso', 'email_obrigatorio');

    IF quantidade_colunas = 1 THEN
        RAISE EXCEPTION
            'Migração recusada: schema parcial das flags da unidade.';
    END IF;

    IF quantidade_colunas = 0 THEN
        ALTER TABLE chatbot.unidade
            ADD COLUMN suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('suporte_idoso', 'false'),
                ('email_obrigatorio', 'true')
        ) AS esperado(column_name, column_default)
        LEFT JOIN information_schema.columns AS coluna
          ON coluna.table_schema = 'chatbot'
         AND coluna.table_name = 'unidade'
         AND coluna.column_name = esperado.column_name
        WHERE coluna.column_name IS NULL
           OR coluna.data_type <> 'boolean'
           OR coluna.is_nullable <> 'NO'
           OR coluna.column_default IS DISTINCT FROM esperado.column_default
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: flags da unidade não correspondem ao contrato BOOLEAN NOT NULL com defaults FALSE/TRUE.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM chatbot.unidade
        WHERE suporte_idoso IS NULL
           OR email_obrigatorio IS NULL
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: foram encontrados valores nulos nas flags da unidade.';
    END IF;
END
$migracao_unidade$;

DO $migracao_motivo_encerramento$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM chatbot.conversa
        WHERE motivo_encerramento IS NOT NULL
          AND motivo_encerramento NOT IN (
              'idade_invalida',
              'foi_agendado',
              'encaminhado_suporte_idoso'
          )
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: conversa.motivo_encerramento contém valor fora do domínio esperado.';
    END IF;

    ALTER TABLE chatbot.conversa
        DROP CONSTRAINT IF EXISTS ck_conversa_motivo_encerramento;

    ALTER TABLE chatbot.conversa
        ADD CONSTRAINT ck_conversa_motivo_encerramento
        CHECK (
            motivo_encerramento IS NULL
            OR motivo_encerramento IN (
                'idade_invalida',
                'foi_agendado',
                'encaminhado_suporte_idoso'
            )
        );

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'chatbot.conversa'::regclass
          AND conname = 'ck_conversa_motivo_encerramento'
          AND contype = 'c'
          AND convalidated = TRUE
    ) THEN
        RAISE EXCEPTION
            'Pós-condição falhou: domínio de motivo_encerramento não foi publicado.';
    END IF;
END
$migracao_motivo_encerramento$;

COMMIT;
