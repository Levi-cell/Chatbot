-- Executar inteiro no DBeaver antes de iniciar o código novo, com webhook e workers parados.
-- Revisada em 28/10/2026: endereço e horários opcionais por unidade.
-- Preserva conversas, históricos, filas, cache e cadastros já preenchidos.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '120s';

ALTER TABLE chatbot.unidade
    ADD COLUMN IF NOT EXISTS horarios_funcionamento TEXT NULL;

-- INICIO DDL ENDERECO UNIDADE
CREATE TABLE IF NOT EXISTS chatbot.endereco_unidade (
    id_unidade INTEGER PRIMARY KEY,
    endereco TEXT NOT NULL,
    CONSTRAINT endereco_unidade_id_unidade_fkey
        FOREIGN KEY (id_unidade) REFERENCES chatbot.unidade(id_unidade)
        ON DELETE CASCADE,
    CONSTRAINT ck_endereco_unidade_nao_vazio
        CHECK (endereco ~ '[^[:space:]]')
);
-- FIM DDL ENDERECO UNIDADE

-- Vincular por nomes conferidos, nunca por IDs de outra instalação.
DO $enderecos$
DECLARE
    registro RECORD;
    unidade INTEGER;
    quantidade INTEGER;
BEGIN
    FOR registro IN SELECT * FROM (VALUES
        ('Supera Santo André', 'Rua Dr. Eduardo Monteiro, 188 - Jardim Bela Vista, Santo André - SP, CEP 09041-300'),
        ('Supera Santo Antônio de Jesus', 'Avenida Barros e Almeida, 88, Centro - Santo Antônio de Jesus'),
        ('Supera Rio Vermelho', 'R. Odilon Santos, 14 - 1 a - Rio Vermelho, Salvador - BA, 41940-350, Brasil')
    ) AS enderecos(nome, endereco)
    LOOP
        SELECT count(*), min(id_unidade) INTO quantidade, unidade
        FROM chatbot.unidade WHERE nome_unidade = registro.nome;
        IF quantidade <> 1 THEN
            RAISE EXCEPTION 'Unidade ausente ou ambígua: %', registro.nome;
        END IF;
        INSERT INTO chatbot.endereco_unidade(id_unidade, endereco)
        VALUES (unidade, registro.endereco)
        ON CONFLICT (id_unidade) DO NOTHING;
    END LOOP;
END $enderecos$;

-- Horário confirmado de Santo André. Preserva cadastros já preenchidos.
UPDATE chatbot.unidade
SET horarios_funcionamento = 'segunda a sexta das 9h às 19h, exceto quarta-feira, quando vai até as 21h, e sábado das 8h30 às 13h30'
WHERE nome_unidade = 'Supera Santo André'
  AND (
      horarios_funcionamento IS NULL
      OR horarios_funcionamento !~ '[^[:space:]]'
  );

COMMIT;
-- Nas demais unidades, horários não informados permanecem NULL.
SELECT u.nome_unidade, e.endereco, u.horarios_funcionamento
FROM chatbot.endereco_unidade e JOIN chatbot.unidade u USING (id_unidade)
ORDER BY u.nome_unidade;
