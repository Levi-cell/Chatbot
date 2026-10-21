-- Adiciona a confirmação do destino como etapa 3 e move as antigas
-- etapas 3..21 para 4..22 sem alterar o progresso das conversas.
--
-- Pré-requisitos operacionais:
--   1. parar webhook, worker-flow e worker-funil e confirmar que estão inativos;
--   2. criar um snapshot do RDS já sem novas mensagens entrando;
--   3. executar este arquivo inteiro como script no DBeaver;
--   4. publicar o código com os novos IDs antes de religar os serviços.
--
-- O bloco aceita somente o catálogo legado canônico ou o catálogo final.
-- Em estado inesperado, timeout ou falha de validação, o PostgreSQL reverte
-- toda a transação. Depois do COMMIT e da retomada dos atendimentos, o
-- rollback suportado é a restauração do snapshot: a nova etapa 3 pode passar
-- a ter dados legítimos e não deve ser fundida automaticamente com a antiga.

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '15min';

LOCK TABLE
    chatbot.etapa,
    chatbot.etapa_transicao,
    chatbot.conversa,
    chatbot.historico_mensagens,
    chatbot.respostas_desafios
IN ACCESS EXCLUSIVE MODE;

CREATE TEMP TABLE migracao_etapa3_contagens_antes
ON COMMIT DROP
AS
SELECT
    (
        SELECT COUNT(*)
        FROM chatbot.conversa
        WHERE id_etapa_atual IS NOT NULL
    ) AS conversas_com_etapa,
    (
        SELECT COUNT(*)
        FROM chatbot.historico_mensagens
        WHERE id_etapa IS NOT NULL
    ) AS historicos_com_etapa,
    (
        SELECT COUNT(*)
        FROM chatbot.respostas_desafios
        WHERE id_etapa IS NOT NULL
    ) AS respostas_com_etapa;

-- O mapa antigo referencia o catálogo e precisa sair antes da troca dos IDs.
-- Ele é um catálogo derivado e é recriado integralmente mais abaixo.
DELETE FROM chatbot.etapa_transicao;

DO $migracao_etapa3$
DECLARE
    v_catalogo_legado BOOLEAN;
    v_catalogo_final BOOLEAN;
    v_id_origem INTEGER;
    v_id_destino INTEGER;
    v_nome_etapa VARCHAR(100);
    v_encerra_automaticamente BOOLEAN;
    v_bloqueio_dias INTEGER;
    v_elegivel_funil BOOLEAN;
BEGIN
    SELECT
        COUNT(*) = 21
        AND MIN(id_etapa) = 1
        AND MAX(id_etapa) = 21
        AND EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = 3
              AND nome_etapa = 'Profissão do cliente'
        )
        AND EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = 17
              AND nome_etapa = 'Agendamento após a triagem cognitiva'
              AND elegivel_funil = TRUE
        )
        AND EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = 21
              AND nome_etapa = 'Finalização do atendimento'
              AND encerra_automaticamente = TRUE
              AND bloqueio_dias = 30
              AND elegivel_funil = TRUE
        )
    INTO v_catalogo_legado
    FROM chatbot.etapa;

    SELECT
        COUNT(*) = 22
        AND MIN(id_etapa) = 1
        AND MAX(id_etapa) = 22
        AND EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = 3
              AND nome_etapa = 'Confirmação do destino do atendimento'
        )
        AND EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = 4
              AND nome_etapa = 'Profissão do cliente'
        )
        AND EXISTS (
            SELECT 1
            FROM chatbot.etapa
            WHERE id_etapa = 22
              AND nome_etapa = 'Finalização do atendimento'
        )
    INTO v_catalogo_final
    FROM chatbot.etapa;

    IF NOT v_catalogo_legado AND NOT v_catalogo_final THEN
        RAISE EXCEPTION
            'Catálogo de etapas fora dos estados suportados; migração cancelada';
    END IF;

    IF v_catalogo_legado THEN
        -- A ordem decrescente libera o ID de destino antes da próxima troca.
        -- Um nome temporário evita conflito com UNIQUE(nome_etapa) enquanto
        -- a linha de origem ainda existe.
        FOR v_id_origem IN REVERSE 21..3 LOOP
            v_id_destino := v_id_origem + 1;

            SELECT
                nome_etapa,
                encerra_automaticamente,
                bloqueio_dias,
                elegivel_funil
            INTO STRICT
                v_nome_etapa,
                v_encerra_automaticamente,
                v_bloqueio_dias,
                v_elegivel_funil
            FROM chatbot.etapa
            WHERE id_etapa = v_id_origem;

            INSERT INTO chatbot.etapa (
                id_etapa,
                nome_etapa,
                encerra_automaticamente,
                bloqueio_dias,
                elegivel_funil
            )
            VALUES (
                v_id_destino,
                FORMAT(
                    '__migracao_etapa_%s_para_%s__',
                    v_id_origem,
                    v_id_destino
                ),
                FALSE,
                0,
                FALSE
            );

            UPDATE chatbot.conversa
            SET id_etapa_atual = v_id_destino
            WHERE id_etapa_atual = v_id_origem;

            UPDATE chatbot.historico_mensagens
            SET id_etapa = v_id_destino
            WHERE id_etapa = v_id_origem;

            UPDATE chatbot.respostas_desafios
            SET id_etapa = v_id_destino
            WHERE id_etapa = v_id_origem;

            DELETE FROM chatbot.etapa
            WHERE id_etapa = v_id_origem;

            UPDATE chatbot.etapa
            SET
                nome_etapa = v_nome_etapa,
                encerra_automaticamente = v_encerra_automaticamente,
                bloqueio_dias = v_bloqueio_dias,
                elegivel_funil = v_elegivel_funil
            WHERE id_etapa = v_id_destino;
        END LOOP;

        INSERT INTO chatbot.etapa (
            id_etapa,
            nome_etapa,
            encerra_automaticamente,
            bloqueio_dias,
            elegivel_funil
        )
        VALUES (
            3,
            'Confirmação do destino do atendimento',
            FALSE,
            0,
            FALSE
        );
    END IF;
