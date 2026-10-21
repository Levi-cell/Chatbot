-- Torna a profissao obrigatoria para titular e dependente.
--
-- Estado anterior:
--   etapa 3 --titular--> etapa 4 (profissao)
--   etapa 3 --dependente--> etapa 5 (nome do dependente)
--
-- Estado final:
--   etapa 3 --confirmado--> etapa 4 (profissao)
--   etapa 4 --dependente--> etapa 5 (nome do dependente)
--   etapa 4 --titular--> etapa 6 (idade)
--
-- Pre-requisitos operacionais:
--   1. parar webhook, worker-flow e worker-funil;
--   2. confirmar os tres servicos como inactive;
--   3. criar e aguardar um snapshot recente do RDS;
--   4. executar este arquivo inteiro como script UTF-8 no DBeaver;
--   5. publicar o codigo correspondente antes de religar os servicos.
--
-- Este script aceita somente o mapa anterior canonico (26 arestas) ou o
-- mapa final canonico (25 arestas). Qualquer estado parcial gera excecao e
-- rollback. Conversas que ja avancaram para a etapa 5 nao sao retrocedidas:
-- a regra passa a valer para novas confirmacoes.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15min';

LOCK TABLE
    chatbot.etapa,
    chatbot.etapa_transicao,
    chatbot.fila_mensagens,
    chatbot.historico_mensagens
IN ACCESS EXCLUSIVE MODE;

CREATE TEMP TABLE migracao_profissao_mapa_final (
    id_etapa_origem INTEGER NOT NULL,
    evento VARCHAR(100) NOT NULL,
    id_etapa_destino INTEGER NOT NULL,
    PRIMARY KEY (id_etapa_origem, evento),
    UNIQUE (id_etapa_origem, id_etapa_destino)
) ON COMMIT DROP;

INSERT INTO migracao_profissao_mapa_final (
    id_etapa_origem,
    evento,
    id_etapa_destino
)
VALUES
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

DO $migracao_profissao$
DECLARE
    v_mapa_anterior BOOLEAN;
    v_mapa_final BOOLEAN;
