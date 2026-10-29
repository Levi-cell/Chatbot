"""DDL final do endereço público (relação opcional 1:1 com a unidade)."""

DDL_ENDERECO_UNIDADE = """
CREATE TABLE IF NOT EXISTS chatbot.endereco_unidade (
    id_unidade INTEGER PRIMARY KEY,
    endereco TEXT NOT NULL,
    CONSTRAINT endereco_unidade_id_unidade_fkey
        FOREIGN KEY (id_unidade) REFERENCES chatbot.unidade(id_unidade)
        ON DELETE CASCADE,
    CONSTRAINT ck_endereco_unidade_nao_vazio
        CHECK (endereco ~ '[^[:space:]]')
);
"""


def criar_tabela_endereco_unidade(cursor):
    cursor.execute(DDL_ENDERECO_UNIDADE)
