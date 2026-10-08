-- Executar o script inteiro. Não envia mensagens nem consulta a Meta.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

-- INICIO DDL CONSUMO META
ALTER TABLE chatbot.unidade
    ADD COLUMN IF NOT EXISTS id_fuso INTEGER NULL,
    ADD COLUMN IF NOT EXISTS nome_fuso TEXT NULL,
    ADD COLUMN IF NOT EXISTS fuso_verificado_em TIMESTAMPTZ NULL;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conrelid = 'chatbot.unidade'::regclass
                     AND conname = 'ck_unidade_fuso_meta') THEN
        ALTER TABLE chatbot.unidade ADD CONSTRAINT ck_unidade_fuso_meta CHECK (
            (id_fuso IS NULL AND nome_fuso IS NULL)
            OR (id_fuso IS NOT NULL AND id_fuso > 0 AND nome_fuso IS NOT NULL
                AND length(trim(nome_fuso)) > 0)
        );
    END IF;
END $$;

CREATE TABLE IF NOT EXISTS chatbot.consumo_mensal_meta (
    id_registro BIGSERIAL PRIMARY KEY,
    id_unidade INTEGER NOT NULL REFERENCES chatbot.unidade(id_unidade) ON DELETE RESTRICT,
    mes_referencia DATE NOT NULL,
    waba_id VARCHAR(100) NOT NULL,
    phone_number_id VARCHAR(100) NOT NULL,
    timezone_id INTEGER NOT NULL CHECK (timezone_id > 0),
    fuso_horario TEXT NOT NULL CHECK (length(trim(fuso_horario)) > 0),
    data_hora_inicio TIMESTAMPTZ NOT NULL,
    data_hora_fim TIMESTAMPTZ NOT NULL,
    qtd_janela_gratuita BIGINT NOT NULL CHECK (qtd_janela_gratuita >= 0),
    qtd_franquia_consumida BIGINT NOT NULL CHECK (qtd_franquia_consumida >= 0),
    qtd_cobradas_meta BIGINT NOT NULL CHECK (qtd_cobradas_meta >= 0),
    franquia_meta_mensal INTEGER NOT NULL DEFAULT 1000 CHECK (franquia_meta_mensal >= 0),
    beneficio_esl_mensal INTEGER NOT NULL DEFAULT 1000 CHECK (beneficio_esl_mensal >= 0),
    tarifa_referencia_brl NUMERIC(12,6) NOT NULL DEFAULT 0.035 CHECK (tarifa_referencia_brl >= 0),
    tarifa_vigencia DATE NOT NULL DEFAULT '2026-10-01',
    consultado_ate TIMESTAMPTZ NOT NULL,
    ultimo_sucesso_em TIMESTAMPTZ NOT NULL,
    status_apuracao VARCHAR(20) NOT NULL,
    data_proxima_consolidacao DATE,
    consolidado_em TIMESTAMPTZ,
    ultima_decisao_consolidacao_em TIMESTAMPTZ,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_consumo_unidade_mes UNIQUE (id_unidade, mes_referencia),
    CONSTRAINT ck_consumo_mes CHECK (extract(day FROM mes_referencia) = 1
                                   AND mes_referencia >= DATE '2026-10-01'),
    CONSTRAINT ck_consumo_fronteiras CHECK (data_hora_inicio < data_hora_fim
        AND consultado_ate > data_hora_inicio AND consultado_ate <= data_hora_fim),
    CONSTRAINT ck_consumo_franquia CHECK (qtd_franquia_consumida <= franquia_meta_mensal),
    CONSTRAINT ck_consumo_estado CHECK (
        (status_apuracao IN ('em_andamento', 'em_conferencia')
            AND consolidado_em IS NULL AND data_proxima_consolidacao IS NOT NULL
            AND extract(day FROM data_proxima_consolidacao) = 25
            AND data_proxima_consolidacao > mes_referencia)
        OR (status_apuracao = 'consolidado' AND consolidado_em IS NOT NULL
            AND data_proxima_consolidacao IS NULL AND ultima_decisao_consolidacao_em IS NOT NULL
            AND consultado_ate = data_hora_fim)
    )
);

-- Agenda separada permite registrar falhas mesmo antes da primeira coleta válida.
-- 'conta' controla a leitura de fuso; AAAA-MM controla cada período, isoladamente.
CREATE TABLE IF NOT EXISTS chatbot.consumo_meta_coletas (
    id_unidade INTEGER NOT NULL REFERENCES chatbot.unidade(id_unidade) ON DELETE RESTRICT,
    periodo VARCHAR(7) NOT NULL CHECK (periodo = 'conta' OR periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'),
    proxima_consulta_em TIMESTAMPTZ NOT NULL,
    ultima_tentativa_em TIMESTAMPTZ,
    ultimo_erro TEXT,
    falhas_consecutivas INTEGER NOT NULL DEFAULT 0 CHECK (falhas_consecutivas >= 0),
    PRIMARY KEY (id_unidade, periodo)
);
CREATE INDEX IF NOT EXISTS idx_consumo_meta_coletas_agenda
    ON chatbot.consumo_meta_coletas (proxima_consulta_em, id_unidade);
CREATE INDEX IF NOT EXISTS idx_consumo_meta_pendentes
    ON chatbot.consumo_mensal_meta (id_unidade, mes_referencia)
    WHERE status_apuracao <> 'consolidado';
-- FIM DDL CONSUMO META

COMMIT;
