-- Recuo compatível do schema, sem apagar os motivos novos já gravados.
-- Parar workers e impedir edição no Admin antes de reverter código/schema.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';
LOCK TABLE chatbot.unidade IN ACCESS EXCLUSIVE MODE;
ALTER TABLE chatbot.unidade
    DROP CONSTRAINT ck_unidade_idade_minima_suporte,
    ADD CONSTRAINT ck_unidade_idade_minima_suporte CHECK (
        idade_minima_suporte IS NULL OR idade_minima_suporte IN (50, 60, 70, 80, 90)
    ),
    DROP CONSTRAINT IF EXISTS ck_unidade_numero_comercial,
    ALTER COLUMN numero_comercial DROP NOT NULL;
-- Não restaurar automaticamente NULL -> 90: pode ter havido edição legítima.
-- A restrição ampliada de motivos é mantida para preservar os dados novos.
INSERT INTO chatbot.cache_controle (nome, versao, atualizado_em)
VALUES ('unidades', 1, NOW())
ON CONFLICT (nome) DO UPDATE
SET versao = chatbot.cache_controle.versao + 1, atualizado_em = NOW();
COMMIT;
