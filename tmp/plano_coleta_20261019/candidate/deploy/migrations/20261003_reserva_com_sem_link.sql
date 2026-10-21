-- Migração: reserva com e sem link, catálogo 22 <-> 24 etapas.
-- Executar o arquivo INTEIRO no DBeaver, com os serviços parados e snapshot
-- do banco feito nesse corte. Backup do código no Git não substitui o do banco.
-- Não executar setup/seeds no banco existente. Nenhuma mensagem é enviada.
-- A reversão recusa dados das novas etapas, preferências ou unidades sem link:
-- depois de iniciar atendimentos novos, usar o snapshot e o código do mesmo corte.

BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15min';

-- O lock no histórico inclui suas partições. As FKs permanecem ativas.
LOCK TABLE chatbot.unidade, chatbot.etapa, chatbot.etapa_transicao,
    chatbot.conversa, chatbot.historico_mensagens, chatbot.respostas_desafios,
    chatbot.followup_retomada IN ACCESS EXCLUSIVE MODE;

-- Catálogos canônicos da versão anterior e da versão implantada.
CREATE TEMP TABLE reserva_catalogo_origem (id_etapa INTEGER PRIMARY KEY, nome_etapa TEXT, encerra_automaticamente BOOLEAN, bloqueio_dias INTEGER, elegivel_funil BOOLEAN) ON COMMIT DROP;
INSERT INTO reserva_catalogo_origem VALUES
    (1, 'Saudação e nome do cliente', FALSE, 0, FALSE),
    (2, 'Destino do atendimento', FALSE, 0, FALSE),
    (3, 'Confirmação do destino do atendimento', FALSE, 0, FALSE),
    (4, 'Profissão do cliente', FALSE, 0, FALSE),
    (5, 'Nome do dependente', FALSE, 0, FALSE),
    (6, 'Idade do aluno', FALSE, 0, FALSE),
    (7, 'Oferta de aula experimental e avaliação cognitiva', FALSE, 0, FALSE),
    (8, 'Oferta adiada e Instagram', FALSE, 0, FALSE),
    (9, 'Confirmação de retorno ao atendimento', FALSE, 0, FALSE),
    (10, 'Email', FALSE, 0, FALSE),
    (11, 'Introdução à triagem cognitiva', FALSE, 0, FALSE),
    (12, 'Triagem cognitiva - pergunta 1', FALSE, 0, FALSE),
    (13, 'Triagem cognitiva - pergunta 2', FALSE, 0, FALSE),
    (14, 'Triagem cognitiva - pergunta 3', FALSE, 0, FALSE),
    (15, 'Triagem cognitiva - pergunta 4', FALSE, 0, FALSE),
    (16, 'Triagem cognitiva - pergunta 5', FALSE, 0, FALSE),
    (17, 'Triagem cognitiva - pergunta 6', FALSE, 0, FALSE),
    (18, 'Agendamento após a triagem cognitiva', FALSE, 0, TRUE),
    (19, 'Pesquisa de satisfação - nota', FALSE, 0, TRUE),
    (20, 'Pesquisa de satisfação - opção de comentário', FALSE, 0, TRUE),
    (21, 'Pesquisa de satisfação - comentário', FALSE, 0, TRUE),
    (22, 'Finalização do atendimento', TRUE, 30, TRUE);

CREATE TEMP TABLE reserva_catalogo_destino (id_etapa INTEGER PRIMARY KEY, nome_etapa TEXT, encerra_automaticamente BOOLEAN, bloqueio_dias INTEGER, elegivel_funil BOOLEAN) ON COMMIT DROP;
INSERT INTO reserva_catalogo_destino VALUES
    (1, 'Saudação e nome do cliente', FALSE, 0, FALSE),
    (2, 'Destino do atendimento', FALSE, 0, FALSE),
    (3, 'Confirmação do destino do atendimento', FALSE, 0, FALSE),
    (4, 'Profissão do cliente', FALSE, 0, FALSE),
    (5, 'Nome do dependente', FALSE, 0, FALSE),
    (6, 'Idade do aluno', FALSE, 0, FALSE),
    (7, 'Oferta de aula experimental e avaliação cognitiva', FALSE, 0, FALSE),
    (8, 'Oferta adiada e Instagram', FALSE, 0, FALSE),
    (9, 'Confirmação de retorno ao atendimento', FALSE, 0, FALSE),
    (10, 'Email', FALSE, 0, FALSE),
    (11, 'Introdução à triagem cognitiva', FALSE, 0, FALSE),
    (12, 'Triagem cognitiva - pergunta 1', FALSE, 0, FALSE),
    (13, 'Triagem cognitiva - pergunta 2', FALSE, 0, FALSE),
    (14, 'Triagem cognitiva - pergunta 3', FALSE, 0, FALSE),
    (15, 'Triagem cognitiva - pergunta 4', FALSE, 0, FALSE),
    (16, 'Triagem cognitiva - pergunta 5', FALSE, 0, FALSE),
    (17, 'Triagem cognitiva - pergunta 6', FALSE, 0, FALSE),
    (18, 'Escolha do turno para a demonstração prática', FALSE, 0, FALSE),
    (19, 'Encaminhamento ao comercial após a triagem', FALSE, 0, TRUE),
    (20, 'Sua reserva pela plataforma da unidade', FALSE, 0, TRUE),
    (21, 'Pesquisa de satisfação - nota', FALSE, 0, TRUE),
    (22, 'Pesquisa de satisfação - opção de comentário', FALSE, 0, TRUE),
    (23, 'Pesquisa de satisfação - comentário', FALSE, 0, TRUE),
    (24, 'Finalização do atendimento', TRUE, 30, TRUE);