BEGIN
    IF (SELECT COUNT(*) FROM chatbot.etapa) <> 22
       OR (SELECT MIN(id_etapa) FROM chatbot.etapa) <> 1
       OR (SELECT MAX(id_etapa) FROM chatbot.etapa) <> 22
       OR NOT EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = 3
              AND nome_etapa = 'Confirmação do destino do atendimento'
       )
       OR NOT EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = 4
              AND nome_etapa = 'Profissão do cliente'
       ) THEN
        RAISE EXCEPTION
            'Catálogo de 22 etapas fora do estado esperado; migração cancelada';
    END IF;

    SELECT
        (SELECT COUNT(*) FROM chatbot.etapa_transicao) = 25
        AND NOT EXISTS (
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM chatbot.etapa_transicao
            EXCEPT
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM migracao_profissao_mapa_final
        )
        AND NOT EXISTS (
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM migracao_profissao_mapa_final
            EXCEPT
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM chatbot.etapa_transicao
        )
    INTO v_mapa_final;

    SELECT
        (SELECT COUNT(*) FROM chatbot.etapa_transicao) = 26
        AND (
            SELECT COUNT(*)
            FROM chatbot.etapa_transicao
            WHERE id_etapa_origem = 3
        ) = 2
        AND EXISTS (
            SELECT 1
            FROM chatbot.etapa_transicao
            WHERE id_etapa_origem = 3
              AND evento = 'destino_atendimento_confirmado_titular'
              AND id_etapa_destino = 4
        )
        AND EXISTS (
            SELECT 1
            FROM chatbot.etapa_transicao
            WHERE id_etapa_origem = 3
              AND evento = 'destino_atendimento_confirmado_dependente'
              AND id_etapa_destino = 5
        )
        AND NOT EXISTS (
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM chatbot.etapa_transicao
            WHERE id_etapa_origem <> 3
            EXCEPT
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM migracao_profissao_mapa_final
            WHERE id_etapa_origem <> 3
        )
        AND NOT EXISTS (
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM migracao_profissao_mapa_final
            WHERE id_etapa_origem <> 3
            EXCEPT
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM chatbot.etapa_transicao
            WHERE id_etapa_origem <> 3
        )
    INTO v_mapa_anterior;

    IF NOT v_mapa_anterior AND NOT v_mapa_final THEN
        RAISE EXCEPTION
            'Mapa de transicoes fora dos estados suportados; migracao cancelada';
    END IF;

    IF v_mapa_final THEN
        RAISE NOTICE
            'Mapa final de 25 transicoes ja aplicado; nenhuma troca necessaria';
        RETURN;
    END IF;

    -- Janela rara: a resposta antiga da etapa 5 pode ter sido persistida e a
    -- fila ainda nao ter recebido o status sent. Trocar o mapa nesse ponto
    -- faria o retry interpretar a resposta antiga com o evento novo. O gate
    -- aborta sem alterar dados; conclua/drene esses itens com a versao antiga.
    IF EXISTS (
        SELECT 1
        FROM chatbot.fila_mensagens AS fila
        WHERE fila.status IN ('pending', 'processing')
          AND EXISTS (
              SELECT 1
              FROM chatbot.historico_mensagens AS cliente
              WHERE cliente.id_conversa = fila.id_conversa
                AND cliente.id_mensagem_fila = fila.id_mensagem
                AND cliente.id_hash_msg = fila.id_hash_msg
                AND cliente.quem_enviou = 'cliente'
                AND cliente.id_etapa = 3
          )
          AND EXISTS (
              SELECT 1
              FROM chatbot.historico_mensagens AS bot
              WHERE bot.id_conversa = fila.id_conversa
                AND bot.id_mensagem_fila = fila.id_mensagem
                AND bot.id_hash_cliente_origem = fila.id_hash_msg
                AND bot.quem_enviou = 'bot'
                AND bot.id_etapa = 5
                AND bot.status_envio = 'sent'
          )
    ) THEN
        RAISE EXCEPTION
            'Existe resposta antiga 3->5 persistida em item ainda aberto; drene a fila antiga antes da migracao';
    END IF;

    DELETE FROM chatbot.etapa_transicao
    WHERE id_etapa_origem = 3;

    INSERT INTO chatbot.etapa_transicao (
        id_etapa_origem,
        evento,
        id_etapa_destino
    )
    VALUES (3, 'destino_atendimento_confirmado', 4);
END
$migracao_profissao$;

DO $validacao_profissao$
DECLARE
    v_sequence TEXT;
BEGIN
    IF (SELECT COUNT(*) FROM chatbot.etapa_transicao) <> 25
       OR EXISTS (
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM chatbot.etapa_transicao
            EXCEPT
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM migracao_profissao_mapa_final
       )
       OR EXISTS (
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM migracao_profissao_mapa_final
            EXCEPT
            SELECT
                id_etapa_origem,
                evento,
                id_etapa_destino
            FROM chatbot.etapa_transicao
       ) THEN
        RAISE EXCEPTION
            'Validacao final do mapa de 25 transicoes falhou';
    END IF;

    v_sequence := pg_get_serial_sequence(
        'chatbot.etapa_transicao',
        'id_transicao'
    );

    IF v_sequence IS NOT NULL THEN
        PERFORM setval(
            v_sequence::regclass,
            GREATEST(
                COALESCE(
                    (SELECT MAX(id_transicao) FROM chatbot.etapa_transicao),
                    1
                ),
                1
            ),
            EXISTS (SELECT 1 FROM chatbot.etapa_transicao)
        );
    END IF;
END
$validacao_profissao$;

SELECT
    id_etapa_origem,
    evento,
    id_etapa_destino
FROM chatbot.etapa_transicao
ORDER BY id_etapa_origem, evento;

COMMIT;
