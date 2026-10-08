-- Aplicação manual única, com flow parado e follow-up desligado. Não executa envios.
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $dependencias$
BEGIN
    IF TO_REGCLASS('chatbot.conversa') IS NULL
       OR TO_REGCLASS('chatbot.historico_mensagens') IS NULL
       OR TO_REGCLASS('chatbot.etapa') IS NULL THEN
        RAISE EXCEPTION 'Dependencias de followup ausentes';
    END IF;
END
$dependencias$;

-- Estabiliza o conjunto legado enquanto ele é registrado e marcado.
LOCK TABLE chatbot.conversa IN SHARE ROW EXCLUSIVE MODE;
DO $integridade_legado$
BEGIN
    IF EXISTS (
        SELECT 1 FROM chatbot.conversa c
        LEFT JOIN chatbot.etapa e ON e.id_etapa = c.id_etapa_atual
        WHERE c.status_ativa IS TRUE AND (
            c.finalizou_em IS NOT NULL OR e.id_etapa IS NULL
            OR c.id_etapa_atual NOT BETWEEN 1 AND 21
            OR e.encerra_automaticamente IS TRUE
        )
    ) THEN
        RAISE EXCEPTION 'Conversa ativa inconsistente ou terminal; concluir a recuperacao do flow antes de migrar';
    END IF;
END
$integridade_legado$;

CREATE TABLE chatbot.followup_envio (
    id_conversa INTEGER NOT NULL REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    id_ancora INTEGER NOT NULL,
    ancora_em TIMESTAMPTZ NOT NULL,
    id_historico_bot INTEGER NOT NULL,
    enviado_em TIMESTAMPTZ NOT NULL,
    id_hash_msg VARCHAR(255) NOT NULL,
    PRIMARY KEY (id_conversa, id_ancora, ancora_em),
    UNIQUE (id_conversa, id_historico_bot, enviado_em)
);

CREATE TABLE chatbot.followup_retomada (
    id_conversa INTEGER NOT NULL REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    id_mensagem_fila INTEGER NOT NULL,
    id_hash_cliente VARCHAR(255) NOT NULL,
    id_etapa INTEGER NOT NULL REFERENCES chatbot.etapa(id_etapa),
    stage_anterior INTEGER NOT NULL CHECK (stage_anterior > 0),
    followup_em TIMESTAMPTZ,
    registrada_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    concluida_em TIMESTAMPTZ,
    PRIMARY KEY (id_conversa, id_mensagem_fila, id_hash_cliente)
);

CREATE INDEX idx_followup_retomada_aberta ON chatbot.followup_retomada(id_conversa)
WHERE concluida_em IS NULL;

CREATE TABLE chatbot.followup_legado (
    id_conversa INTEGER PRIMARY KEY REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    stage_anterior INTEGER,
    marcada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO chatbot.followup_legado (id_conversa, stage_anterior)
SELECT id_conversa, followup_stage FROM chatbot.conversa WHERE status_ativa IS TRUE;

-- Marca também etapas 18–21 para retomada reativa; elas nunca recebem proativo.
-- Preserva etapa, histórico, finalização, última interação e last_sent_at.
UPDATE chatbot.conversa c
SET followup_stage = 1
FROM chatbot.followup_legado l
WHERE c.id_conversa = l.id_conversa;

SELECT COUNT(*) AS conversas_ativas_marcadas FROM chatbot.followup_legado;

COMMIT;
