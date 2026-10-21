-- Executar inteiro no DBeaver com webhook e TODOS os workers parados.
-- Exige 20261009_consulta_dash_v1. Não consulta nem escreve em serviços externos.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL FIREADS ABA GERAL
DO $migracao$
DECLARE
    restricao RECORD;
    antes JSONB;
    depois JSONB;
    configuracoes JSONB;
BEGIN
    IF NOT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
                   WHERE versao='20261009_consulta_dash_v1') THEN
        RAISE EXCEPTION 'Aplicar primeiro a migração do worker_consulta_dash.';
    END IF;
    LOCK TABLE chatbot.integracao_fireads, chatbot.consulta_fireads,
        chatbot.conversa, chatbot.funil_envios, chatbot.envios_dash,
        chatbot.migracoes_fireads IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
               WHERE versao='20261014_fireads_aba_geral_v1') THEN
        RAISE NOTICE 'Aba geral já migrada; nenhum dado reprocessado.';
        RETURN;
    END IF;

    SELECT jsonb_build_object(
        'consultas',(SELECT count(*) FROM chatbot.consulta_fireads),
        'conversas',(SELECT count(*) FROM chatbot.conversa),
        'funil',(SELECT count(*) FROM chatbot.funil_envios),
        'dashboard',(SELECT count(*) FROM chatbot.envios_dash)
    ) INTO antes;
    SELECT COALESCE(jsonb_agg(jsonb_build_object(
        'id_integracao',id_integracao_fireads,'aba_google',aba_google,
        'aba_meta',aba_meta,'aba_destino',aba_destino,
        'url',url_dashbord,'fuso',fuso_formularios)), '[]'::jsonb)
    INTO configuracoes FROM chatbot.integracao_fireads;

    ALTER TABLE chatbot.migracoes_fireads ADD COLUMN IF NOT EXISTS dados JSONB;
    ALTER TABLE chatbot.funil_envios ADD COLUMN snapshot JSONB;
    ALTER TABLE chatbot.funil_envios ADD CONSTRAINT ck_funil_snapshot
        CHECK (snapshot IS NULL OR jsonb_typeof(snapshot)='object');

    -- Somente a restrição do domínio da origem; preservar a coerência com contexto.
    FOR restricao IN
        SELECT c.conname FROM pg_constraint c
        JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attname='origem_fireads'
        WHERE c.conrelid='chatbot.conversa'::regclass AND c.contype='c'
          AND c.conkey=ARRAY[a.attnum]::smallint[]
    LOOP
        EXECUTE format('ALTER TABLE chatbot.conversa DROP CONSTRAINT %I', restricao.conname);
    END LOOP;
    ALTER TABLE chatbot.conversa ALTER COLUMN origem_fireads TYPE VARCHAR(20);
    ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_origem_fireads
        CHECK (origem_fireads IN ('google','meta','organico_site','organico'));

    -- Resultados concluídos continuam intactos. A ponte distingue uma mudança
    -- real anterior da simples remoção das colunas durante este deploy.
    UPDATE chatbot.consulta_fireads q SET entrada=q.entrada || jsonb_build_object(
        'compatibilidade_aba_geral',jsonb_build_object(
            'valida',COALESCE(
                i.url_dashbord=q.entrada->>'url'
                AND i.aba_google=q.entrada->>'aba_google'
                AND i.aba_meta=q.entrada->>'aba_meta'
                AND i.fuso_formularios IS NOT DISTINCT FROM q.entrada->>'fuso', FALSE),
            'url',i.url_dashbord,'aba',i.aba_destino,'fuso',i.fuso_formularios))
    FROM chatbot.integracao_fireads i
    WHERE i.id_integracao_fireads=q.id_integracao_fireads
      AND NOT (q.entrada ? 'versao');

    -- Converter apenas pendências compatíveis. Entrada original fica auditável;
    -- prazo/IDs/tentativas não são reiniciados. A reserva anterior perde validade.
    UPDATE chatbot.consulta_fireads q SET
        entrada=jsonb_build_object('versao',2,'url',q.entrada->'url',
            'aba',q.entrada->'compatibilidade_aba_geral'->'aba',
            'fuso',q.entrada->'fuso','numero',q.entrada->'numero',
            'entrada_anterior',q.entrada),
        status='pendente',processing_started_at=NULL,reserva_ate=NULL,
        versao_reserva=versao_reserva+1,atualizado_em=clock_timestamp()
    WHERE q.status<>'concluida'
      AND q.entrada->'compatibilidade_aba_geral'->>'valida'='true'
      AND NOT (q.entrada ? 'versao');

    -- Guardar no Funil o payload já congelado; nunca produzir novo texto para
    -- uma tentativa histórica que possua snapshot no dashboard.
    UPDATE chatbot.funil_envios f SET snapshot=jsonb_build_object(
        'versao',1,'payload_funil',d.snapshot->'payload_funil',
        'canal',d.snapshot->'canal','url_funil',d.snapshot->'url_funil')
    FROM chatbot.envios_dash d WHERE d.id_conversa=f.id_conversa;

    ALTER TABLE chatbot.integracao_fireads
        DROP COLUMN aba_google RESTRICT,
        DROP COLUMN aba_meta RESTRICT;
    ALTER TABLE chatbot.integracao_fireads ADD CONSTRAINT ck_fireads_aba_leads
        CHECK (BTRIM(aba_destino)<>'');

    SELECT jsonb_build_object(
        'consultas',(SELECT count(*) FROM chatbot.consulta_fireads),
        'conversas',(SELECT count(*) FROM chatbot.conversa),
        'funil',(SELECT count(*) FROM chatbot.funil_envios),
        'dashboard',(SELECT count(*) FROM chatbot.envios_dash)
    ) INTO depois;
    IF antes IS DISTINCT FROM depois THEN
        RAISE EXCEPTION 'Contagens alteradas; migração cancelada.';
    END IF;
    IF EXISTS (SELECT 1 FROM chatbot.consulta_fireads q
               JOIN chatbot.conversa c USING (id_conversa)
               WHERE c.id_unidade<>q.id_unidade) THEN
        RAISE EXCEPTION 'Consulta vinculada a outra unidade; migração cancelada.';
    END IF;
    INSERT INTO chatbot.migracoes_fireads(versao,dados)
    VALUES ('20261014_fireads_aba_geral_v1',jsonb_build_object(
        'contagens',antes,'configuracoes_anteriores',configuracoes));
END;
$migracao$;
-- FIM DDL FIREADS ABA GERAL

SELECT
    EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
            WHERE versao='20261014_fireads_aba_geral_v1') AS migracao_ok,
    (SELECT count(*) FROM chatbot.consulta_fireads) AS consultas,
    (SELECT count(*) FROM chatbot.consulta_fireads WHERE status<>'concluida') AS pendentes,
    (SELECT count(*) FROM chatbot.envios_dash WHERE status<>'sent') AS envios_dash_pendentes;
COMMIT;
