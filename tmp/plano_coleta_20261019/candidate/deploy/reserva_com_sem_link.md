# Implantação da reserva com e sem link

Esta atualização acrescenta a escolha de turno e o contato comercial para
unidades sem plataforma de agendamento. O código e o catálogo de etapas do
banco devem entrar juntos. Não executar o setup inicial nem reaplicar migrações
históricas em um banco existente.

## Arquivos e requisitos

- Migração: [`migrations/20261003_reserva_com_sem_link.sql`](migrations/20261003_reserva_com_sem_link.sql).
- Reversão restrita: [`rollback/20261003_reserva_com_sem_link.sql`](rollback/20261003_reserva_com_sem_link.sql).
- A base esperada tem 22 etapas e o mapa da V1.8.1. O SQL valida nomes, políticas,
  transições e referências antes de alterar dados. Um catálogo diferente exige
  análise, sem contornar as validações.
- Continuam PyWa 4.5.0, os requisitos atuais, os cinco serviços e o ambiente
  existente. Não há pacote, token ou variável de ambiente nova nesta atualização.
- As tabelas de negócio são `managed=False`: `manage.py migrate` não executa
  esta migração. Usar o arquivo SQL completo.

## Corte coordenado na VM e no banco

1. Conferir a árvore limpa, o commit instalado e o commit remoto. Registrar o
   commit anterior para eventual reversão. Não descartar alterações locais.
2. Parar primeiro `chatbot-worker-followup.service`; depois parar webhook,
   flow, Funil e Consumo Meta. Confirmar que os cinco serviços estão inativos.
   Não editar o Admin nem escrever diretamente no banco durante o corte.
3. Fazer e confirmar um snapshot/backup restaurável do RDS **nesse corte**.
   O backup do Git preserva código, mas não substitui o backup dos atendimentos.
4. Atualizar o código com `git pull --ff-only origin prod`, mantendo os serviços
   parados. Não iniciar código antigo com o catálogo novo, nem código novo com
   o catálogo antigo.
5. Executar **todo** o SQL de migração no DBeaver, de `BEGIN` até `COMMIT`, com
   a role de migração. O script mantém FKs ativas, bloqueia as tabelas envolvidas
   e inclui as partições do histórico. Em caso de erro, executar `ROLLBACK`,
   manter os serviços parados e investigar a mensagem antes de repetir.
6. Confirmar as 24 etapas e as 28 transições, o domínio de `conversa.turno` e
   `unidade.link_agendamento` opcional. Conferir a saída das contagens por etapa.
7. Executar `check --deploy` e `collectstatic --noinput` com o ambiente e o
   usuário dos serviços. Esta atualização muda o JavaScript do painel e a sua
   versão no template; precisa de coleta dos estáticos e recarga do Python.
8. Iniciar webhook e flow, conferir estado/logs, depois Funil e Consumo Meta.
   Reativar follow-up por último, após confirmar que o flow compatível está ativo.
9. Verificar os cinco serviços, os endpoints públicos e o painel. Em um contato
   de homologação autorizado, percorrer cada rota e conferir o botão comercial,
   o turno salvo, a satisfação e o recebimento no CRM.

O SQL é reexecutável: ao encontrar o catálogo final, não desloca etapas novamente
nem apaga turnos coletados. Não é necessário repetir os seeds após executá-lo.

## O que a migração preserva

| Antes | Depois | Significado |
|---|---|---|
| 18 | 20 | Plataforma de reserva |
| 19 | 21 | Nota de satisfação |
| 20 | 22 | Decisão de comentar |
| 21 | 23 | Comentário |
| 22 | 24 | Finalização e bloqueio de 30 dias |

O remapeamento abrange conversa, histórico e suas partições, respostas de desafios,
checkpoints de retomada e mapa de transições. Os IDs das transições existentes
são mantidos. A migração não reabre conversas, não limpa filas, não reseta locks,
não apaga respostas nem modifica recibos de Funil/follow-up. A recuperação normal
do worker continua tratando mensagens pendentes e locks abandonados.

As etapas 18 e 19 novas significam, respectivamente, preferência de turno e
contato comercial. `turno` começa nulo e aceita somente `manha`, `tarde`, `noite`
ou `NULL`. O Consumo Meta, seus fusos, dados mensais e agenda não são alterados.

Consultas de conferência após o SQL:

```sql
SELECT id_etapa, nome_etapa, encerra_automaticamente, bloqueio_dias, elegivel_funil
FROM chatbot.etapa ORDER BY id_etapa;

SELECT id_etapa_origem, evento, id_etapa_destino
FROM chatbot.etapa_transicao ORDER BY id_etapa_origem, evento;

SELECT table_name, column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_schema = 'chatbot'
  AND ((table_name = 'conversa' AND column_name = 'turno')
    OR (table_name = 'unidade' AND column_name = 'link_agendamento'));
```

## Alterar o link depois da implantação

Uma nova saída da triagem usa o link atual da unidade. Adicionar link não
redireciona uma conversa que já está na escolha de turno ou no contato comercial:
ela conclui a rota iniciada. O Funil continua verificando a configuração vigente.

**Antes de retirar um link, concluir ou tratar administrativamente as conversas
ativas na etapa 20.** Essa etapa exige uma plataforma válida para reapresentar
a reserva. Não existe conversão automática de 20 para 18. A validação do contexto
recusa um novo envio sem link; uma resposta já registrada é recuperada normalmente
no retry, mesmo se o link tiver sido retirado depois do envio.

Consulta de leitura, substituindo `123` pela unidade desejada:

```sql
SELECT id_conversa, id_etapa_atual, status_ativa
FROM chatbot.conversa
WHERE id_unidade = 123 AND status_ativa IS TRUE AND id_etapa_atual = 20;
```

## Reversão

Antes de retomar atendimentos, o SQL de rollback pode restaurar o catálogo antigo
e o contrato anterior das colunas. Ele recusa referências às novas etapas 18/19,
turnos preenchidos e unidades com link nulo. Só retornar o código antigo depois
da reversão do banco ter concluído com sucesso.

Depois de existirem dados da nova rota, não forçar esse rollback nem apagar dados
para fazê-lo passar. Corrigir adiante ou restaurar o snapshot e o código do mesmo
corte, avaliando os atendimentos ocorridos desde então. Nenhum rollback local
desfaz mensagens já enviadas ao WhatsApp ou aceitas pelo CRM.

## Validação local realizada

- Suíte completa: 452 testes aprovados, sem testes ignorados, em Python 3.12 e
  PyWa 4.5.0. As integrações usaram PostgreSQL 17.11 descartável em loopback.
- Depois da revisão final, os 34 testes das rotas e da migração foram repetidos
  com sucesso. Django `check`, análise dos 67 arquivos Python criados/alterados,
  sintaxe JavaScript e `git diff --check` também passaram.
- Migração e reversão, reexecução, catálogo divergente, FK desconhecida com
  `ON DELETE SET NULL`, partições do histórico, dados de Consumo e recuperação
  com resposta já enviada após mudança do link.
- Rotas de titular/dependente, turno, Funil, follow-up, satisfação, regras de
  idade/e-mail, locks, autorização do painel, CSVs e PDFs.
- Prévia com dados fictícios revisada no computador e em 390 px de largura:
  detalhes de turno, navegação, relatório de 24 etapas e Consumo, sem rolagem
  horizontal da página nem erros de JavaScript observados.

Meta e CRM foram simulados nos testes. O banco de produção e a VM não foram
alterados durante a implementação local; a conferência real pertence ao deploy.