END
$migracao_etapa3$;

-- Normaliza as políticas no estado final. A etapa 18 inicia a elegibilidade
-- do Funil e somente a etapa 22 encerra e bloqueia por 30 dias.
UPDATE chatbot.etapa
SET
    encerra_automaticamente = (id_etapa = 22),
    bloqueio_dias = CASE WHEN id_etapa = 22 THEN 30 ELSE 0 END,
    elegivel_funil = (id_etapa BETWEEN 18 AND 22)
WHERE id_etapa BETWEEN 1 AND 22;

INSERT INTO chatbot.etapa_transicao (
    id_etapa_origem,
    evento,
    id_etapa_destino
)
VALUES
    (1, 'nome_cliente_valido', 2),
    (2, 'destino_atendimento_definido', 3),
    (3, 'destino_atendimento_confirmado_titular', 4),
    (3, 'destino_atendimento_confirmado_dependente', 5),
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

SELECT setval(
    pg_get_serial_sequence('chatbot.etapa', 'id_etapa'),
    22,
    TRUE
);

SELECT setval(
    pg_get_serial_sequence('chatbot.etapa_transicao', 'id_transicao'),
    COALESCE((SELECT MAX(id_transicao) FROM chatbot.etapa_transicao), 1),
    TRUE
);

DO $validar_migracao_etapa3$
DECLARE
    v_antes RECORD;
BEGIN
    SELECT *
    INTO STRICT v_antes
    FROM migracao_etapa3_contagens_antes;

    IF (SELECT COUNT(*) FROM chatbot.etapa) <> 22 THEN
        RAISE EXCEPTION 'Catálogo final não possui exatamente 22 etapas';
    END IF;

    IF (
        SELECT ARRAY_AGG(id_etapa ORDER BY id_etapa)
        FROM chatbot.etapa
        WHERE elegivel_funil = TRUE
    ) IS DISTINCT FROM ARRAY[18, 19, 20, 21, 22] THEN
        RAISE EXCEPTION 'Elegibilidade do Funil divergente de 18..22';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM chatbot.etapa
        WHERE encerra_automaticamente = TRUE
           OR bloqueio_dias > 0
    ) <> 1 OR NOT EXISTS (
        SELECT 1
        FROM chatbot.etapa
        WHERE id_etapa = 22
          AND encerra_automaticamente = TRUE
          AND bloqueio_dias = 30
    ) THEN
        RAISE EXCEPTION 'Política terminal não está exclusiva na etapa 22';
    END IF;

    IF (SELECT COUNT(*) FROM chatbot.etapa_transicao) <> 26 THEN
        RAISE EXCEPTION 'Mapa final não possui exatamente 26 transições';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM chatbot.etapa_transicao
        WHERE id_etapa_origem = 2
          AND evento = 'destino_atendimento_definido'
          AND id_etapa_destino = 3
    ) OR NOT EXISTS (
        SELECT 1
        FROM chatbot.etapa_transicao
        WHERE id_etapa_origem = 3
          AND evento = 'destino_atendimento_confirmado_titular'
          AND id_etapa_destino = 4
    ) OR NOT EXISTS (
        SELECT 1
        FROM chatbot.etapa_transicao
        WHERE id_etapa_origem = 3
          AND evento = 'destino_atendimento_confirmado_dependente'
          AND id_etapa_destino = 5
    ) THEN
        RAISE EXCEPTION 'Transições da confirmação estão incompletas';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM chatbot.conversa
        WHERE id_etapa_atual IS NOT NULL
    ) <> v_antes.conversas_com_etapa THEN
        RAISE EXCEPTION 'Quantidade de conversas com etapa foi alterada';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM chatbot.historico_mensagens
        WHERE id_etapa IS NOT NULL
    ) <> v_antes.historicos_com_etapa THEN
        RAISE EXCEPTION 'Quantidade de históricos com etapa foi alterada';
    END IF;

    IF (
        SELECT COUNT(*)
        FROM chatbot.respostas_desafios
        WHERE id_etapa IS NOT NULL
    ) <> v_antes.respostas_com_etapa THEN
        RAISE EXCEPTION 'Quantidade de respostas com etapa foi alterada';
    END IF;
END
$validar_migracao_etapa3$;

-- Resumo visível para a revisão antes do COMMIT.
SELECT
    id_etapa,
    nome_etapa,
    encerra_automaticamente,
    bloqueio_dias,
    elegivel_funil
FROM chatbot.etapa
ORDER BY id_etapa;

SELECT
    id_etapa_origem,
    evento,
    id_etapa_destino
FROM chatbot.etapa_transicao
ORDER BY id_etapa_origem, evento;

COMMIT;
