-- Substitui a migracao anterior que criava unidade_monitoramento.
-- Executar inteiro no DBeaver antes de publicar o codigo atualizado.
-- Aplicacao unica. Em caso de erro, execute ROLLBACK antes de tentar novamente.
-- Se a tabela anterior existir, seus vinculos sao transferidos antes da remocao.

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

ALTER TABLE chatbot.unidade
    ADD COLUMN id_usuario_monitoramento INT NULL,
    ADD CONSTRAINT uq_unidade_usuario_monitoramento
        UNIQUE (id_usuario_monitoramento),
    ADD CONSTRAINT unidade_id_usuario_monitoramento_fkey
        FOREIGN KEY (id_usuario_monitoramento)
        REFERENCES chatbot.auth_user(id)
        ON DELETE SET NULL;

DO $transferir_monitoramento$
BEGIN
    IF TO_REGCLASS('chatbot.unidade_monitoramento') IS NOT NULL THEN
        LOCK TABLE chatbot.unidade_monitoramento IN ACCESS EXCLUSIVE MODE;

        IF EXISTS (
            SELECT 1
            FROM chatbot.unidade_monitoramento AS antigo
            LEFT JOIN chatbot.unidade AS u ON u.id_unidade = antigo.id_unidade
            LEFT JOIN chatbot.auth_user AS usuario ON usuario.id = antigo.id_usuario
            WHERE u.id_unidade IS NULL OR usuario.id IS NULL
        ) OR EXISTS (
            SELECT 1 FROM chatbot.unidade_monitoramento
            GROUP BY id_unidade HAVING COUNT(*) > 1
        ) THEN
            RAISE EXCEPTION 'Migracao recusada: vinculos antigos invalidos ou ambiguos.';
        END IF;

        UPDATE chatbot.unidade AS u
        SET id_usuario_monitoramento = antigo.id_usuario
        FROM chatbot.unidade_monitoramento AS antigo
        WHERE u.id_unidade = antigo.id_unidade;

        IF EXISTS (
            SELECT 1
            FROM chatbot.unidade_monitoramento AS antigo
            JOIN chatbot.unidade AS u ON u.id_unidade = antigo.id_unidade
            WHERE u.id_usuario_monitoramento IS DISTINCT FROM antigo.id_usuario
        ) THEN
            RAISE EXCEPTION 'Migracao recusada: nem todos os vinculos foram transferidos.';
        END IF;

        -- Sem CASCADE: dependencias inesperadas impedem a remocao e revertem tudo.
        DROP TABLE chatbot.unidade_monitoramento;
    END IF;
END
$transferir_monitoramento$;

COMMIT;
