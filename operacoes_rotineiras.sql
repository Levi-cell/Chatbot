/*
===============================================================================
CONSULTAS ROTINEIRAS DO CHATBOT
===============================================================================

Arquivo destinado a consultas e operações manuais executadas no DBeaver.

Regras:
  - Cada consulta deve explicar sua finalidade e o formato do resultado.
  - Consultas de leitura e operações destrutivas devem permanecer em seções
    separadas e claramente identificadas.
  - Operações destrutivas nunca devem ser executadas sem conferir o ambiente,
    interromper os serviços envolvidos e compreender os dados removidos.
*/


/*
===============================================================================
1. HISTÓRICO COMPLETO DAS CONVERSAS COM ATIVIDADE NAS ÚLTIMAS 48 HORAS
===============================================================================

Finalidade:
  - Identificar os clientes que conversaram com alguma unidade nas últimas
    48 horas.
  - Exibir uma linha para cada conversa encontrada.
  - Apresentar os dados do cliente, profissão, unidade, dependente e etapa.
  - Reunir todas as mensagens da conversa em ordem cronológica.

Comportamento do período:
  - A conversa entra no relatório quando possui pelo menos uma mensagem nas
    últimas 48 horas.
  - Depois que a conversa é selecionada, todo o seu histórico é apresentado,
    inclusive mensagens anteriores ao período, preservando o contexto completo.

Visualização no DBeaver:
  - Cada conversa aparece em uma linha.
  - Abra a célula "mensagens_em_ordem" para visualizar o diálogo formatado.
*/

WITH conversas_com_atividade_recente AS (
    SELECT DISTINCT
        hm.id_conversa
    FROM chatbot.historico_mensagens AS hm
    WHERE hm.received_data_hora >= NOW() - INTERVAL '48 hours'
),

conversas_numeradas AS (
    SELECT
        c.*,
        ROW_NUMBER() OVER (
            PARTITION BY c.id_cliente
            ORDER BY c.iniciou_em, c.id_conversa
        ) AS numero_conversa_cliente
    FROM chatbot.conversa AS c
),

historico_agrupado AS (
    SELECT
        hm.id_conversa,
        COUNT(*) AS total_mensagens,
        MIN(hm.received_data_hora) AS primeira_mensagem_em,
        MAX(hm.received_data_hora) AS ultima_mensagem_em,

        STRING_AGG(
            FORMAT(
                E'[%s] %s | etapa %s | tipo=%s%s\n%s',
                TO_CHAR(
                    hm.received_data_hora
                        AT TIME ZONE 'America/Sao_Paulo',
                    'DD/MM/YYYY HH24:MI:SS'
                ),
                CASE hm.quem_enviou
                    WHEN 'cliente' THEN 'CLIENTE'
                    WHEN 'bot' THEN 'BOT'
                    ELSE UPPER(hm.quem_enviou)
                END,
                COALESCE(hm.id_etapa::TEXT, '-'),
                COALESCE(hm.tipo_mensagem, '-'),
                CASE
                    WHEN hm.status_envio IS NOT NULL
                    THEN ' | status=' || hm.status_envio
                    ELSE ''
                END,
                COALESCE(
                    NULLIF(BTRIM(hm.conteudo_texto), ''),
                    FORMAT(
                        '[mensagem sem conteúdo textual: %s]',
                        COALESCE(hm.tipo_mensagem, 'tipo desconhecido')
                    )
                )
            ),
            E'\n\n'
            ORDER BY
                hm.received_data_hora,
                hm.id_mensagem
        ) AS mensagens_em_ordem

    FROM chatbot.historico_mensagens AS hm

    INNER JOIN conversas_com_atividade_recente AS recente
        ON recente.id_conversa = hm.id_conversa

    GROUP BY hm.id_conversa
)

