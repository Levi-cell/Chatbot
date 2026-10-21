-- Executar inteiro no DBeaver, com webhook e todos os workers parados.
-- Exige a migração FireAds de 07/10. Não consulta nem escreve no dashboard.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL CONSULTA DASH
DO $migracao$
DECLARE
    total_antes BIGINT;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
                   WHERE versao='20261007_fireads_v1') THEN
        RAISE EXCEPTION 'Aplicar primeiro a estrutura FireAds existente.';
    END IF;
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
               WHERE versao='20261009_consulta_dash_v1') THEN
        RAISE NOTICE 'Worker de consulta já migrado; nenhum dado reimportado.';
        RETURN;
    END IF;
    LOCK TABLE chatbot.consulta_fireads,chatbot.conversa IN ACCESS EXCLUSIVE MODE;
    SELECT count(*) INTO total_antes FROM chatbot.consulta_fireads;

    -- DROP COLUMN elimina somente constraints locais que usam id_chat.
    -- A FK composta da conversa é substituída abaixo, sem CASCADE de objetos.
    ALTER TABLE chatbot.consulta_fireads DROP COLUMN id_chat;
    ALTER TABLE chatbot.consulta_fireads RENAME COLUMN id_conversa_referencia TO id_conversa;
    ALTER TABLE chatbot.consulta_fireads
        ADD CONSTRAINT uq_consulta_fireads_conversa UNIQUE (id_conversa),
        ADD CONSTRAINT fk_consulta_fireads_conversa_unidade
            FOREIGN KEY (id_conversa,id_unidade)
            REFERENCES chatbot.conversa(id_conversa,id_unidade) ON DELETE CASCADE,
        ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'pendente',
        ADD COLUMN entrada JSONB,
        ADD COLUMN solicitado_em TIMESTAMPTZ NOT NULL DEFAULT now(),
        ADD COLUMN prazo_final TIMESTAMPTZ NOT NULL DEFAULT (now()+INTERVAL '300 seconds'),
        ADD COLUMN tentativas INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN versao_reserva BIGINT NOT NULL DEFAULT 0,
        ADD COLUMN processing_started_at TIMESTAMPTZ,
        ADD COLUMN reserva_ate TIMESTAMPTZ,
        ADD COLUMN aplicacao JSONB,
        ADD COLUMN aplicado_em TIMESTAMPTZ,
        ADD COLUMN ultimo_erro TEXT;

    -- Preserva IDs, resultado e conteúdo antigo. Dados legados passam a um
    -- envelope; não inventar linhas de formulário que não foram armazenadas.
    UPDATE chatbot.consulta_fireads q SET
        status=CASE WHEN q.consulta_concluida THEN 'concluida' ELSE 'pendente' END,
        entrada=jsonb_build_object('url',i.url_dashbord,'aba_google',i.aba_google,
            'aba_meta',i.aba_meta,'fuso',i.fuso_formularios,'numero',cl.waid_telefone,
            'migrada',true),
        solicitado_em=COALESCE(q.consultado_em,q.atualizado_em),
        prazo_final=COALESCE(q.consultado_em,q.atualizado_em)+INTERVAL '300 seconds',
        dados=CASE WHEN q.dados IS NOT NULL
            THEN jsonb_build_object('decisao',q.dados,'fontes','{}'::jsonb,'legado',true)
            ELSE NULL END,
        aplicacao=CASE WHEN q.consulta_concluida THEN c.contexto_fireads END,
        aplicado_em=CASE WHEN q.consulta_concluida AND c.contexto_fireads IS NOT NULL
            THEN COALESCE(q.consultado_em,q.atualizado_em) END
    FROM chatbot.conversa c,chatbot.cliente cl,chatbot.integracao_fireads i
    WHERE c.id_conversa=q.id_conversa AND cl.id_cliente=c.id_cliente
      AND i.id_integracao_fireads=q.id_integracao_fireads;

    ALTER TABLE chatbot.consulta_fireads
        ALTER COLUMN entrada SET NOT NULL,
        ADD CONSTRAINT ck_consulta_entrada CHECK (jsonb_typeof(entrada)='object'),
        ADD CONSTRAINT ck_consulta_status CHECK (status IN ('pendente','processando','concluida')),
        ADD CONSTRAINT ck_consulta_conclusao CHECK ((status='concluida')=consulta_concluida),
        ADD CONSTRAINT ck_consulta_reserva CHECK (
            (status='processando' AND processing_started_at IS NOT NULL AND reserva_ate IS NOT NULL)
            OR (status<>'processando' AND processing_started_at IS NULL AND reserva_ate IS NULL)),
        ADD CONSTRAINT ck_consulta_tentativas CHECK (tentativas>=0 AND versao_reserva>=0),
        ADD CONSTRAINT ck_consulta_aplicacao CHECK (
            (aplicacao IS NULL AND aplicado_em IS NULL)
            OR (aplicacao IS NOT NULL AND aplicado_em IS NOT NULL AND consulta_concluida)),
        ADD CONSTRAINT ck_consulta_prazo CHECK (prazo_final>=solicitado_em);

    CREATE INDEX idx_consulta_fireads_pendentes
        ON chatbot.consulta_fireads(solicitado_em,id_consulta) WHERE status<>'concluida';

    IF (SELECT count(*) FROM chatbot.consulta_fireads)<>total_antes THEN
        RAISE EXCEPTION 'Quantidade de consultas alterada; migração cancelada.';
    END IF;
    INSERT INTO chatbot.migracoes_fireads(versao) VALUES ('20261009_consulta_dash_v1');
END;
$migracao$;
-- FIM DDL CONSULTA DASH

SELECT
    EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
            WHERE versao='20261009_consulta_dash_v1') AS migracao_ok,
    (SELECT count(*) FROM chatbot.consulta_fireads) AS consultas,
    (SELECT count(*) FROM chatbot.consulta_fireads WHERE status<>'concluida') AS pendentes,
    (SELECT count(*) FROM chatbot.consulta_fireads q JOIN chatbot.conversa c USING (id_conversa)
     WHERE q.id_unidade<>c.id_unidade) AS vinculos_invalidos;
COMMIT;
