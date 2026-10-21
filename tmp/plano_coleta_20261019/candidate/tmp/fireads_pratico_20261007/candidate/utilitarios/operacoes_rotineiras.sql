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
1. HISTÓRICO DE TODAS AS CONVERSAS — UMA LINHA POR MENSAGEM
===============================================================================

Finalidade:
  - Monitorar todas as conversas da unidade selecionada.
  - Exibir uma linha independente para cada mensagem do cliente ou do bot.
  - Repetir id_cliente, nome_cliente, telefone e id_conversa em todas as linhas.
  - Manter clientes, conversas e mensagens em ordem cronológica.
  - Servir como base simples para DBeaver, planilhas, dashboards e interfaces.

Filtro:
  - Atualmente consulta somente a unidade de id 1.
  - Para consultar outra unidade, altere apenas o valor do WHERE.

Formato da coluna "mensagem":
  - Contém somente o conteúdo textual da mensagem.
  - Quando a mensagem for mídia sem texto, informa seu tipo.

Remetente:
  - A coluna "quem_enviou" informa separadamente se a mensagem é do cliente
    ou do bot.
*/

SELECT
    cliente.id_cliente,
    cliente.nome AS nome_cliente,
    cliente.waid_telefone AS telefone,
    conversa.id_conversa,
    historico.quem_enviou,

    COALESCE(
        NULLIF(BTRIM(historico.conteudo_texto), ''),
        FORMAT(
            '[mensagem sem conteúdo textual: %s]',
            COALESCE(
                historico.tipo_mensagem,
                'tipo desconhecido'
            )
        )
    ) AS mensagem

FROM chatbot.conversa AS conversa

INNER JOIN chatbot.cliente AS cliente
    ON cliente.id_cliente = conversa.id_cliente

INNER JOIN chatbot.historico_mensagens AS historico
    ON historico.id_conversa = conversa.id_conversa

WHERE conversa.id_unidade = 1

ORDER BY
    cliente.id_cliente,
    conversa.iniciou_em,
    conversa.id_conversa,
    historico.received_data_hora,
    historico.id_mensagem;




















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
