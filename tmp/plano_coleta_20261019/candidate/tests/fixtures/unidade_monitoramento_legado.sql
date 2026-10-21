-- Fixture exclusiva de teste: representa a proposta anterior de tabela separada.
-- Nao executar em producao. O DDL e a migracao atuais usam a coluna em unidade.

BEGIN;
SET LOCAL lock_timeout = '5s';

DO $dependencias_monitoramento$
BEGIN
    IF TO_REGCLASS('chatbot.unidade') IS NULL
       OR TO_REGCLASS('chatbot.auth_user') IS NULL THEN
        RAISE EXCEPTION
            'Migracao recusada: chatbot.unidade e chatbot.auth_user devem existir.';
    END IF;
END
$dependencias_monitoramento$;

CREATE TABLE chatbot.unidade_monitoramento (
    id_monitoramento SERIAL PRIMARY KEY,
    id_unidade INT NOT NULL,
    id_usuario INT NOT NULL,

    CONSTRAINT uq_unidade_monitoramento_unidade
        UNIQUE (id_unidade),
    CONSTRAINT uq_unidade_monitoramento_usuario
        UNIQUE (id_usuario),

    CONSTRAINT unidade_monitoramento_id_unidade_fkey
        FOREIGN KEY (id_unidade)
        REFERENCES chatbot.unidade(id_unidade)
        ON DELETE CASCADE,
    CONSTRAINT unidade_monitoramento_id_usuario_fkey
        FOREIGN KEY (id_usuario)
        REFERENCES chatbot.auth_user(id)
        ON DELETE CASCADE
);

COMMIT;
