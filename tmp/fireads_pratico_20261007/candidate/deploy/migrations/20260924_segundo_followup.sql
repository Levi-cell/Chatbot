-- Executar o arquivo inteiro antes de iniciar os workers da nova versão.
-- Apenas amplia o motivo de encerramento. Não fecha nem altera conversas existentes.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

ALTER TABLE chatbot.conversa
    DROP CONSTRAINT ck_conversa_motivo_encerramento,
    ADD CONSTRAINT ck_conversa_motivo_encerramento CHECK (
        motivo_encerramento IS NULL OR motivo_encerramento IN (
            'idade_invalida',
            'foi_agendado',
            'encaminhado_suporte_idoso',
            'followup_sem_resposta'
        )
    );

COMMIT;
