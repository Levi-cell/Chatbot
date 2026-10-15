# FireAds — aplicação e deploy

> Atualização local de 14/10/2026: o contrato vigente usa somente a aba geral,
> `Para quem é` e `Canal`, com seleção dos canais elegíveis antes da recência.
> Consulte [o plano aplicado e o procedimento de deploy](../atualizar_envio.md).
> As descrições abaixo de duas/três abas e seus SQLs são históricas; não as
> reaplique neste deploy. A proposta de coleta parcial continua sem implementação.


Código aplicado localmente em **08/10/2026**, sobre o backup
`37b0265` (V1.9.2). **Deploy da V1.10.0 confirmado em 09/10/2026**, no commit
`49af8d5`, com a migração executada e os cinco serviços ativos. A conferência da
VM retornou 4 unidades, 4 personalizações, 4 linhas na view, nenhum vínculo de
chat inválido, 30 transições e nenhuma integração FireAds ativa. Webhook e login
responderam HTTP 200. O cadastro/ativação de Santo André no Admin continua sendo
a etapa seguinte da integração.

A [separação visual no Admin e suspensão por status_pagamento](status_pagamento_e_admin.md)
é uma atualização local posterior, com SQL próprio e ainda sem deploy. Não está
incluída no commit `49af8d5` já implantado.

A [leitura direta de unidade e personalização](consultas_diretas_unidade.md)
também está aplicada localmente para o próximo deploy. O código deixa de depender
da view; sua remoção está incluída no SQL unificado de suspensão por pagamento.
Os passos de implantação abaixo registram a entrega original da FireAds.

## Correção local de telefone — 09/10/2026

A busca compartilha agora a mesma regra entre produção e o utilitário
`utilitarios/fireAds/test_Dash.py`: normaliza DDI brasileiro, máscaras e prefixo
`p:+`, procura o número exato em cada aba e, se ausente, tenta a variante móvel
com/sem nono dígito. Preserva DDD e todos os demais dígitos. A variante segue a
regra do utilitário para números móveis antigos iniciados em 6, 7, 8 ou 9;
números fixos não ganham um nono dígito e DDI explícito estrangeiro é recusado.

Google e Meta continuam concorrendo pela data mais recente. Na escrita, todos os
formatos equivalentes são examinados para detectar linhas duplicadas: um único
cadastro compatível recebe só as observações; duplicados ou conflito de e-mail
permanecem pendentes. As variantes usam a mesma chave de lock por integração,
sem modificar o telefone do cliente ou o número enviado ao dashboard.

Esta correção requer deploy do código, sem migração SQL. Decisões de consultas
já concluídas permanecem gravadas; o teste da nova abertura exige uma nova
conversa. Os testes simulam chamadas externas, incluindo o caso de formulário
com nono dígito e WhatsApp sem ele.

## Consulta periódica por conversa

A proposta local de threads auxiliares no flow foi substituída pelo serviço
`worker_consulta_dash`, com resultado completo persistido e uma consulta por
conversa. Esta mudança REQUER a migração `20261009_worker_consulta_dash.sql` e a
instalação de um sexto serviço. Os detalhes de implantação, recuperação e prazo de
300 segundos estão no [guia do worker](valida_dados_parciais_fireads.md).

Os passos históricos abaixo descrevem a entrega inicial; não substituem o guia
novo nem autorizam reaplicar o SQL inicial numa instalação já atualizada.

## Implementação

- Adaptador HTTP e regras de importação em `core/integrations/fireads`.
- Consultas e entregas persistidas em `core/repositories/fireads`.
- Consulta de abertura em `workers/worker_flow/fireads.py`, antes da primeira
  resposta. Aguarda o worker de consulta e só importa sob a reserva da conversa.
  Falha efetiva, ambiguidade ou prazo de 300 segundos esgotado inicia como orgânico;
  enquanto aguarda dentro do prazo, a mensagem permanece pendente.
- Envio ao dashboard em `workers/worker_funil/fireads.py`, depois do sucesso no
  Funil e com fila própria. Não depende de haver novos leads para o Funil no ciclo.
- Personalização separada da identidade da unidade, com inline obrigatório no
  Admin e visualização pelo nome da unidade. Configurações FireAds são opcionais,
  únicas por unidade e começam desativadas.
- Tabela `chat` universal; conversa e consulta FireAds têm vínculos conferidos no
  banco. Uma nova conversa cria outra consulta; o chat é acessado por meio da conversa,
  preservando consultas e decisões anteriores.

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
