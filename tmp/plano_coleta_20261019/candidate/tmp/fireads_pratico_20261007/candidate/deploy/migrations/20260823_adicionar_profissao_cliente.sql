BEGIN;

ALTER TABLE chatbot.cliente
    ADD COLUMN IF NOT EXISTS profissao VARCHAR(100);

DO $schema_profissao$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('cliente',  'profissao', 100),
                ('conversa', 'profissao', 100)
        ) AS esperado(table_name, column_name, max_length)
        LEFT JOIN information_schema.columns AS coluna
          ON coluna.table_schema = 'chatbot'
         AND coluna.table_name = esperado.table_name
         AND coluna.column_name = esperado.column_name
        WHERE coluna.column_name IS NULL
           OR coluna.data_type <> 'character varying'
           OR coluna.character_maximum_length IS DISTINCT FROM esperado.max_length
           OR coluna.is_nullable <> 'YES'
           OR coluna.column_default IS NOT NULL
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: cliente.profissao e conversa.profissao devem ser VARCHAR(100) NULL sem default.';
    END IF;
END
$schema_profissao$;

-- O cadastro recebe a profissão da conversa mais recente que possua um valor.
-- Cada chatbot.conversa.profissao permanece intacta como snapshot histórico.
WITH ultima_profissao AS (
    SELECT DISTINCT ON (id_cliente)
        id_cliente,
        BTRIM(profissao) AS profissao
    FROM chatbot.conversa
    WHERE profissao IS NOT NULL
      AND BTRIM(profissao) <> ''
    ORDER BY id_cliente, iniciou_em DESC, id_conversa DESC
)
UPDATE chatbot.cliente AS cliente
SET profissao = ultima_profissao.profissao
FROM ultima_profissao
WHERE cliente.id_cliente = ultima_profissao.id_cliente
  AND NULLIF(BTRIM(cliente.profissao), '') IS NULL;

COMMIT;
