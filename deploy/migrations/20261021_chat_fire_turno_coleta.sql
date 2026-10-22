-- Executar inteiro no DBeaver, com webhook e TODOS os workers parados.
-- Aplicar depois de 20261019_coleta_abertura.sql. Não altera atendimentos salvos.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL CHAT FIRE TURNO
DO $migracao$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
                   WHERE versao='20261019_coleta_abertura_v1') THEN
        RAISE EXCEPTION 'Aplicar primeiro a migração da coleta por campo.';
    END IF;
    LOCK TABLE chatbot.conversa, chatbot.etapa_transicao, chatbot.migracoes_fireads
        IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
               WHERE versao='20261021_chat_fire_turno_coleta_v1') THEN
        RAISE NOTICE 'Chat Fire e turno antecipado já migrados.';
        RETURN;
    END IF;

    ALTER TABLE chatbot.conversa DROP CONSTRAINT ck_conversa_origem_fireads;
    ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_origem_fireads
        CHECK (origem_fireads IN ('google','meta','organico_site','chat_fire','organico'));

    ALTER TABLE chatbot.conversa ALTER COLUMN turno TYPE VARCHAR(6);
    ALTER TABLE chatbot.conversa DROP CONSTRAINT ck_conversa_turno;
    ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_turno
        CHECK (turno IS NULL OR turno IN ('manha','tarde','noite','sabado'));

    IF EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=17
               AND (evento='triagem_concluida_turno_coletado' OR id_etapa_destino=19)
               AND NOT (evento='triagem_concluida_turno_coletado' AND id_etapa_destino=19)) THEN
        RAISE EXCEPTION 'Aresta 17 -> 19 conflita com o mapa existente.';
    END IF;
    INSERT INTO chatbot.etapa_transicao(id_etapa_origem,evento,id_etapa_destino)
    VALUES (17,'triagem_concluida_turno_coletado',19)
    ON CONFLICT (id_etapa_origem,evento) DO NOTHING;
    INSERT INTO chatbot.migracoes_fireads(versao) VALUES ('20261021_chat_fire_turno_coleta_v1');
END $migracao$;
-- FIM DDL CHAT FIRE TURNO

COMMIT;
SELECT EXISTS (SELECT 1 FROM chatbot.migracoes_fireads
               WHERE versao='20261021_chat_fire_turno_coleta_v1') AS migracao_ok,
       EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=17
               AND evento='triagem_concluida_turno_coletado' AND id_etapa_destino=19) AS transicao_ok,
       (SELECT character_maximum_length FROM information_schema.columns
        WHERE table_schema='chatbot' AND table_name='conversa' AND column_name='turno') AS tamanho_turno;