CREATE TEMP TABLE reserva_mapa_origem (id_etapa_origem INTEGER, evento TEXT, id_etapa_destino INTEGER) ON COMMIT DROP;
INSERT INTO reserva_mapa_origem VALUES
    (1, 'nome_cliente_valido', 2),
    (2, 'destino_atendimento_definido', 3),
    (3, 'destino_atendimento_confirmado', 4),
    (4, 'profissao_dependente_valida', 5),
    (4, 'profissao_titular_valida', 6),
    (5, 'nome_dependente_valido', 6),
    (6, 'idade_valida', 7),
    (7, 'oferta_aceita', 10),
    (7, 'oferta_adiada', 8),
    (8, 'cliente_retornou', 9),
    (9, 'retorno_confirmado', 10),
    (9, 'retorno_adiado', 8),
    (10, 'email_valido', 11),
    (11, 'triagem_iniciada', 12),
    (12, 'triagem_pergunta_1_respondida', 13),
    (13, 'triagem_pergunta_2_respondida', 14),
    (14, 'triagem_pergunta_3_respondida', 15),
    (15, 'triagem_pergunta_4_respondida', 16),
    (16, 'triagem_pergunta_5_respondida', 17),
    (17, 'triagem_pergunta_6_respondida', 18),
    (18, 'agendamento_confirmado', 19),
    (19, 'satisfacao_avaliada', 20),
    (20, 'comentario_satisfacao_aceito', 21),
    (20, 'comentario_satisfacao_recusado', 22),
    (21, 'comentario_satisfacao_recebido', 22);

CREATE TEMP TABLE reserva_mapa_destino (id_etapa_origem INTEGER, evento TEXT, id_etapa_destino INTEGER) ON COMMIT DROP;
INSERT INTO reserva_mapa_destino VALUES
    (1, 'nome_cliente_valido', 2),
    (2, 'destino_atendimento_definido', 3),
    (3, 'destino_atendimento_confirmado', 4),
    (4, 'profissao_dependente_valida', 5),
    (4, 'profissao_titular_valida', 6),
    (5, 'nome_dependente_valido', 6),
    (6, 'idade_valida', 7),
    (7, 'oferta_aceita', 10),
    (7, 'oferta_adiada', 8),
    (8, 'cliente_retornou', 9),
    (9, 'retorno_confirmado', 10),
    (9, 'retorno_adiado', 8),
    (10, 'email_valido', 11),
    (11, 'triagem_iniciada', 12),
    (12, 'triagem_pergunta_1_respondida', 13),
    (13, 'triagem_pergunta_2_respondida', 14),
    (14, 'triagem_pergunta_3_respondida', 15),
    (15, 'triagem_pergunta_4_respondida', 16),
    (16, 'triagem_pergunta_5_respondida', 17),
    (17, 'triagem_pergunta_6_respondida', 20),
    (17, 'triagem_concluida_sem_link', 18),
    (18, 'turno_escolhido', 19),
    (19, 'avaliacao_solicitada', 21),
    (20, 'agendamento_confirmado', 21),
    (21, 'satisfacao_avaliada', 22),
    (22, 'comentario_satisfacao_aceito', 23),
    (22, 'comentario_satisfacao_recusado', 24),
    (23, 'comentario_satisfacao_recebido', 24);


CREATE TEMP TABLE reserva_estado (
    migrar BOOLEAN NOT NULL,
    reverter BOOLEAN NOT NULL
) ON COMMIT DROP;

