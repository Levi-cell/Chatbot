-- Somente durante manutenção, antes de reiniciar código booleano.
-- Recusa faixas novas: 50/70/80/90 não são equivalentes ao suporte antigo.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $precondicoes$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema='chatbot' AND table_name='unidade'
           AND column_name='idade_minima_suporte' AND data_type='integer'
           AND is_nullable='YES'
    ) OR EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema='chatbot' AND table_name='unidade'
           AND column_name='suporte_idoso'
    ) THEN
        RAISE EXCEPTION 'Schema incompatível com esta reversão';
    END IF;
END;
$precondicoes$;

LOCK TABLE chatbot.unidade IN ACCESS EXCLUSIVE MODE;

DO $dominio$
BEGIN
    IF EXISTS (SELECT 1 FROM chatbot.unidade
                WHERE idade_minima_suporte IS NOT NULL AND idade_minima_suporte <> 60) THEN
        RAISE EXCEPTION 'Há faixas novas configuradas; não converter silenciosamente para 60+';
    END IF;
END;
$dominio$;

CREATE TEMP TABLE suporte_idade_rollback_antes ON COMMIT DROP AS
SELECT id_unidade, idade_minima_suporte, to_jsonb(u) - 'idade_minima_suporte' AS outros_campos
  FROM chatbot.unidade u;

ALTER TABLE chatbot.unidade
    DROP CONSTRAINT ck_unidade_idade_minima_suporte,
    ALTER COLUMN idade_minima_suporte DROP DEFAULT;
ALTER TABLE chatbot.unidade
    ALTER COLUMN idade_minima_suporte TYPE BOOLEAN
    USING (idade_minima_suporte IS NOT NULL);
ALTER TABLE chatbot.unidade RENAME COLUMN idade_minima_suporte TO suporte_idoso;
ALTER TABLE chatbot.unidade
    ALTER COLUMN suporte_idoso SET DEFAULT FALSE,
    ALTER COLUMN suporte_idoso SET NOT NULL;

DO $conferencia$
BEGIN
    IF EXISTS (
        SELECT 1 FROM suporte_idade_rollback_antes a
        FULL JOIN chatbot.unidade u USING (id_unidade)
         WHERE a.id_unidade IS NULL OR u.id_unidade IS NULL
            OR u.suporte_idoso IS DISTINCT FROM (a.idade_minima_suporte IS NOT NULL)
            OR (to_jsonb(u) - 'suporte_idoso') IS DISTINCT FROM a.outros_campos
    ) THEN
        RAISE EXCEPTION 'Reversão não preservou a configuração ou os demais campos';
    END IF;
END;
$conferencia$;

SELECT COUNT(*) AS unidades, COUNT(*) FILTER (WHERE suporte_idoso) AS habilitadas
  FROM chatbot.unidade;
COMMIT;
