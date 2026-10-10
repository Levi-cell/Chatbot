# FireAds — aplicação e deploy

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

## Correção local da espera na abertura — 09/10/2026

O erro `ReadTimeout` da conversa 285 foi provocado pelo limite local de leitura
de 8 segundos por requisição. Havia ainda um orçamento de 25 segundos para as
duas abas e seus redirecionamentos. Após a revisão solicitada pelo usuário,
a abertura tem **300 segundos no total**, compartilhados por Google, Meta,
redirecionamentos e espera por vaga. A leitura HTTP usa o tempo restante, sem o
corte antigo de 8 segundos. O prazo não é 300 segundos para cada aba.

A leitura roda em uma thread que só consulta e interpreta os formulários. Enquanto
ela não termina, a mensagem volta à fila por 5 segundos, sem consumir tentativas,
sem gravar uma decisão orgânica por demora antes do limite e sem enviar a
primeira resposta. As demais
conversas continuam sendo atendidas. A retomada reutiliza a leitura e adquire
novas reservas da conversa/mensagem antes de importar; não mantém uma transação
SQL aberta durante a espera. Todo SQL dessa abertura fica nos repositories.

Há no máximo quatro leituras simultâneas por processo. Outras consultas aguardam
na fila; esse limite não interrompe as já iniciadas. Resultados confirmados são
retirados da memória, que também limita resultados abandonados. Um reinício
pode refazer o GET pendente, mas nunca repete um POST de abertura, pois ela só lê.
O início da espera fica preservado em `consulta_fireads.atualizado_em` enquanto
a consulta está pendente. Retentativas e reinícios do worker não renovam os cinco
minutos; uma nova conversa recebe um prazo novo. Ao atingir o limite, a próxima
passagem do worker conclui como orgânico, com `resultado=erro` e
`motivo=tempo_limite_300s`, e inicia o atendimento completo. Resultados HTTP tardios
não alteram essa decisão nem importam parcialmente os formulários. Falhas efetivas
de conexão, HTTP ou contrato conservam a regra anterior de erro.

Continua sendo um único serviço `worker_flow`; as threads auxiliares só fazem
GET/interpretação e não recebem conexão SQL nem enviam mensagens. A fila do banco
mantém a ordem das mensagens. Não é necessário criar outro serviço na VM.

No Apps Script fornecido pela FireAds, `doGet` devolve todos os registros da aba;
não há filtro por telefone. O cliente já envia `sheet` e `abas=0`, consultando
as duas abas configuradas e dispensando o inventário de abas. Uma otimização na
FireAds seria uma consulta por telefone que retorne só os registros correspondentes
das duas fontes, com dados recentes dos formulários. O código fornecido já tem
cache e leitura em lote; sua presença não permite diagnosticar a execução lenta
sem os tempos internos do Apps Script. Formato compacto reduz transferência, mas
continua lendo a aba e não garante resolver a variação de tempo observada.

O diagnóstico encontrou ainda dois formulários Google desse telefone, com nome,
e-mail, destinatário e data idênticos. Duplicações equivalentes da mesma fonte e
data agora contam como uma candidatura na importação. Dados distintos, fontes
distintas e datas não comparáveis conservam a proteção contra ambiguidade.
A proteção contra duplicados na escrita do dashboard permanece independente.

**Esta correção exige deploy do código, sem migração SQL.** Conversas já iniciadas
(inclusive a 285, que gravou o timeout) não são reiniciadas nem reclassificadas.
Para validar a abertura corrigida em produção, é necessária uma nova conversa.

Diagnóstico somente leitura, sem alterar banco, Redis ou dashboard:

```powershell
& 'C:\Chatbot\venv\.venv\Scripts\python.exe' -X utf8 utilitarios/fireAds/diagnostico_tempo_consulta.py 71994111866
```

Os logs `fireads_consulta_iniciada` e `fireads_consulta_concluida` incluem a conversa,
o resultado e a duração, sem nome, telefone ou e-mail. A mensagem pendente aparece
em nível DEBUG como `fireads_consulta_pendente`.

Validação após a revisão de 300 segundos: **77 testes passaram** (63 unitários e
14 em PostgreSQL 16 local descartável). Incluem o orçamento compartilhado,
resposta tardia e preservação do prazo após retomadas e reinício. As sondas reais
ao dashboard foram somente GET.
Na última sonda, Google demorou 63,50 segundos e Meta 2,86 segundos. A simulação
do telefone de teste retornou `resultado=importado`, `origem=google` e
`status_dependente=true`, sem gravar a decisão no banco de produção.

## Implementação

- Adaptador HTTP e regras de importação em `core/integrations/fireads`.
- Consultas e entregas persistidas em `core/repositories/fireads`.
- Consulta de abertura em `workers/worker_flow/fireads.py`, antes da primeira
  resposta. Aguarda HTTP fora do ciclo e só persiste sob a reserva da conversa.
  Falha efetiva, ambiguidade ou prazo de 300 segundos esgotado inicia como orgânico;
  enquanto aguarda dentro do prazo, a mensagem permanece pendente.
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