DO $preflight$
DECLARE
    v_catalogo JSONB;
    v_mapa JSONB;
    v_origem BOOLEAN;
    v_destino BOOLEAN;
    v_inesperadas TEXT;
BEGIN
    SELECT jsonb_agg(jsonb_build_array(id_etapa, nome_etapa,
        encerra_automaticamente, bloqueio_dias, elegivel_funil) ORDER BY id_etapa)
    INTO v_catalogo FROM chatbot.etapa;
    SELECT jsonb_agg(jsonb_build_array(id_etapa_origem, evento, id_etapa_destino)
        ORDER BY id_etapa_origem, evento)
    INTO v_mapa FROM chatbot.etapa_transicao;

    v_origem := v_catalogo = (SELECT jsonb_agg(jsonb_build_array(id_etapa,
        nome_etapa, encerra_automaticamente, bloqueio_dias, elegivel_funil)
        ORDER BY id_etapa) FROM reserva_catalogo_origem)
        AND v_mapa = (SELECT jsonb_agg(jsonb_build_array(id_etapa_origem, evento,
        id_etapa_destino) ORDER BY id_etapa_origem, evento) FROM reserva_mapa_origem);
    v_destino := v_catalogo = (SELECT jsonb_agg(jsonb_build_array(id_etapa,
        nome_etapa, encerra_automaticamente, bloqueio_dias, elegivel_funil)
        ORDER BY id_etapa) FROM reserva_catalogo_destino)
        AND v_mapa = (SELECT jsonb_agg(jsonb_build_array(id_etapa_origem, evento,
        id_etapa_destino) ORDER BY id_etapa_origem, evento) FROM reserva_mapa_destino);

    IF NOT COALESCE(v_origem OR v_destino, FALSE) THEN
        RAISE EXCEPTION 'Catálogo/mapa diferente das versões suportadas. Nada foi aplicado; conferir as etapas antes de migrar.';
    END IF;

    -- Uma FK nova exige revisão: não arriscar ON DELETE SET NULL/CASCADE em
    -- uma referência desconhecida. FKs herdadas das partições são cobertas.
    SELECT string_agg(c.conrelid::regclass::text || '.' || c.conname, ', ')
    INTO v_inesperadas
    FROM pg_constraint c
    LEFT JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
    WHERE c.contype = 'f' AND c.confrelid = 'chatbot.etapa'::regclass
      AND c.conparentid = 0
      AND NOT (
        c.convalidated AND array_length(c.conkey, 1) = 1
        AND c.confkey = ARRAY[(SELECT attnum FROM pg_attribute
            WHERE attrelid = 'chatbot.etapa'::regclass AND attname = 'id_etapa')]
        AND (
            (c.conrelid = 'chatbot.conversa'::regclass AND a.attname = 'id_etapa_atual')
            OR (c.conrelid IN (SELECT relid FROM pg_partition_tree('chatbot.historico_mensagens')) AND a.attname = 'id_etapa')
            OR (c.conrelid IN ('chatbot.respostas_desafios'::regclass, 'chatbot.followup_retomada'::regclass) AND a.attname = 'id_etapa')
            OR (c.conrelid = 'chatbot.etapa_transicao'::regclass AND a.attname IN ('id_etapa_origem', 'id_etapa_destino'))
        )
      );
    IF v_inesperadas IS NOT NULL THEN
        RAISE EXCEPTION 'Referências de etapa não mapeadas: %. Migração cancelada.', v_inesperadas;
    END IF;

    INSERT INTO reserva_estado VALUES (v_origem, FALSE);
END
$preflight$;

-- As contagens por significado incluem etapas nulas e todas as partições.
-- Só os campos de referência às etapas serão remapeados.
CREATE TEMP VIEW reserva_contagens AS
SELECT 'conversa'::TEXT AS tabela, id_etapa_atual AS etapa, COUNT(*) AS quantidade
FROM chatbot.conversa GROUP BY id_etapa_atual
UNION ALL SELECT 'historico_mensagens', id_etapa, COUNT(*)
FROM chatbot.historico_mensagens GROUP BY id_etapa
UNION ALL SELECT 'respostas_desafios', id_etapa, COUNT(*)
FROM chatbot.respostas_desafios GROUP BY id_etapa
UNION ALL SELECT 'followup_retomada', id_etapa, COUNT(*)
FROM chatbot.followup_retomada GROUP BY id_etapa;

