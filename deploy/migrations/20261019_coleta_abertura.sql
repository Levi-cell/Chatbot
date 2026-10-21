-- Executar inteiro no DBeaver, com webhook e TODOS os workers parados.
-- Exige a migração 20261014_fireads_aba_geral_v1. Não chama serviços externos.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL COLETA ABERTURA
DO $migracao$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261014_fireads_aba_geral_v1') THEN
        RAISE EXCEPTION 'Aplicar primeiro a migração da aba geral.';
    END IF;
    LOCK TABLE chatbot.conversa, chatbot.etapa_transicao, chatbot.migracoes_fireads IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261019_coleta_abertura_v1') THEN
        RAISE NOTICE 'Coleta por campo já migrada; nenhum atendimento reprocessado.';
        RETURN;
    END IF;
    ALTER TABLE chatbot.conversa ADD COLUMN contexto_coleta JSONB NULL;
    ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_contexto_coleta CHECK (
        contexto_coleta IS NULL OR COALESCE((
            jsonb_typeof(contexto_coleta)='object'
            AND contexto_coleta->>'versao'='1'
            AND contexto_coleta->>'id_conversa'=id_conversa::text
            AND jsonb_typeof(contexto_coleta->'campos')='object'
            AND jsonb_typeof(contexto_coleta->'mensagem_original')='object'
            AND contexto_coleta->>'status' IN ('preparando','aguardando_consulta','pronto')
            AND (contexto_coleta->>'status'<>'pronto' OR contexto_coleta->>'etapa_inicial' IN ('1','2','4'))
        ), FALSE)
    );
    -- Preserva os IDs e o mapa atual. A aresta adicional só é usada com destino coletado.
    IF EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=1
               AND (evento='nome_cliente_valido_destino_coletado' OR id_etapa_destino=4)
               AND NOT (evento='nome_cliente_valido_destino_coletado' AND id_etapa_destino=4)) THEN
        RAISE EXCEPTION 'Aresta 1 -> 4 conflita com o mapa existente.';
    END IF;
    INSERT INTO chatbot.etapa_transicao(id_etapa_origem,evento,id_etapa_destino)
    VALUES (1,'nome_cliente_valido_destino_coletado',4)
    ON CONFLICT (id_etapa_origem,evento) DO NOTHING;
    INSERT INTO chatbot.migracoes_fireads(versao) VALUES ('20261019_coleta_abertura_v1');
END $migracao$;
-- FIM DDL COLETA ABERTURA

COMMIT;
SELECT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261019_coleta_abertura_v1') AS migracao_ok,
       EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=1
               AND evento='nome_cliente_valido_destino_coletado' AND id_etapa_destino=4) AS transicao_ok,
       (SELECT COUNT(*) FROM chatbot.conversa WHERE contexto_coleta IS NOT NULL) AS conversas_com_coleta;
