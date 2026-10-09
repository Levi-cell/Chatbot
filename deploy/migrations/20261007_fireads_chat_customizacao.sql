-- FireAds: executar inteiro no DBeaver, com workers/webhook parados.
-- Não habilita a integração nem modifica dados no dashboard.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

-- INICIO DDL FIREADS
CREATE TABLE IF NOT EXISTS chatbot.migracoes_fireads (
    versao TEXT PRIMARY KEY, aplicada_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

DO $migracao$
DECLARE
    quantidade_conversas BIGINT;
    quantidade_clientes BIGINT;
    quantidade_unidades BIGINT;
BEGIN
    IF EXISTS (SELECT 1 FROM chatbot.migracoes_fireads WHERE versao='20261007_fireads_v1') THEN
        RAISE NOTICE 'Migração FireAds já aplicada; nenhum dado reimportado.';
        RETURN;
    END IF;

    LOCK TABLE chatbot.unidade, chatbot.cliente, chatbot.conversa,
               chatbot.etapa, chatbot.etapa_transicao IN ACCESS EXCLUSIVE MODE;
    SELECT COUNT(*) INTO quantidade_conversas FROM chatbot.conversa;
    SELECT COUNT(*) INTO quantidade_clientes FROM chatbot.cliente;
    SELECT COUNT(*) INTO quantidade_unidades FROM chatbot.unidade;
    IF (SELECT COUNT(*) FROM chatbot.etapa) <> 24
       OR NOT EXISTS (SELECT 1 FROM information_schema.columns
          WHERE table_schema='chatbot' AND table_name='conversa' AND column_name='turno')
       OR NOT EXISTS (SELECT 1 FROM chatbot.etapa_transicao
          WHERE id_etapa_origem=17 AND evento='triagem_concluida_sem_link' AND id_etapa_destino=18)
    THEN
        RAISE EXCEPTION 'Base incompatível: exige catálogo de 24 etapas e rota sem link já aplicada.';
    END IF;

    CREATE TABLE chatbot.atendimento_customizado (
        id_customizacao SERIAL PRIMARY KEY,
        id_unidade INTEGER NOT NULL UNIQUE REFERENCES chatbot.unidade(id_unidade) ON DELETE CASCADE,
        nome_agente VARCHAR(100) NOT NULL CHECK (nome_agente ~ '[^[:space:]]'),
        genero VARCHAR(9) NOT NULL CHECK (genero IN ('masculino','feminino')),
        numero_comercial VARCHAR(30) NOT NULL CHECK (
            regexp_replace(numero_comercial,'[^0-9]','','g') ~ '^([0-9]{10,11}|55[0-9]{10,11})$'),
        idade_minima_suporte INTEGER CHECK (idade_minima_suporte IN (50,60,70,80)),
        email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
        link_agendamento VARCHAR(400) UNIQUE,
        link_instagram VARCHAR(400),
        bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE
    );
    INSERT INTO chatbot.atendimento_customizado
      (id_unidade,nome_agente,genero,numero_comercial,idade_minima_suporte,
       email_obrigatorio,link_agendamento,link_instagram,bpa_ativo)
    SELECT id_unidade,nome_agente,genero,numero_comercial,idade_minima_suporte,
           email_obrigatorio,link_agendamento,link_instagram,bpa_ativo FROM chatbot.unidade;
    IF EXISTS (
        SELECT id_unidade,nome_agente,genero,numero_comercial,idade_minima_suporte,
               email_obrigatorio,link_agendamento,link_instagram,bpa_ativo FROM chatbot.unidade
        EXCEPT
        SELECT id_unidade,nome_agente,genero,numero_comercial,idade_minima_suporte,
               email_obrigatorio,link_agendamento,link_instagram,bpa_ativo FROM chatbot.atendimento_customizado
    ) OR (SELECT COUNT(*) FROM chatbot.atendimento_customizado) <> quantidade_unidades THEN
        RAISE EXCEPTION 'Cópia de personalização divergente; migração abortada.';
    END IF;
    ALTER TABLE chatbot.unidade
        DROP COLUMN nome_agente, DROP COLUMN genero, DROP COLUMN numero_comercial,
        DROP COLUMN idade_minima_suporte, DROP COLUMN email_obrigatorio,
        DROP COLUMN link_agendamento, DROP COLUMN link_instagram, DROP COLUMN bpa_ativo;

    CREATE TABLE chatbot.chat (
        id_chat BIGSERIAL PRIMARY KEY,
        id_cliente INTEGER NOT NULL REFERENCES chatbot.cliente(id_cliente) ON DELETE CASCADE,
        id_unidade INTEGER NOT NULL REFERENCES chatbot.unidade(id_unidade) ON DELETE CASCADE,
        criado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        CONSTRAINT uq_chat_cliente_unidade UNIQUE (id_cliente,id_unidade),
        CONSTRAINT uq_chat_identidade UNIQUE (id_chat,id_cliente,id_unidade),
        CONSTRAINT uq_chat_unidade UNIQUE (id_chat,id_unidade)
    );
    INSERT INTO chatbot.chat (id_cliente,id_unidade,criado_em)
    SELECT id_cliente,id_unidade,MIN(iniciou_em) FROM chatbot.conversa GROUP BY id_cliente,id_unidade;
    ALTER TABLE chatbot.conversa ADD COLUMN id_chat BIGINT;
    UPDATE chatbot.conversa c SET id_chat=h.id_chat FROM chatbot.chat h
        WHERE h.id_cliente=c.id_cliente AND h.id_unidade=c.id_unidade;
    ALTER TABLE chatbot.conversa
        ALTER COLUMN id_chat SET NOT NULL,
        ADD CONSTRAINT fk_conversa_chat FOREIGN KEY (id_chat,id_cliente,id_unidade)
            REFERENCES chatbot.chat(id_chat,id_cliente,id_unidade) ON DELETE CASCADE,
        ADD CONSTRAINT uq_conversa_chat_unidade UNIQUE (id_conversa,id_chat,id_unidade),
        ADD CONSTRAINT uq_conversa_unidade UNIQUE (id_conversa,id_unidade),
        ADD COLUMN origem_fireads VARCHAR(10) CHECK (origem_fireads IN ('google','meta','organico')),
        ADD COLUMN contexto_fireads JSONB,
        ADD COLUMN lead_no_dash BOOLEAN DEFAULT NULL,
        ADD CONSTRAINT ck_conversa_fireads CHECK (
            (origem_fireads IS NULL AND contexto_fireads IS NULL)
            OR (origem_fireads IS NOT NULL AND contexto_fireads IS NOT NULL
                AND jsonb_typeof(contexto_fireads)='object'
                AND contexto_fireads->>'origem' IS NOT DISTINCT FROM origem_fireads
                AND contexto_fireads->>'id_conversa' IS NOT DISTINCT FROM id_conversa::text
                AND contexto_fireads->>'concluida' IS NOT DISTINCT FROM 'true'));
    CREATE INDEX idx_conversa_chat ON chatbot.conversa(id_chat,iniciou_em DESC);

    CREATE TABLE chatbot.integracao_fireads (
        id_integracao_fireads SERIAL PRIMARY KEY,
        id_unidade INTEGER NOT NULL UNIQUE REFERENCES chatbot.unidade(id_unidade) ON DELETE CASCADE,
        integracao_ativa BOOLEAN NOT NULL DEFAULT FALSE,
        url_dashbord VARCHAR(1000) NOT NULL CHECK (url_dashbord ~ '^https://script[.]google[.]com/macros/s/[^/]+/exec$'),
        url_operation VARCHAR(1000),
        aba_google VARCHAR(200) NOT NULL DEFAULT 'Leads Google Ads (NÃO EDITAR)',
        aba_meta VARCHAR(200) NOT NULL DEFAULT '[FIRE] Leads Ads Geral - 7.2',
        aba_destino VARCHAR(200) NOT NULL DEFAULT 'LEADS GERAL - Feedback',
        fuso_formularios VARCHAR(100),
        contrato_validado BOOLEAN NOT NULL DEFAULT FALSE,
        ativada_em TIMESTAMPTZ,
        criado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        CONSTRAINT uq_integracao_fireads_unidade UNIQUE (id_integracao_fireads,id_unidade),
        CHECK (NOT integracao_ativa OR (contrato_validado AND ativada_em IS NOT NULL)),
        CHECK (BTRIM(aba_google)<>'' AND BTRIM(aba_meta)<>'' AND BTRIM(aba_destino)<>''
            AND aba_google<>aba_meta AND aba_google<>aba_destino AND aba_meta<>aba_destino)
    );
    CREATE TABLE chatbot.consulta_fireads (
        id_consulta BIGSERIAL PRIMARY KEY,
        id_chat BIGINT NOT NULL UNIQUE,
        id_unidade INTEGER NOT NULL,
        id_integracao_fireads INTEGER NOT NULL,
        id_conversa_referencia INTEGER NOT NULL,
        consulta_concluida BOOLEAN NOT NULL DEFAULT FALSE,
        resultado VARCHAR(30) NOT NULL DEFAULT 'pendente'
            CHECK (resultado IN ('pendente','importado','ausente','incompleto','ambiguidade','erro')),
        dados JSONB,
        consultado_em TIMESTAMPTZ,
        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY (id_chat,id_unidade) REFERENCES chatbot.chat(id_chat,id_unidade) ON DELETE CASCADE,
        FOREIGN KEY (id_integracao_fireads,id_unidade)
            REFERENCES chatbot.integracao_fireads(id_integracao_fireads,id_unidade),
        FOREIGN KEY (id_conversa_referencia,id_chat,id_unidade)
            REFERENCES chatbot.conversa(id_conversa,id_chat,id_unidade) ON DELETE CASCADE,
        CHECK ((NOT consulta_concluida AND resultado='pendente' AND dados IS NULL AND consultado_em IS NULL)
            OR (consulta_concluida AND resultado<>'pendente' AND dados IS NOT NULL AND consultado_em IS NOT NULL))
    );
    CREATE TABLE chatbot.envios_dash (
        id_envio_dash BIGSERIAL PRIMARY KEY,
        id_conversa INTEGER NOT NULL UNIQUE,
        id_unidade INTEGER NOT NULL,
        id_integracao_fireads INTEGER NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','sent')),
        attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count>=0),
        next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        processing_started_at TIMESTAMPTZ,
        enviado_em TIMESTAMPTZ,
        ultimo_erro TEXT,
        recibo JSONB,
        snapshot JSONB NOT NULL CHECK (jsonb_typeof(snapshot)='object'),
        criado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        atualizado_em TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
        FOREIGN KEY (id_conversa,id_unidade) REFERENCES chatbot.conversa(id_conversa,id_unidade) ON DELETE CASCADE,
        FOREIGN KEY (id_integracao_fireads,id_unidade)
            REFERENCES chatbot.integracao_fireads(id_integracao_fireads,id_unidade),
        CHECK ((status='processing')=(processing_started_at IS NOT NULL)),
        CHECK ((status='sent')=(enviado_em IS NOT NULL))
    );
    CREATE INDEX idx_envios_dash_pendentes ON chatbot.envios_dash(status,next_attempt_at,attempt_count)
        WHERE status<>'sent';

    -- A configuração é cadastrada DESATIVADA pelo Admin após conferir a unidade.
    -- Não inferir qual ID é Santo André nem habilitar importação retroativa.
    INSERT INTO chatbot.etapa_transicao (id_etapa_origem,evento,id_etapa_destino)
    VALUES (7,'oferta_aceita_email_fireads',11),(9,'retorno_confirmado_email_fireads',11)
    ON CONFLICT (id_etapa_origem,evento) DO NOTHING;
    IF NOT EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=7 AND evento='oferta_aceita_email_fireads' AND id_etapa_destino=11)
       OR NOT EXISTS (SELECT 1 FROM chatbot.etapa_transicao WHERE id_etapa_origem=9 AND evento='retorno_confirmado_email_fireads' AND id_etapa_destino=11)
       OR (SELECT COUNT(*) FROM chatbot.etapa_transicao)<>30 THEN
        RAISE EXCEPTION 'Mapa divergente: esperado catálogo de 30 transições.';
    END IF;
    IF (SELECT COUNT(*) FROM chatbot.conversa)<>quantidade_conversas
       OR (SELECT COUNT(*) FROM chatbot.cliente)<>quantidade_clientes
       OR (SELECT COUNT(*) FROM chatbot.unidade)<>quantidade_unidades
       OR EXISTS (SELECT 1 FROM chatbot.conversa WHERE id_chat IS NULL) THEN
        RAISE EXCEPTION 'Contagens ou vínculos divergentes; nenhuma alteração será confirmada.';
    END IF;
    INSERT INTO chatbot.migracoes_fireads(versao) VALUES ('20261007_fireads_v1');