CREATE TEMP TABLE reserva_contagens_esperadas ON COMMIT DROP AS
SELECT tabela,
    CASE WHEN NOT e.migrar THEN etapa
         WHEN e.reverter AND etapa BETWEEN 20 AND 24 THEN etapa - 2
         WHEN NOT e.reverter AND etapa BETWEEN 18 AND 22 THEN etapa + 2
         ELSE etapa END AS etapa,
    quantidade
FROM reserva_contagens CROSS JOIN reserva_estado e;

DO $remapear$
DECLARE
    v_estado RECORD;
    v_etapa RECORD;
    v_origem INTEGER;
    v_destino INTEGER;
    v_tem_turno BOOLEAN;
    v_tem_preferencia BOOLEAN;
BEGIN
    SELECT * INTO STRICT v_estado FROM reserva_estado;
    SELECT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = 'chatbot.conversa'::regclass
        AND attname = 'turno' AND NOT attisdropped) INTO v_tem_turno;

    IF v_estado.reverter THEN
        IF EXISTS (SELECT 1 FROM reserva_contagens WHERE etapa IN (18, 19)) AND v_estado.migrar THEN
            RAISE EXCEPTION 'Reversão recusada: há atendimentos/histórico/checkpoints das novas etapas 18/19. Usar o snapshot do corte.';
        END IF;
        IF v_tem_turno THEN
            EXECUTE 'SELECT EXISTS (SELECT 1 FROM chatbot.conversa WHERE turno IS NOT NULL)' INTO v_tem_preferencia;
            IF v_tem_preferencia THEN
                RAISE EXCEPTION 'Reversão recusada: há preferências de turno registradas. Usar o snapshot do corte.';
            END IF;
        END IF;
        IF EXISTS (SELECT 1 FROM chatbot.unidade WHERE link_agendamento IS NULL) THEN
            RAISE EXCEPTION 'Reversão recusada: há unidades sem link, incompatíveis com a versão anterior.';
        END IF;
    ELSE
        IF v_estado.migrar AND v_tem_turno THEN
            EXECUTE 'SELECT EXISTS (SELECT 1 FROM chatbot.conversa WHERE turno IS NOT NULL)' INTO v_tem_preferencia;
            IF v_tem_preferencia THEN
                RAISE EXCEPTION 'Estado misto: catálogo legado já tem preferências. Revisar antes de migrar.';
            END IF;
        END IF;
        ALTER TABLE chatbot.unidade ALTER COLUMN link_agendamento DROP NOT NULL;
        ALTER TABLE chatbot.conversa ADD COLUMN IF NOT EXISTS turno VARCHAR(5);
        IF NOT EXISTS (SELECT 1 FROM pg_attribute WHERE attrelid = 'chatbot.conversa'::regclass
            AND attname = 'turno' AND atttypid = 'varchar'::regtype AND atttypmod = 9 AND NOT attnotnull) THEN
            RAISE EXCEPTION 'Coluna conversa.turno incompatível: esperado VARCHAR(5) opcional.';
        END IF;
        ALTER TABLE chatbot.conversa DROP CONSTRAINT IF EXISTS ck_conversa_turno;
        ALTER TABLE chatbot.conversa ADD CONSTRAINT ck_conversa_turno
            CHECK (turno IS NULL OR turno IN ('manha', 'tarde', 'noite'));
    END IF;

    IF v_estado.migrar THEN
        IF v_estado.reverter THEN
            DELETE FROM chatbot.etapa_transicao
            WHERE (id_etapa_origem, evento) IN (
                (17, 'triagem_concluida_sem_link'), (18, 'turno_escolhido'), (19, 'avaliacao_solicitada')
            );
            DELETE FROM chatbot.etapa WHERE id_etapa IN (18, 19);
        END IF;

        -- Subida: ordem decrescente 22..18. Reversão: crescente 20..24.
        -- Cada destino fica livre antes da inserção seguinte, inclusive nomes
        -- UNIQUE. Não há desativação de constraints, triggers ou apagamento de dados.
        FOR v_origem IN
            SELECT id_etapa FROM reserva_catalogo_origem
            WHERE (NOT v_estado.reverter AND id_etapa BETWEEN 18 AND 22)
               OR (v_estado.reverter AND id_etapa BETWEEN 20 AND 24)
            ORDER BY CASE WHEN v_estado.reverter THEN id_etapa ELSE -id_etapa END
        LOOP
            v_destino := v_origem + CASE WHEN v_estado.reverter THEN -2 ELSE 2 END;
            SELECT * INTO STRICT v_etapa FROM chatbot.etapa WHERE id_etapa = v_origem;
            UPDATE chatbot.etapa SET nome_etapa = '__reserva_link_20261003_' || v_origem
            WHERE id_etapa = v_origem;
            INSERT INTO chatbot.etapa(id_etapa, nome_etapa, encerra_automaticamente, bloqueio_dias, elegivel_funil)
            VALUES (v_destino, v_etapa.nome_etapa, v_etapa.encerra_automaticamente, v_etapa.bloqueio_dias, v_etapa.elegivel_funil);

            UPDATE chatbot.conversa SET id_etapa_atual = v_destino WHERE id_etapa_atual = v_origem;
            UPDATE chatbot.historico_mensagens SET id_etapa = v_destino WHERE id_etapa = v_origem;
            UPDATE chatbot.respostas_desafios SET id_etapa = v_destino WHERE id_etapa = v_origem;
            UPDATE chatbot.followup_retomada SET id_etapa = v_destino WHERE id_etapa = v_origem;
            UPDATE chatbot.etapa_transicao SET id_etapa_origem = v_destino WHERE id_etapa_origem = v_origem;
            UPDATE chatbot.etapa_transicao SET id_etapa_destino = v_destino WHERE id_etapa_destino = v_origem;
            DELETE FROM chatbot.etapa WHERE id_etapa = v_origem;
        END LOOP;

        INSERT INTO chatbot.etapa(id_etapa, nome_etapa, encerra_automaticamente, bloqueio_dias, elegivel_funil)
        SELECT * FROM reserva_catalogo_destino
        ON CONFLICT (id_etapa) DO UPDATE SET nome_etapa = EXCLUDED.nome_etapa,
            encerra_automaticamente = EXCLUDED.encerra_automaticamente,
            bloqueio_dias = EXCLUDED.bloqueio_dias, elegivel_funil = EXCLUDED.elegivel_funil;

        -- Mantém os IDs das arestas antigas e acrescenta somente as novas.
        INSERT INTO chatbot.etapa_transicao(id_etapa_origem, evento, id_etapa_destino)
        SELECT m.* FROM reserva_mapa_destino m
        WHERE NOT EXISTS (SELECT 1 FROM chatbot.etapa_transicao e
            WHERE e.id_etapa_origem = m.id_etapa_origem AND e.evento = m.evento);
    END IF;

    IF v_estado.reverter THEN
        ALTER TABLE chatbot.unidade ALTER COLUMN link_agendamento SET NOT NULL;
        ALTER TABLE chatbot.conversa DROP COLUMN IF EXISTS turno;
    END IF;
