-- Alternativa isolada: a remoção já está incluída no SQL unificado
-- 20261009_status_pagamento_workers.sql. Não é necessário executar os dois.
-- Executar inteiro no próximo deploy, com webhook/workers parados e código
-- atualizado para consultar unidade e atendimento_customizado diretamente.
-- Remove apenas a view antiga; não altera tabelas, colunas ou registros.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- RESTRICT impede a remoção de outros objetos que ainda dependam da view.
DROP VIEW IF EXISTS chatbot.unidade_atendimento RESTRICT;

COMMIT;