END;
$migracao$;

-- As leituras atuais unem unidade e atendimento_customizado diretamente.
-- Instalações/reexecuções não criam a antiga view. Para removê-la de uma base
-- já implantada, usar 20261009_remover_view_unidade_atendimento.sql no deploy.

CREATE OR REPLACE FUNCTION chatbot.verificar_customizacao_unidade() RETURNS TRIGGER
LANGUAGE plpgsql AS $fn$
DECLARE uid INTEGER;
BEGIN
    IF TG_TABLE_NAME='unidade' THEN uid=NEW.id_unidade; ELSE uid=OLD.id_unidade; END IF;
    IF EXISTS (SELECT 1 FROM chatbot.unidade WHERE id_unidade=uid)
       AND NOT EXISTS (SELECT 1 FROM chatbot.atendimento_customizado WHERE id_unidade=uid) THEN
        RAISE EXCEPTION 'Unidade % precisa de exatamente um atendimento_customizado.',uid;
    END IF;
    RETURN NULL;
END;
$fn$;
DROP TRIGGER IF EXISTS unidade_exige_customizacao ON chatbot.unidade;
CREATE CONSTRAINT TRIGGER unidade_exige_customizacao AFTER INSERT ON chatbot.unidade
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chatbot.verificar_customizacao_unidade();
DROP TRIGGER IF EXISTS customizacao_nao_orfa ON chatbot.atendimento_customizado;
CREATE CONSTRAINT TRIGGER customizacao_nao_orfa AFTER DELETE OR UPDATE ON chatbot.atendimento_customizado
    DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION chatbot.verificar_customizacao_unidade();