END
$remapear$;

DO $validar$
BEGIN
    IF EXISTS (
        (SELECT * FROM reserva_contagens EXCEPT SELECT * FROM reserva_contagens_esperadas)
        UNION ALL
        (SELECT * FROM reserva_contagens_esperadas EXCEPT SELECT * FROM reserva_contagens)
    ) THEN
        RAISE EXCEPTION 'Contagens por significado divergiram. Toda a migração foi cancelada.';
    END IF;
    IF EXISTS (
        (SELECT id_etapa,nome_etapa,encerra_automaticamente,bloqueio_dias,elegivel_funil FROM chatbot.etapa
         EXCEPT SELECT * FROM reserva_catalogo_destino)
        UNION ALL
        (SELECT * FROM reserva_catalogo_destino EXCEPT
         SELECT id_etapa,nome_etapa,encerra_automaticamente,bloqueio_dias,elegivel_funil FROM chatbot.etapa)
    ) OR EXISTS (
        (SELECT id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao EXCEPT SELECT * FROM reserva_mapa_destino)
        UNION ALL
        (SELECT * FROM reserva_mapa_destino EXCEPT SELECT id_etapa_origem,evento,id_etapa_destino FROM chatbot.etapa_transicao)
    ) THEN
        RAISE EXCEPTION 'Catálogo ou mapa final divergente. Toda a migração foi cancelada.';
    END IF;
END
$validar$;

SELECT setval(pg_get_serial_sequence('chatbot.etapa', 'id_etapa'),
    (SELECT MAX(id_etapa) FROM chatbot.etapa), TRUE);
SELECT setval(pg_get_serial_sequence('chatbot.etapa_transicao', 'id_transicao'),
    (SELECT MAX(id_transicao) FROM chatbot.etapa_transicao), TRUE);

-- Mostra o resultado sem expor mensagens nem dados pessoais.
SELECT id_etapa, nome_etapa, encerra_automaticamente, bloqueio_dias, elegivel_funil
FROM chatbot.etapa ORDER BY id_etapa;
SELECT tabela, etapa, quantidade FROM reserva_contagens ORDER BY tabela, etapa;
DROP VIEW reserva_contagens;
COMMIT;
