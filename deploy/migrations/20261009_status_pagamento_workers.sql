-- Pausa por status_pagamento e remoção da view unidade_atendimento.
-- Executar inteiro com webhook/workers parados e código atualizado
-- para consultar unidade e atendimento_customizado diretamente.
-- Preserva cadastros, histórico, pendências e configurações de pagamento atuais.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

CREATE OR REPLACE FUNCTION chatbot.dequeue_message()
RETURNS TABLE (
    id_mensagem INT,
    cliente_telefone VARCHAR,
    conteudo_texto TEXT,
    tipo_mensagem VARCHAR,
    id_phone_unidade VARCHAR,
    unidade_telefone VARCHAR,
    received_data_hora TIMESTAMPTZ,
    id_hash_msg VARCHAR,
    retry_count INT
)
LANGUAGE plpgsql
AS $$

BEGIN
    RETURN QUERY

    WITH next_job AS (
        SELECT f.id_mensagem
        FROM chatbot.fila_mensagens f
        WHERE (
            (
                f.status = 'pending'
                AND f.next_attempt_at <= NOW()
            )
            OR
            (
                f.status = 'processing'
                AND f.processing_started_at
                    < NOW() - INTERVAL '2 minutes'
            )
        )
        -- Inativas mantêm as mensagens pendentes, sem consumir retries.
        AND NOT EXISTS (
            SELECT 1 FROM chatbot.unidade u
            WHERE u.phone_number_id = f.id_phone_unidade
              AND u.status_pagamento IS NOT TRUE
        )
        ORDER BY
            CASE
                WHEN f.status = 'pending' THEN f.next_attempt_at
                WHEN f.status = 'processing'
                    THEN f.processing_started_at
            END NULLS FIRST,
            f.id_mensagem
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )

    UPDATE chatbot.fila_mensagens f
    SET
        status = 'processing',
        retry_count = f.retry_count + 1,
        processing_started_at = NOW()
    FROM next_job
    WHERE f.id_mensagem = next_job.id_mensagem

    RETURNING
        f.id_mensagem,
        f.cliente_telefone,
        f.conteudo_texto,
        f.tipo_mensagem,
        f.id_phone_unidade,
        f.unidade_telefone,
        f.received_data_hora,
        f.id_hash_msg,
        f.retry_count;
END;

$$;

-- Remove somente a view. As tabelas e seus dados são preservados.
-- RESTRICT impede a remoção de outros objetos que ainda dependam dela.
DROP VIEW IF EXISTS chatbot.unidade_atendimento RESTRICT;

COMMIT;