SELECT
    cliente.id_cliente,
    cliente.nome AS nome_cliente,
    cliente.waid_telefone AS telefone_whatsapp,
    cliente.email,
    cliente.idade AS idade_cliente,

    conversa.id_conversa,
    conversa.numero_conversa_cliente,

    unidade.id_unidade,
    unidade.nome AS nome_unidade,

    conversa.profissao,
    conversa.status_dependente,

    dependente.nome_dependente,
    dependente.idade AS idade_dependente,

    CASE
        WHEN conversa.status_dependente IS TRUE
            THEN COALESCE(
                dependente.nome_dependente,
                'Dependente sem nome registrado'
            )
        ELSE cliente.nome
    END AS pessoa_atendida,

    CASE
        WHEN conversa.status_dependente IS TRUE
            THEN dependente.idade
        ELSE cliente.idade
    END AS idade_pessoa_atendida,

    conversa.id_etapa_atual,
    etapa.nome_etapa AS etapa_atual,
    conversa.status_ativa,
    conversa.motivo_encerramento,

    TO_CHAR(
        conversa.iniciou_em AT TIME ZONE 'America/Sao_Paulo',
        'DD/MM/YYYY HH24:MI:SS'
    ) AS conversa_iniciada_em,

    TO_CHAR(
        conversa.finalizou_em AT TIME ZONE 'America/Sao_Paulo',
        'DD/MM/YYYY HH24:MI:SS'
    ) AS conversa_finalizada_em,

    historico.total_mensagens,

    TO_CHAR(
        historico.primeira_mensagem_em
            AT TIME ZONE 'America/Sao_Paulo',
        'DD/MM/YYYY HH24:MI:SS'
    ) AS primeira_mensagem_em,

    TO_CHAR(
        historico.ultima_mensagem_em
            AT TIME ZONE 'America/Sao_Paulo',
        'DD/MM/YYYY HH24:MI:SS'
    ) AS ultima_mensagem_em,

    historico.mensagens_em_ordem

FROM conversas_com_atividade_recente AS recente

INNER JOIN conversas_numeradas AS conversa
    ON conversa.id_conversa = recente.id_conversa

INNER JOIN chatbot.cliente AS cliente
    ON cliente.id_cliente = conversa.id_cliente

INNER JOIN chatbot.unidade AS unidade
    ON unidade.id_unidade = conversa.id_unidade

LEFT JOIN chatbot.dependente AS dependente
    ON dependente.id_conversa = conversa.id_conversa

LEFT JOIN chatbot.etapa AS etapa
    ON etapa.id_etapa = conversa.id_etapa_atual

INNER JOIN historico_agrupado AS historico
    ON historico.id_conversa = conversa.id_conversa

ORDER BY
    cliente.id_cliente,
    conversa.numero_conversa_cliente,
    conversa.id_conversa;




















/*
===============================================================================
2. RESET COMPLETO DAS TABELAS OPERACIONAIS E DE SUAS IDENTIDADES
===============================================================================

ATENÇÃO — OPERAÇÃO DESTRUTIVA:
  - Exclui definitivamente todos os registros das tabelas listadas.
  - Reinicia suas sequências de IDs; os próximos registros começarão em 1.
  - Não execute este bloco por engano nem junto com a consulta anterior.
  - Em produção, interrompa previamente webhook, flow_worker e funil_worker.
  - O COMMIT torna a exclusão definitiva.

Dados preservados:
  - clientes;
  - unidades;
  - integrações do funil;
  - clientes bloqueados na Meta;
  - catálogo de etapas e mapa de transições.

Finalidade:
  - Limpar somente os dados operacionais para iniciar um novo ciclo de testes
    ou atendimento sem remover cadastros estruturais.
  - Confirmar, antes do COMMIT, que todas as tabelas afetadas ficaram vazias.

Proteção:
  - RESTRICT impede que o PostgreSQL apague automaticamente outras tabelas não
    declaradas por meio de CASCADE.
  - Qualquer erro anterior ao COMMIT desfaz toda a operação.
*/

BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

TRUNCATE TABLE
    chatbot.historico_mensagens,
    chatbot.respostas_desafios,
    chatbot.pesquisa_satisfacao,
    chatbot.funil_envios,
    chatbot.dependente,
    chatbot.fila_mensagens,
    chatbot.conversa,
    chatbot.webhook_flood_evento
RESTART IDENTITY
RESTRICT;

SELECT 'conversa' AS tabela, COUNT(*) AS registros
FROM chatbot.conversa

UNION ALL
SELECT 'dependente', COUNT(*)
FROM chatbot.dependente

UNION ALL
SELECT 'fila_mensagens', COUNT(*)
FROM chatbot.fila_mensagens

UNION ALL
SELECT 'historico_mensagens', COUNT(*)
FROM chatbot.historico_mensagens

UNION ALL
SELECT 'respostas_desafios', COUNT(*)
FROM chatbot.respostas_desafios

UNION ALL
SELECT 'pesquisa_satisfacao', COUNT(*)
FROM chatbot.pesquisa_satisfacao

UNION ALL
SELECT 'funil_envios', COUNT(*)
FROM chatbot.funil_envios

UNION ALL
SELECT 'webhook_flood_evento', COUNT(*)
FROM chatbot.webhook_flood_evento;

COMMIT;