CREATE OR REPLACE FUNCTION chatbot.marcar_ativacao_fireads() RETURNS TRIGGER
LANGUAGE plpgsql AS $fn$
BEGIN
    IF NEW.fuso_formularios IS NOT NULL AND NOT EXISTS
        (SELECT 1 FROM pg_timezone_names WHERE name=NEW.fuso_formularios) THEN
        RAISE EXCEPTION 'Fuso de leitura FireAds desconhecido.';
    END IF;
    IF NEW.integracao_ativa THEN
        IF TG_OP='INSERT' THEN NEW.ativada_em=clock_timestamp();
        ELSIF NOT OLD.integracao_ativa THEN NEW.ativada_em=clock_timestamp();
        ELSE NEW.ativada_em=OLD.ativada_em;
        END IF;
    END IF;
    NEW.atualizado_em=clock_timestamp();
    RETURN NEW;
END;
$fn$;
DROP TRIGGER IF EXISTS integracao_fireads_ativacao ON chatbot.integracao_fireads;
CREATE TRIGGER integracao_fireads_ativacao BEFORE INSERT OR UPDATE ON chatbot.integracao_fireads
    FOR EACH ROW EXECUTE FUNCTION chatbot.marcar_ativacao_fireads();
-- FIM DDL FIREADS

SELECT (SELECT COUNT(*) FROM chatbot.unidade) AS unidades,
       (SELECT COUNT(*) FROM chatbot.atendimento_customizado) AS customizacoes,
       (SELECT COUNT(*) FROM chatbot.chat) AS chats,
       (SELECT COUNT(*) FROM chatbot.conversa WHERE id_chat IS NULL) AS conversas_sem_chat,
       (SELECT COUNT(*) FROM chatbot.etapa_transicao) AS transicoes,
       (SELECT COUNT(*) FROM chatbot.integracao_fireads WHERE integracao_ativa) AS fireads_ativas;
COMMIT;
