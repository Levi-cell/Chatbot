"""DDL canônico de instalação limpa; migração incremental fica em deploy/migrations."""

DDL_FOLLOWUP = """

CREATE TABLE IF NOT EXISTS chatbot.followup_envio (
    id_conversa INTEGER NOT NULL REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    id_ancora INTEGER NOT NULL,
    ancora_em TIMESTAMPTZ NOT NULL,
    id_historico_bot INTEGER NOT NULL,
    enviado_em TIMESTAMPTZ NOT NULL,
    id_hash_msg VARCHAR(255) NOT NULL,
    PRIMARY KEY (id_conversa, id_ancora, ancora_em),
    UNIQUE (id_conversa, id_historico_bot, enviado_em)
);

CREATE TABLE IF NOT EXISTS chatbot.followup_retomada (
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

CREATE INDEX IF NOT EXISTS idx_followup_retomada_aberta ON chatbot.followup_retomada(id_conversa)
WHERE concluida_em IS NULL;

CREATE TABLE IF NOT EXISTS chatbot.followup_legado (
    id_conversa INTEGER PRIMARY KEY REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    stage_anterior INTEGER,
    marcada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

"""


def criar_tabelas_followup(cursor):
    cursor.execute(DDL_FOLLOWUP)
