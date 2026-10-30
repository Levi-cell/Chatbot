-- Executar inteiro, uma vez por implantação, com webhook e TODOS os workers parados.
-- Não envia mensagens nem apaga histórico. Pode ser reexecutado.
-- Corte inclusivo: 29/10/2026 19:00:00 em Brasília (22:00:00 UTC).
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

LOCK TABLE chatbot.conversa, chatbot.followup_envio IN ACCESS EXCLUSIVE MODE;

-- Os envios existentes pertencem à sequência antiga de dois lembretes.
-- O DEFAULT 2 só se aplica aos novos envios, sem reclassificar o histórico.
DO $versao$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'chatbot' AND table_name = 'followup_envio'
          AND column_name = 'versao_fluxo'
    ) THEN
        ALTER TABLE chatbot.followup_envio
            ADD COLUMN versao_fluxo SMALLINT NOT NULL DEFAULT 1
            CONSTRAINT ck_followup_envio_versao CHECK (versao_fluxo IN (1, 2));
    END IF;
END $versao$;
ALTER TABLE chatbot.followup_envio ALTER COLUMN versao_fluxo SET DEFAULT 2;

ALTER TABLE chatbot.conversa
    DROP CONSTRAINT ck_conversa_motivo_encerramento,
    ADD CONSTRAINT ck_conversa_motivo_encerramento CHECK (
        motivo_encerramento IS NULL OR motivo_encerramento IN (
            'idade_invalida', 'encaminhado_suporte_idoso', 'foi_agendado',
            'followup_sem_resposta', 'atualizacao_followup',
            'titular_menor_18', 'dependente_menor_4', 'dependente_menor_5',
            'suporte_idoso_50', 'suporte_idoso_60', 'suporte_idoso_70',
            'suporte_idoso_80', 'idade_universal_90'
        )
    );

-- Só encerra as que ainda estão abertas. Preserva etapa, contador real, datas
-- dos envios, histórico e conversas já encerradas. A aplicação reconhece este
-- motivo como encerramento administrativo SEM bloqueio de 30 dias.
UPDATE chatbot.conversa
SET status_ativa = FALSE,
    finalizou_em = COALESCE(finalizou_em, clock_timestamp()),
    motivo_encerramento = 'atualizacao_followup',
    processing = FALSE,
    processing_started_at = NULL,
    lock_version = COALESCE(lock_version, 0) + 1
WHERE status_ativa IS TRUE
  AND iniciou_em <= TIMESTAMPTZ '2026-10-29 19:00:00-03:00';

COMMIT;

SELECT
    COUNT(*) FILTER (WHERE status_ativa IS TRUE
        AND iniciou_em <= TIMESTAMPTZ '2026-10-29 19:00:00-03:00') AS antigas_ainda_abertas,
    COUNT(*) FILTER (WHERE motivo_encerramento = 'atualizacao_followup') AS encerradas_na_atualizacao,
    COUNT(*) FILTER (WHERE status_ativa IS TRUE
        AND iniciou_em > TIMESTAMPTZ '2026-10-29 19:00:00-03:00') AS novas_abertas
FROM chatbot.conversa;
