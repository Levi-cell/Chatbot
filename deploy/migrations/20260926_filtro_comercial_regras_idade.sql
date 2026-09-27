-- Executar inteiro, com os workers parados e o Admin indisponível para edição.
-- Não altera motivos históricos, idades, elegibilidade do funil ou bloqueios.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

LOCK TABLE chatbot.unidade, chatbot.conversa IN ACCESS EXCLUSIVE MODE;

DO $validacao$
DECLARE
    unidades_invalidas TEXT;
BEGIN
    SELECT string_agg(id_unidade::TEXT, ', ' ORDER BY id_unidade)
      INTO unidades_invalidas
      FROM chatbot.unidade
     WHERE numero_comercial IS NULL
        OR NOT (regexp_replace(numero_comercial, '[^0-9]', '', 'g')
                ~ '^([0-9]{10,11}|55[0-9]{10,11})$');
    IF unidades_invalidas IS NOT NULL THEN
        RAISE EXCEPTION 'Regularize o número comercial real das unidades: %', unidades_invalidas;
    END IF;
END;
$validacao$;

-- Guardar esta saída na evidência do deploy antes de normalizar 90 -> NULL.
SELECT id_unidade, nome_unidade, idade_minima_suporte AS suporte_anterior
  FROM chatbot.unidade WHERE idade_minima_suporte = 90 ORDER BY id_unidade;

UPDATE chatbot.unidade SET idade_minima_suporte = NULL WHERE idade_minima_suporte = 90;
ALTER TABLE chatbot.unidade
    DROP CONSTRAINT ck_unidade_idade_minima_suporte,
    ADD CONSTRAINT ck_unidade_idade_minima_suporte
        CHECK (idade_minima_suporte IS NULL OR idade_minima_suporte IN (50, 60, 70, 80)),
    ALTER COLUMN numero_comercial SET NOT NULL;
ALTER TABLE chatbot.unidade DROP CONSTRAINT IF EXISTS ck_unidade_numero_comercial;
ALTER TABLE chatbot.unidade ADD CONSTRAINT ck_unidade_numero_comercial CHECK (
    regexp_replace(numero_comercial, '[^0-9]', '', 'g') ~ '^([0-9]{10,11}|55[0-9]{10,11})$'
);

ALTER TABLE chatbot.conversa
    DROP CONSTRAINT ck_conversa_motivo_encerramento,
    ADD CONSTRAINT ck_conversa_motivo_encerramento CHECK (
        motivo_encerramento IS NULL OR motivo_encerramento IN (
            'idade_invalida', 'encaminhado_suporte_idoso', 'foi_agendado', 'followup_sem_resposta',
            'titular_menor_18', 'dependente_menor_4', 'dependente_menor_5',
            'suporte_idoso_50', 'suporte_idoso_60', 'suporte_idoso_70', 'suporte_idoso_80',
            'idade_universal_90'
        )
    );

INSERT INTO chatbot.cache_controle (nome, versao, atualizado_em)
VALUES ('unidades', 1, NOW())
ON CONFLICT (nome) DO UPDATE
SET versao = chatbot.cache_controle.versao + 1, atualizado_em = NOW();

COMMIT;
