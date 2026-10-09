# FireAds — aplicação e deploy

Código aplicado localmente em **08/10/2026**, sobre o backup
`37b0265` (V1.9.2). **O deploy e a migração no banco de produção ainda não foram
executados.** Não iniciar os workers com o código novo sobre o schema antigo.

## Implementação

- Adaptador HTTP e regras de importação em `core/integrations/fireads`.
- Consultas e entregas persistidas em `core/repositories/fireads`.
- Consulta de abertura em `workers/worker_flow/fireads.py`, antes da primeira
  resposta e sob a reserva da conversa. Falha ou ambiguidade inicia como orgânico.
- Envio ao dashboard em `workers/worker_funil/fireads.py`, depois do sucesso no
  Funil e com fila própria. Não depende de haver novos leads para o Funil no ciclo.
- Personalização separada da identidade da unidade, com inline obrigatório no
  Admin e visualização pelo nome da unidade. Configurações FireAds são opcionais,
  únicas por unidade e começam desativadas.
- Tabela `chat` universal; conversa e consulta FireAds têm vínculos conferidos no
  banco. Uma nova conversa atualiza a consulta do chat, mas preserva a decisão e
  os dados usados na conversa anterior.

## Ajustes confirmados durante a aplicação

- A leitura real do Google já retornou `Para mim` e `Para meu avô/avó`, compatíveis
  com a nova interpretação. Registros antigos com apenas faixa/perfil etário
  continuam insuficientes para decidir titular/dependente.
- Na Meta, foi observado `pai_ou_mae`. O mapeamento reconhece esse identificador,
  `para_mim`, `mim_e_outra` e as variantes explícitas previstas no contrato.
- O Admin valida a personalização antes de iniciar o cadastro da unidade na Meta.
- Messages apenas compõe o texto da abertura: a decisão de tratamento permanece
  no worker, e o sender preserva o registro do tratamento enviado.
- O repositório de entrega recupera o conteúdo congelado antes de reconstruí-lo.
- Os testes de banco foram adaptados à estrutura atual; os de migração histórica
  conservam os mapas de suas versões originais.

## Validação

**487 testes passaram, sem falhas, erros ou testes pulados.** Foram usados sete
bancos PostgreSQL 16 locais e descartáveis. A suíte inclui migração/reexecução,
preservação dos dados, locks concorrentes, importação, retry, envio pendente,
reconciliação, reserva com/sem link, follow-up, painel, consumo Meta e relatórios.
Também foram conferidas a sintaxe Python e as verificações Django de models/Admin.

As consultas reais à FireAds foram somente leitura. Os POSTs à Meta, ao Funil e
ao dashboard foram simulados nos testes. Não houve envio de leads de teste.

## Ordem de implantação

1. Subir e conferir a revisão de código que será implantada.
2. Parar webhook e workers que usam o banco, conforme o procedimento habitual.
3. Atualizar o código da VM.
4. Executar **inteiro** no DBeaver o arquivo
   [`20261007_fireads_chat_customizacao.sql`](../deploy/migrations/20261007_fireads_chat_customizacao.sql).
   Ele também está no último passo do [plano prático](integracao_fireads.md).
5. Conferir o resultado: uma personalização por unidade, nenhuma conversa sem
   chat, 30 transições e nenhuma integração ativa por padrão. Um erro aborta a
   transação; não continuar executando apenas partes posteriores do SQL.
6. Executar as verificações Django e iniciar os serviços. Conferir saúde e logs.
7. No Admin, cadastrar a integração de Santo André pelo nome, com o endereço
   `/exec` e as abas padrão. `url_operation` é só referência do editor.
8. Confirmar a configuração de fuso da planilha e a desativação da antiga
   sincronização da agência. Marcar o contrato validado e ativar a integração.

O horário exibido no dashboard sugere Brasília, mas não confirma a configuração
da planilha. Preencher `America/Sao_Paulo` apenas após essa confirmação. Enquanto
o campo estiver nulo, uma correspondência única válida pode ser importada;
registros cujas datas não possam ser comparadas resultam em atendimento orgânico.
Nenhum fuso ou Data/Hora é imposto ao dashboard nas escritas.

## Limites conhecidos

A API da planilha não oferece atualização condicional nem chave de idempotência
no servidor. A leitura antes da escrita, os locks locais e os marcadores por
conversa reduzem duplicações. Uma edição/ordenação externa entre GET e POST ainda
pode conflitar; essa limitação foi aceita. Não há exclusão automática de leads.

O rollback desta entrega não é apenas voltar o Git: o schema move colunas e cria
vínculos obrigatórios. Qualquer reversão após migrar deve considerar o banco e os
novos dados em conjunto. Não executar migrações antigas ou o setup para desfazer
essa alteração.
