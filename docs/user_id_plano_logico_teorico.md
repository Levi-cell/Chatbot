# Plano autoritativo — `user_id`, WA ID e PyWa 4.x

## 1. Estado deste documento

Este plano substitui integralmente as versões anteriores do desenho de
`user_id`.
Ele ainda **não foi aplicado ao código operacional**.
Nesta tarefa, somente este arquivo Markdown é alterado. Todos os caminhos de
código, banco, testes e deploy citados abaixo descrevem impacto futuro; não são
arquivos a modificar agora.

A baseline operacional usada nesta revisão é a V1.0.5 com a correção que
torna a profissão obrigatória para titular e dependente, totalizando 22 etapas e
25 transições. Ela inclui a confirmação do destino, os tratamentos atuais, a
triagem por faixa etária e o detalhamento das perguntas no Funil. A futura
implementação deste plano acrescentará somente a etapa de compartilhamento
oficial do contato após o nome; por isso o estado final terá 23 etapas e 27
transições.

Os contratos de payload usados como referência são:

- `payloads/WAID.json`;
- `payloads/BSUID_USERNAME.json`;
- `payloads/WAID_BSUID_USERNAME.json`;
- `payloads/CONTACT_INFO.json`.

Os três primeiros representam combinações normais de identidade no envelope.
`CONTACT_INFO.json` representa o webhook inbound recebido como resposta ao envio
outbound `request_contact_info(...)`: o nome da chamada não aparece literalmente
no retorno; a prova persistível é `type='contacts'` com
`origin='contact_request'` e o WA ID dentro do cartão oficial.

Os nomes de dois fixtures e o nome deste próprio Markdown ainda contêm `BSUID`
por legado de arquivo; esses caminhos serão preservados para não quebrar as
referências da tarefa. No contrato, no banco, no código e nos logs o nome correto
será sempre `user_id`. Não são dois identificadores diferentes.

Esses arquivos são fixtures representativas, e não capturas reais de produção.
Antes do deploy, o primeiro payload bruto real de cada formato deverá ser salvo,
anonimizado e confrontado com os testes.

Quando este plano for aplicado, cada passo deverá apresentar o conteúdo completo
de todo arquivo criado ou alterado. Não serão aceitos trechos soltos que
dependam de interpretação durante o deploy. Como os senders ainda serão
refinados antes da aplicação, o apêndice de código completo deverá ser
regenerado a partir do commit definitivo imediatamente antes da implementação;
o contrato comportamental e de banco deste documento já é autoritativo.

## 2. Objetivo e limites

O objetivo é aceitar os dois identificadores técnicos enviados pela Meta e
preservar uma informação complementar:

1. WA ID, identificador técnico prioritário;
2. `user_id` privado e escopado ao negócio, usado como fallback de destinatário
   e de identidade de negócio somente no início do atendimento enquanto o WA ID
   ainda não foi compartilhado; no transporte inbound ele continua sendo aceito
   quando for o único identificador que a Meta entregar;
3. username opcional, salvo apenas como informação adicional.

Prioridade técnica:

```text
wa_id conhecido                          -> usar wa_id
wa_id ausente nas etapas iniciais        -> usar user_id
username                                 -> snapshot e informação opcional no Funil
etapa posterior sem wa_id                -> não enviar
```

O plano não autoriza:

- mudar os pontos ou a ordem de `commit` e `rollback` do `flow_worker`;
- mudar posse da fila, dequeue, quantidade de retries ou autocura;
- deslocar `reagendar_se_houver_mensagem_anterior()`;
- alterar a semântica de `reagendar_mensagem_sem_erro()` ou
  `reagendar_mensagem()`;
- deslocar ou remover `bot_resposta_atual()`;
- criar advisory lock novo no worker;
- mudar a posição de `chatbot.lock_conversa()`;
- alterar os fluxos A/B/C de turno;
- criar salto, retorno ou avanço fora de `chatbot.etapa_transicao`;
- usar username como identidade, lock, destinatário Meta ou chave de conversa;
- usar `user_id` como fallback de sender depois da etapa obrigatória de
  compartilhamento do WA ID;
- usar WAMID como identidade da pessoa;
- executar `ALTER TABLE` em Python;
- usar `metadata.display_phone_number` como telefone do cliente.

Há somente três extensões comportamentais aprovadas neste plano:

1. transportar `wa_id`, `user_id` e username como dados adicionais nos contextos
   já existentes, deixando o resolver escolher para o sender `wa_id` ou, apenas
   antes do compartilhamento obrigatório, `user_id`;
2. reconciliar um cliente provisório com o cliente global canônico quando um
   payload conjunto ou o compartilhamento oficial provar o vínculo;
3. preservar uma única janela anti-flood para `user_id` e `wa_id` oficialmente
   vinculados na mesma unidade, somando as duas rajadas e deduplicando-as por
   WAMID, sem inferir equivalência por username, nome ou proximidade temporal.

A reconciliação é um efeito de dados executado pelo mesmo cursor dentro da
transação que `validar_banco_mensagem()` já utiliza. Ela não autoriza novo
`commit`, `rollback`, lock, prazo, contador de retry, requeue, `continue`, retorno
terminal ou mudança da ordem do ciclo. `validar_banco_mensagem()` continua
devolvendo o contexto normal esperado pelo restante do `flow_worker`.

O plano não cria tratamento especial para Funil, denylist ou bloqueio dentro da
transação de reconciliação. Funil e denylist conservam seu comportamento atual.
A continuidade anti-flood aprovada é executada pelo guard do webhook e pelas
camadas próprias de cache/repositório, fora da transação do `flow_worker`; a
reconciliação apenas confirma depois o vínculo permanente que esse guard pode
usar.

O WAMID continua servindo para deduplicar e correlacionar uma mensagem. Ele não
substitui a identidade usada pelo turno, que continuará combinando a identidade
técnica do cliente com `id_phone_unidade`.

## 3. Contrato dos payloads

### 3.1 Campos da unidade

Dentro de `entry[].changes[].value`:

- `metadata.phone_number_id`: ID técnico do número da unidade e fonte
  autoritativa para localizar a unidade;
- `metadata.display_phone_number`: número público da unidade;
- `entry[].id`: WABA ID;
- `id_portfolio`: não vem no webhook; será lido do cadastro da unidade.

Nenhum desses campos identifica o cliente.

### 3.2 Campos do cliente

| Informação | Caminho principal | Fallback permitido |
|---|---|---|
| WA ID do remetente | `value.contacts[].wa_id` | `value.messages[].from` |
| User ID | `value.contacts[].user_id` | `value.messages[].from_user_id` |
| Username | `value.contacts[].profile.username` | nenhum |

No retorno oficial de compartilhamento:

| Informação | Caminho |
|---|---|
| Tipo | `value.messages[].type = "contacts"` |
| Origem | `value.messages[].contacts[].origin = "contact_request"` |
| Telefone exibido | `value.messages[].contacts[].phones[].phone` |
| WA ID compartilhado | `value.messages[].contacts[].phones[].wa_id` |

Existem dois arrays `contacts` diferentes:

- `value.contacts[]` descreve o remetente;
- `value.messages[].contacts[]` descreve o cartão de contato compartilhado.

Eles nunca podem ser confundidos.

### 3.3 Matriz de entrada

| Entrada | Webhook | Identidade técnica | Funil |
|---|---|---|---|
| WA ID + user ID + username | aceita | WA ID | WA ID + `@username` |
| WA ID + user ID | aceita | WA ID | WA ID |
| WA ID + username | aceita | WA ID | WA ID + `@username` |
| somente WA ID | aceita | WA ID | WA ID |
| user ID + username, sem WA ID, vínculo desconhecido | aceita | user ID temporariamente | exige etapa de contato |
| somente user ID, vínculo desconhecido | aceita | user ID temporariamente | exige etapa de contato |
| somente user ID já mapeado, em qualquer etapa | aceita | user ID permanece a identidade do item; cliente e WA ID canônico são resolvidos no worker | fluxo normal somente com WA ID canônico |
| somente username | ignora com HTTP 200 | inexistente | não executa |
| nenhum dos três | ignora com HTTP 200 | inexistente | não executa |

Um evento é processável quando:

```python
processavel = bool(wa_id_remetente or user_id)
```

O WA ID contido no cartão de um `contact_request` não torna o evento processável
por si só e não vira identidade do remetente. Ele é o
`wa_id_compartilhado`; no fixture atual o remetente continua processável pelo
`user_id` presente no envelope.

## 4. Decisões de identidade

### 4.1 WA ID é a identidade prioritária

O resolver escolhe o destinatário do sender a partir dos valores canônicos
carregados do banco no contexto. Nas etapas iniciais, antes do compartilhamento
obrigatório:

```python
destinatario = wa_id_banco or user_id_banco
```

Depois que a etapa obrigatória comprovar e persistir o WA ID, todos os senders
posteriores exigem `wa_id_banco`; eles não voltam silenciosamente ao `user_id`.
O username nunca entra nessa seleção.

O evento serve para alimentar a persistência. Antes do envio, o worker lê e
reconstrói os valores pelo banco e os coloca em `contexto_historico`; nenhum
resolver deve encaminhar diretamente ao sender um identificador bruto do payload.
A ausência de um campo em evento posterior nunca apaga valor já conhecido.

#### 4.1.1 Identidade do item, WA ID compartilhado e WA ID canônico

Os três papéis abaixo são distintos e não podem ser intercambiados antes da
validação bancária:

- `identidade_do_item`: identidade técnica pela qual o evento entrou. Ela é
  definida uma única vez, reconstruída a partir do snapshot da fila e permanece
  congelada durante turno, ordem, retry, logs e autocura daquele item;
- `wa_id_compartilhado`: candidato extraído exclusivamente do
  `contacts/contact_request`. Antes da prova bancária, não é destinatário, chave
  de turno, chave de cache nem identidade da conversa;
- `wa_id_canonico`: `cliente.wa_id` relido do banco depois da persistência ou
  reconciliação. Somente ele pode ser usado pelo sender que avança da etapa 2
  para a 3 e por todos os senders posteriores.

No handoff representado por `payloads/CONTACT_INFO.json`:

```text
identidade_do_item  = (user_id, user_id do remetente)
wa_id_compartilhado = WA ID do contato oficial
wa_id_canonico      = cliente.wa_id relido depois da validação
```

Persistir ou descobrir o WA ID canônico não recalcula a identidade do item no
meio do ciclo. Um retry do mesmo item reconstrói a mesma identidade original.
Essa separação é apenas de papel lógico; não cria uma quarta coluna de snapshot.

### 4.2 User ID é escopado ao negócio

O `user_id` não é global como o WA ID. O vínculo canônico será:

```text
cliente 1 --- N user_id_cliente N --- 1 unidade --- id_portfolio
```

Cada linha de `chatbot.user_id_cliente` liga exatamente um `id_cliente` a um
`user_id` dentro de uma unidade. Assim:

- o mesmo cliente global continua tendo um único `id_cliente`;
- o cliente pode ter um `user_id` diferente em cada unidade;
- a volta futura usando somente `user_id` resolve o cliente canônico sem criar
  outro cliente provisório;
- um payload que já contenha WA ID + user ID registra ou atualiza o vínculo no
  primeiro processamento, sem esperar a etapa especial;
- `id_portfolio` permanece na unidade para consultas de monitoramento e não
  entra no caminho transacional online.

O fluxo online continua isolado por:

```text
(wa_id, id_phone_unidade)
ou, sem WA ID,
(user_id, id_phone_unidade)
```

`id_portfolio` não será colocado na fila, nas chaves de turno nem nos locks.
Ele servirá a consultas futuras de monitoramento.

### 4.3 Username não é identidade

Username:

- pode ser `NULL` em todas as tabelas;
- nunca é `UNIQUE`;
- nunca seleciona cliente ou conversa;
- nunca entra em lock, turno, cache ou deduplicação;
- nunca é usado no campo `to` da Meta;
- é mostrado no funil com exatamente um `@`, quando existir.

Somente `cliente.username` representa o valor canônico mais recente. Quando um
novo payload trouxer username diferente, apenas essa coluna será atualizada.
Payload sem username preserva o valor canônico anterior.

As demais tabelas guardam snapshots históricos:

- fila, histórico e flood: username daquele evento;
- conversa: primeiro username não vazio observado naquela conversa;
- bloqueio: username conhecido no instante em que o bloqueio foi criado.

Durante uma reconciliação oficialmente provada, fila e histórico da conversa
atual podem receber preenchimento retroativo **somente onde a coluna ainda for
NULL**. Um valor não nulo nunca é reescrito. Isso enriquece os primeiros eventos
da conversa sem apagar qual username já havia sido observado em outro momento.

### 4.4 Handoff seguro de user ID para WA ID

O evento `CONTACT_INFO.json` contém o `user_id` do remetente e o novo WA ID em
`messages[].contacts[].phones[].wa_id`.

Esse evento deve:

1. localizar a conversa atual pelo `user_id` + unidade;
2. validar que se trata de `contacts + contact_request` oficial;
3. tratar o número do cartão como `wa_id_compartilhado`, persistir o WA ID
   comprovado e o vínculo `user_id_cliente`;
4. reconciliar o cliente provisório, se necessário, como efeito de dados dentro
   da validação de banco já existente;
5. reconstruir `wa_id`, `user_id` e username a partir do banco no
   `contexto_historico`;
6. usar o WA ID persistido como destinatário da resposta que avança o fluxo;
7. manter o `user_id` e o username apenas como snapshots no `contexto_envio`.

O item continua seguindo exatamente o turno que já foi adquirido para a
mensagem. Não se troca chave de turno no meio do ciclo, não se consulta a fila
pelos dois aliases, não se desloca `reagendar_se_houver_mensagem_anterior()` e
não se cria lock, commit, status, prazo ou retry. A identidade do item continua
sendo o user ID; somente o destinatário muda para o WA ID canônico depois de o
valor ter sido confirmado e relido do banco.

Existem três resultados idempotentes:

- WA ID novo: completar o próprio cliente provisório e manter a conversa;
- WA ID do mesmo cliente: somente preencher snapshots nulos e confirmar o
  vínculo;
- WA ID de um cliente global antigo: executar a reconciliação canônica descrita
  na seção 4.5.

O webhook não decide merge de cliente, porque ele não é dono do `id_cliente` nem
da conversa. Ele valida e persiste o evento; a eventual reconciliação pertence à
validação de banco já existente no worker.

### 4.5 Reconciliação do cliente global

O cenário aprovado é:

1. no passado, o cliente falou com WA ID público e recebeu um `id_cliente`;
2. depois, volta para a mesma unidade somente com `user_id`;
3. sem vínculo prévio, o sistema cria cliente provisório + conversa nova +
   `user_id_cliente` na mesma transação;
4. após responder o nome, o cliente compartilha oficialmente seu contato;
5. o WA ID oficial já pertence ao cliente global antigo.

Isso não representa duas pessoas compartilhando o mesmo WA ID. O caso esperado é
o **mesmo cliente** que antes expunha o número e, depois de ativar a privacidade,
foi visto provisoriamente apenas pelo `user_id`. A ocorrência deve ser rara, mas
é legítima; a relação `user_id_cliente` faz essa reconciliação acontecer no
máximo uma vez por cliente/unidade enquanto aquele vínculo permanecer válido.

Nesse caso, a conversa nova é legítima e será preservada. Usando o mesmo cursor
e a mesma transação que já existem em `validar_banco_mensagem()`, a reconciliação
executa somente estes efeitos de dados:

1. confirmar que o WA ID veio junto do user ID no payload ou de um
   `contacts/contact_request` oficial; username nunca prova vínculo;
2. localizar o vínculo `(user_id, id_unidade)`, o cliente provisório da conversa
   atual e o cliente canônico que já possui o WA ID;
3. confirmar que o provisório ainda não possui outro WA ID e que a conversa que
   será preservada é exatamente a conversa atual;
4. localizar eventual conversa anterior ainda ativa do cliente canônico na mesma
   unidade;
5. se ela existir e for diferente da atual, encerrá-la pelo mecanismo de
   encerramento já existente com `motivo_encerramento='ativou_user_id'`; essa
   conversa antiga é preservada e não é retomada;
6. atualizar **somente a conversa nova atual** para usar o `id_cliente`
   canônico, mantendo o mesmo `id_conversa`, a mesma etapa e os mesmos vínculos
   de fila e histórico;
7. consolidar `user_id_cliente` para ligar o user ID atual e a unidade ao cliente
   canônico: se ainda não houver linha canônica, reatribuir a linha provisória;
   se o canônico já tiver outro user ID na mesma unidade, remover primeiro a
   linha provisória comprovada e atualizar a linha canônica para o novo user ID.
   Essa ordem usa o mesmo cursor/transação e evita violar as duas restrições
   `UNIQUE`, sem criar lock ou ramo de controle;
8. preencher `wa_id`, `user_id` e username apenas nas colunas ainda `NULL` da
   conversa atual e de seus registros de fila/histórico;
9. preservar os dados já existentes do cliente canônico; o username só é
   atualizado quando o payload trouxer um valor não vazio;
10. excluir o cliente provisório somente depois de executar verificações
    explícitas de ausência de referência em `conversa`, `dependente`,
    `cliente_bloqueado_meta` e `user_id_cliente`; não basta confiar na ação da
    FK nem em uma verificação genérica não enumerada;
11. devolver o contexto normal da conversa nova para que o `flow_worker`
    continue na ordem atual e o sender envie “Para quem é o atendimento?” pelo
    WA ID lido do banco.

Histórico e fila não trocam de `id_conversa`, portanto não precisam ser movidos.
Pelo fluxo normal, o cliente provisório permanece na primeira conversa/etapa
especial até provar o WA ID, logo não deve possuir outra conversa. Se uma
referência extra impedir sua exclusão, a operação não usa cascata nem apaga dados;
o erro segue o tratamento transacional já existente.

O gate anterior é obrigatório porque `conversa.id_cliente` e
`dependente.id_cliente` possuem `ON DELETE CASCADE`, enquanto
`cliente_bloqueado_meta.id_cliente` possui `ON DELETE SET NULL`; a futura FK de
`user_id_cliente.id_cliente` será `ON DELETE RESTRICT`. Antes do `DELETE`, a
conversa atual já deve apontar ao cliente canônico, a linha provisória do vínculo
deve ter sido consolidada e cada uma dessas quatro consultas deve retornar zero.
Fila e histórico não entram nessa lista de FKs diretas porque continuam ligados
à conversa preservada. Qualquer resultado diferente de zero impede o `DELETE` e
segue o rollback/tratamento já existente, sem cascata e sem política nova.

Se a conversa canônica anterior já estiver encerrada, ela permanece intacta e a
conversa nova continua. Se um vínculo `(user_id, unidade)` apontar para cliente
com outro WA ID não nulo e incompatível, não ocorre merge por username nem por
aproximação. A inconsistência segue o rollback e o tratamento de erro que o
worker já possui; este plano não cria retorno terminal, remoção especial de fila
ou exceção nova.

Quando um payload normal já trouxer WA ID + user ID, o contrato roda de forma
simplificada: resolve pelo WA ID, cria/atualiza `user_id_cliente`, grava os três
snapshots disponíveis e preenche somente colunas `NULL` da conversa atual, fila
e histórico. Isso evita criar um provisório numa volta futura somente por user ID
sem reescrever snapshots históricos.

O repositório não usa `UPSERT` cego. Ele compara tanto o vínculo de
`(user_id, unidade)` quanto o de `(cliente, unidade)`. Se o mesmo cliente passou
a usar outro user ID e o WA ID conjunto prova o vínculo, o novo user ID passa a
ser o vínculo atual daquela unidade. Quando ele ainda aponta para o provisório e
já existe uma linha canônica com user ID antigo, a linha provisória é removida
antes da atualização da canônica; nunca se tenta apontar ambas ao mesmo
`(cliente, unidade)`. Se o novo user ID aponta para terceiro cliente com WA ID
diferente e não nulo, a transação falha sem fundir pessoas distintas.

## 5. Banco declarativo final

### 5.1 Nomes canônicos

A grafia correta é `id_portfolio`. A forma `id_portofolio` não será usada.

Estado final:

`chatbot.unidade`:

```sql
id_portfolio VARCHAR(100) NOT NULL
```

`chatbot.cliente`:

```sql
wa_id VARCHAR(50) NULL
username VARCHAR(255) NULL
```

`cliente` não recebe `user_id`: ele continua global. Os user IDs escopados
ficam exclusivamente na relação por unidade abaixo.

`chatbot.user_id_cliente`:

```sql
id_user_id_cliente BIGSERIAL PRIMARY KEY
id_cliente INTEGER NOT NULL
user_id VARCHAR(255) NOT NULL
id_unidade INTEGER NOT NULL
```

Essa é a tabela canônica do vínculo privado. O nome `user_id_cliente` fica
fixado neste contrato para não haver variações durante a implementação. As
colunas de identidade presentes nas demais tabelas continuam como snapshots
operacionais e de auditoria.

`chatbot.fila_mensagens`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

`chatbot.historico_mensagens`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

`chatbot.conversa`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

`chatbot.cliente_bloqueado_meta`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

`chatbot.webhook_flood_evento`:

```sql
wa_id VARCHAR(50) NULL
user_id VARCHAR(255) NULL
username VARCHAR(255) NULL
```

Contrato existente ampliado sem coluna nova:

```sql
chatbot.conversa.motivo_encerramento
    IN ('idade_invalida', 'foi_agendado', 'ativou_user_id')
```

O contrato final soma 22 campos listados nesta seção, contando chaves/FKs da
tabela de vínculo e colunas renomeadas. Renome não cria uma segunda cópia do
WA ID legado.

Não existirão `telefone_informado`, `username_informado`,
`telefone_contato_compartilhado`, `wa_id_contato_compartilhado`,
`bsuid_cliente`, `username_whatsapp`, `cliente_telefone`, `waid_telefone` ou
`wa_id_cliente` no estado final.

Os campos existentes de WA ID serão **renomeados**, não duplicados:

- `cliente.waid_telefone -> cliente.wa_id`;
- `fila_mensagens.cliente_telefone -> fila_mensagens.wa_id`;
- `historico_mensagens.cliente_telefone -> historico_mensagens.wa_id`;
- `cliente_bloqueado_meta.wa_id_cliente -> cliente_bloqueado_meta.wa_id`;
- `webhook_flood_evento.wa_id_cliente -> webhook_flood_evento.wa_id`.

### 5.2 Nulabilidade e integridade

As colunas de snapshot são individualmente anuláveis. Isso não significa que
uma mensagem operacional possa ficar sem identidade. Fila, histórico, conversa,
bloqueio e flood exigem pelo menos um identificador técnico:

```sql
CHECK (
    NULLIF(BTRIM(wa_id), '') IS NOT NULL
    OR NULLIF(BTRIM(user_id), '') IS NOT NULL
)
```

Cada texto opcional também impede string vazia:

```sql
CHECK (campo IS NULL OR BTRIM(campo) <> '')
```

`cliente` é a exceção ao CHECK combinado: um cliente recém-criado apenas por
user ID pode possuir `wa_id = NULL` e `username = NULL`; o vínculo técnico fica
em `user_id_cliente` e a conversa guarda seu snapshot.

Também são exceções à nulabilidade:

- `unidade.id_portfolio` é obrigatório e não vazio;
- `user_id_cliente.id_cliente`, `user_id` e `id_unidade` são obrigatórios;
- `user_id_cliente.user_id` não aceita string vazia.

`id_portfolio` recebe índice normal, não `UNIQUE`, pois o mesmo portfólio pode
administrar mais de uma unidade. O SQL de produção adiciona a coluna
temporariamente anulável, preenche um mapa explícito e validado de todas as
unidades e somente então aplica `NOT NULL`; nunca infere portfólio pelo WABA.

A tabela de vínculo impõe:

```sql
UNIQUE (user_id, id_unidade)
UNIQUE (id_cliente, id_unidade)
```

A primeira restrição impede dois clientes para a mesma identidade privada na
unidade. A segunda mantém um único user ID atual por cliente/unidade. Uma troca
só é aceita quando WA ID + user ID chegam juntos ou quando o
`contact_request` oficial prova o vínculo.

### 5.3 Índices

Não se indexa username. Os índices de identidade são duplicados por caminho,
preservando filtros e ordenações atuais:

- fila aberta por `(wa_id, id_phone_unidade, ...)`;
- fila aberta por `(user_id, id_phone_unidade, ...)`;
- conversa para auditoria/último atendimento por
  `(wa_id, id_unidade, finalizou_em DESC)` quando WA ID existe;
- conversa para auditoria/último atendimento por
  `(user_id, id_unidade, finalizou_em DESC)` quando user ID existe;
- bloqueio com a restrição `UNIQUE (wa_id, id_unidade)` existente; como o
  PostgreSQL permite múltiplos `NULL`, ela continua compatível com WA ID
  anulável;
- bloqueio parcial único por `(user_id, id_unidade)` quando user ID existe;
- bloqueio parcial único por `(id_cliente, id_unidade)` quando o cliente
  canônico já é conhecido, impedindo duas linhas da mesma pessoa/unidade depois
  da reconciliação;
- flood por `(wa_id, phone_id_unidade, received_at)`;
- flood por `(user_id, phone_id_unidade, received_at)`;
- vínculo canônico único por `(user_id, id_unidade)`;
- vínculo canônico único por `(id_cliente, id_unidade)`;
- apoio à FK/cascade de unidade por `(id_unidade, id_cliente)`;
- histórico mantém apenas seus índices cronológicos atuais; não será criado
  índice por identidade sem consulta operacional concreta que o justifique.

A fila continua usando `id_phone_unidade`. Não será adicionada uma coluna
redundante `id_unidade`.

### 5.4 DDL e migração

Os arquivos Python de deploy conterão somente o estado final de criação. Não
haverá `ALTER TABLE` em Python.

O último passo do plano conterá um único SQL puro, transacional, para produção,
com:

1. preflight do schema atual;
2. serviços parados e filas operacionais vazias;
3. renome das cinco colunas existentes de WA ID;
4. criação das colunas novas e de `user_id_cliente`;
5. preenchimento explícito de `id_portfolio` para todas as unidades e aplicação
   de `NOT NULL`;
6. remoção de `NOT NULL` dos WA IDs de snapshot;
7. inclusão de `ativou_user_id` no CHECK de encerramento;
8. constraints, FKs e índices finais;
9. atualização preservada do catálogo/mapa de etapas;
10. recriação controlada de `chatbot.dequeue_message()`;
11. pós-validação completa, incluindo ações das FKs e definição dos índices;
12. `COMMIT` apenas depois de todas as validações.

A transação desse SQL pertence exclusivamente à futura janela de migração com
os serviços parados. Ela não representa nem altera commits, rollbacks, locks ou
retries do `flow_worker` em runtime.

Como `historico_mensagens` é particionada, a migração validará pai e partições.
Como a assinatura de retorno de `dequeue_message()` mudará, não será usado
`CREATE OR REPLACE` sobre a assinatura antiga: o SQL fará `DROP FUNCTION` e
recriará a função com o mesmo CTE, filtros, ordem, `FOR UPDATE SKIP LOCKED`,
posse, incremento de retry e timestamps, alterando somente nomes/colunas de
retorno.

Essa recriação é mecânica para transportar `wa_id`, `user_id` e username lidos
da fila. Ela não autoriza qualquer mudança no algoritmo transacional da função.

## 6. Webhook

### 6.1 Extração determinística

O parser não fará busca recursiva por qualquer chave chamada `phone`. Ele usará
somente caminhos semânticos conhecidos.

A cardinalidade externa continuará igual à do webhook atual: somente
`entry[0]`, `changes[0]`, `value.contacts[0]` e `messages[0]` participam do
evento processado. Este plano não amplia um POST para vários turnos nem altera a
unidade de idempotência. Dentro da mensagem `contacts` selecionada, porém, todos
os `messages[0].contacts[*].phones[*]` serão examinados apenas para decidir se
existe um único número inequívoco compartilhado pelo botão oficial.

Ordem do WA ID do remetente (`wa_id_remetente`):

1. `value.contacts[].wa_id`;
2. `value.messages[].from`.

Ordem do WA ID compartilhado (`wa_id_compartilhado`):

1. somente em `type="contacts"` com origem `contact_request`,
   `messages[].contacts[].phones[].wa_id`;
2. somente se esse valor faltar, o `phones[].phone` do mesmo contato oficial,
   depois da normalização restrita descrita abaixo.

O parser mantém esses dois resultados separados. O WA ID compartilhado não
participa de `wa_id_remetente or user_id` usado pelos guardas do webhook, pelo
turno ou pela autocura. Ele é apenas o candidato transportado para a validação
bancária do handoff.

Ordem de user ID:

1. `value.contacts[].user_id`;
2. `value.messages[].from_user_id`.

Username:

1. `value.contacts[].profile.username`;
2. ausência é aceita e representada por `NULL`.

Regras:

- `contacts[0].wa_id` e `messages[0].from` devem coincidir quando ambos
  existirem;
- `contacts[0].user_id` e `messages[0].from_user_id` devem coincidir quando
  ambos existirem;
- divergência registra `CRITICAL`, retorna HTTP 200 e não cria fila;
- `metadata.display_phone_number` jamais participa da extração do cliente;
- `messages[].id` é WAMID, não WA ID;
- um `phones[].wa_id` explícito é preservado como `wa_id_compartilhado`
  exatamente, salvo remoção de
  espaços externos;
- nenhum dígito é acrescentado ou removido de um WA ID explícito.

O `phone` formatado é último fallback e somente na resposta oficial quando
nenhum `phones[].wa_id` explícito existir no contato oficial. Por ser fallback,
ele não é comparado nem preferido quando `phones[].wa_id` vier no mesmo contato.

Sua normalização remove caracteres de apresentação (`+`, espaço, `(`, `)`,
`-`) e valida de 10 a 15 dígitos. Para o padrão brasileiro atual do projeto:

- `DDD + 8 dígitos`: acrescentar `55`;
- `DDD + 9 + 8 dígitos`: remover somente esse nono dígito móvel e acrescentar
  `55`;
- `55 + DDD + 9 + 8 dígitos`: remover somente o nono dígito móvel;
- outro número internacional já em E.164: preservar os dígitos.

Essa transformação jamais é aplicada a um WA ID explícito. Assim, o fixture
`CONTACT_INFO.json` usa diretamente seu `phones[].wa_id`; o campo formatado
`phone` nem participa da seleção do candidato nesse caso. A regra brasileira do
fallback deverá ser confirmada com um payload real sem `phones[].wa_id` antes da
implementação.

### 6.2 Mensagem `contacts`

O tipo bruto persistido na fila continuará sendo `contacts`. Não será inventado
um tipo substituto que apague a informação original.

Como webhook e worker são processos diferentes, a origem não pode existir
somente em memória. Sem criar outra coluna, a fila persistirá:

```text
tipo_mensagem = 'contacts'
conteudo_texto = 'contact_request'  # resposta oficial
conteudo_texto = 'other'            # contato/vCard manual
```

Esse marcador normalizado distingue:

- `contact_request`: resposta ao botão oficial;
- `other`/ausente: contato ou vCard enviado manualmente.

Para tolerar as duas formas de normalização observáveis sem fazer busca
recursiva, a origem será lida exclusivamente de um destes pontos semânticos:

1. `messages[0].origin`, quando a biblioteca expuser a origem no nível da
   mensagem;
2. `messages[0].contacts[*].origin`, como ocorre no fixture
   `payloads/CONTACT_INFO.json`.

O parser reúne as origens não vazias desses dois caminhos. O marcador somente é
`contact_request` quando o conjunto resultante é exatamente
`{'contact_request'}`. Origem desconhecida, ausente ou conflitante não recebe
privilégio e é persistida como `other`.

Somente `tipo_mensagem='contacts'` com
`conteudo_texto='contact_request'`, durante a etapa especial, pode fornecer o
WA ID e avançar. Um contato manual continua recebendo tratamento de
contexto/mídia. O conteúdo de um contato não é texto livre do cliente, portanto
usar esse marcador em `conteudo_texto` não apaga uma resposta textual.

O payload pode conter vários contatos e telefones. Para a etapa especial, o
evento válido deve identificar inequivocamente o contato solicitado. Se a
origem estiver no nível da mensagem, todos os contatos pertencem à resposta
oficial; se estiver no contato, somente os contatos cujo `origin` seja
`contact_request` fornecem candidatos.

O parser coleta os valores distintos de `wa_id_compartilhado` apenas nesses
contatos oficiais: exatamente um valor avança; mais de um é ambíguo e recebe
tratamento de contexto. Somente quando não existir nenhum WA ID explícito serão
normalizados os valores distintos de `phone`; novamente, exatamente um valor
avança. Não se escolhe silenciosamente o primeiro número.

### 6.3 Ordem das proteções

A ordem atual será preservada. O webhook passa a extrair `user_id` e username
junto dos campos que já normaliza e o anti-flood passa a resolver aliases
oficialmente vinculados antes de contabilizar a janela:

1. validação de content type, tamanho, assinatura e estrutura JSON;
2. classificação do evento e extração dos identificadores;
3. denylist e tentativa de bloqueio na Meta;
4. deduplicação e flood por WAMID;
5. validação da unidade por `metadata.phone_number_id`;
6. bloqueio temporário da conversa;
7. regra de turno e inserção idempotente na mesma transação de fila;
8. resposta HTTP e tratamento atual das exceções.

O limite de 15 WAMIDs distintos em 5 segundos, o efeito do bloqueio e a posição
relativa desses guardas não mudam. São acrescentados somente TTLs auxiliares da
resolução de aliases — ponte pendente por 15 segundos, vínculo confirmado em
cache por 1 hora e ausência de vínculo por 5 segundos — e o retorno HTTP 503
fail-safe quando não for possível tomar uma decisão compartilhada segura. Antes
de promover qualquer contato compartilhado, o webhook escolhe uma única
identidade técnica para o evento pela mesma regra reconstruída no worker:

```python
if tipo_mensagem == "contacts" and origem == "contact_request" and user_id:
    tipo_identidade_do_item = "user_id"
    identidade_do_item = user_id
elif wa_id_remetente:
    tipo_identidade_do_item = "wa_id"
    identidade_do_item = wa_id_remetente
else:
    tipo_identidade_do_item = "user_id"
    identidade_do_item = user_id
```

Em eventos normais, WA ID do remetente continua prioritário. A única exceção é o
`contact_request` oficial que também possui user ID: esse item mantém user ID
como identidade congelada, mesmo se um formato futuro trouxer excepcionalmente
WA ID no envelope. Isso impede que o WA ID do cartão ou do envelope troque a
chave do handoff; depois da validação, o WA ID canônico ainda vence como
destinatário. Um formato real diferente exige fixture e revisão deste contrato,
nunca mudança silenciosa.

Fora dessa exceção, se WA ID do remetente faltar, user ID ocupa seu lugar no
transporte inbound. Isso também vale se a Meta continuar entregando somente user
ID depois da etapa 2: o webhook não conhece nem decide a etapa antes de
enfileirar. A limitação às etapas iniciais vale para o avanço de negócio e para o
fallback de destinatário, não para aceitar e proteger o envelope recebido. Não
se executam duas avaliações, incrementos ou locks independentes para a mesma
mensagem; username nunca participa da identidade técnica.

No anti-flood, a janela pertence ao sujeito lógico comprovado dentro do mesmo
`phone_id_unidade`. Antes da prova, user ID e WA ID permanecem separados. Depois
da associação oficial, os eventos ainda válidos das duas identidades são
somados, o WA ID torna-se a referência canônica e a troca de identificador não
reinicia a métrica.

Há duas formas de prova, sem aproximação:

1. vínculo permanente em `chatbot.user_id_cliente`, ligado ao cliente canônico
   com WA ID na mesma unidade;
2. durante o intervalo anterior ao commit do worker, `contact_request` oficial,
   autenticado pela assinatura da Meta, com user ID presente e exatamente um
   `wa_id_compartilhado` inequívoco.

A segunda prova cria somente uma ponte anti-flood pendente no Redis, escrita
atomicamente nas duas direções e com TTL de 15 segundos. Ela não promove o WA ID
no banco, não muda a identidade congelada do item, não autoriza sender e não
substitui a reconciliação transacional. Após o commit, o vínculo persistido passa
a ser a prova permanente e o cache confirmado substitui a ponte pendente.

Redis e memória somam os contadores das duas identidades sem duplicar eventos. O
fallback SQL usa `COUNT(DISTINCT id_hash_msg)` sobre WA ID e user ID associados.
O WAMID é deduplicado por unidade, de modo que uma reentrega ou o mesmo evento
visto pelos dois aliases conta uma única vez. Limite, janela e efeito de bloqueio
permanecem 15 WAMIDs distintos em 5 segundos.

Ausência de vínculo pode receber cache negativo de 5 segundos para evitar uma
consulta ao RDS por evento; a ponte oficial usa namespace separado e tem
prioridade imediata. Conflito, Redis indisponível sem prova persistida ou
qualquer impossibilidade de manter uma decisão compartilhada resulta em HTTP
503 para reentrega, sem bloqueio Meta e sem abrir um contador paralelo por
hipótese. Contato manual, username, nome, coincidência temporal ou semelhança de
valores nunca unem identidades.

O clique no botão gera uma nova mensagem inbound com WAMID e timestamp próprios.
Ela passa por deduplicação, flood, turno e fila como qualquer outra mensagem.

### 6.4 Turno e identidade do item

As consultas mantêm o algoritmo atual e recebem uma única identidade tipada por
item. A reconstrução usa os campos já persistidos; não cria coluna adicional:

```python
if (
    tipo_mensagem == "contacts"
    and conteudo_texto == "contact_request"
    and user_id_item_fila
):
    tipo_identidade_do_item = "user_id"
    identidade_do_item = user_id_item_fila
elif wa_id_item_fila:
    tipo_identidade_do_item = "wa_id"
    identidade_do_item = wa_id_item_fila
else:
    tipo_identidade_do_item = "user_id"
    identidade_do_item = user_id_item_fila

chave_turno = (
    tipo_identidade_do_item,
    identidade_do_item,
    id_phone_unidade,
)
```

No item de `contact_request`, a identidade do turno continua sendo a identidade
com a qual a mensagem foi enfileirada, normalmente o `user_id`. O WA ID
compartilhado não entra nessa chave; somente o WA ID canônico é usado como
destinatário do sender depois de lido do banco. Ele não recalcula a chave do
turno e não altera
`reagendar_se_houver_mensagem_anterior()`. A chave efetiva permanece congelada
durante todo o ciclo.

O tipo faz parte do namespace lógico: uma string igual observada como WA ID e
como user ID não representa a mesma chave. Na consulta SQL, o repositório escolhe
exatamente uma coluna (`wa_id` ou `user_id`) e mantém os mesmos filtros de
unidade, status, data e desempate; nunca executa busca dual por aliases.

### 6.5 Persistência na fila

Cada item recebe snapshots:

```python
{
    "wa_id": wa_id,
    "user_id": user_id,
    "username": username,
}
```

Ao menos `wa_id` ou `user_id` deve existir. Username ausente não causa erro.

No `contact_request` representado pelos fixtures, `fila_mensagens.wa_id` pode
transportar o candidato compartilhado sem criar `wa_id_compartilhado` físico. A
combinação persistida `tipo_mensagem='contacts'`,
`conteudo_texto='contact_request'` e `user_id` obriga a reconstrução da
`identidade_do_item` pelo user ID. A validação bancária é que promove esse mesmo
valor candidato a WA ID comprovado; até lá, nenhuma lógica de turno, cache,
bloqueio ou autocura pode tratá-lo como identidade canônica.

## 7. `flow_worker`: núcleo congelado e reconciliação delimitada

### 7.1 Sequência congelada

A sequência abaixo permanece exatamente no mesmo lugar:

1. `dequeue_message()` e commit atual;
2. `reagendar_se_houver_mensagem_anterior()` imediatamente após o dequeue;
3. `validar_banco_mensagem()` e commit atual;
4. confirmação/reparo de cache;
5. tratamento de bloqueio;
6. `chatbot.lock_conversa()` e commit atual;
7. vínculo fila -> conversa;
8. `valida_historico()` e commit atual;
9. `bot_resposta_atual()` antes do resolver/sender;
10. `flow_sender()`;
11. `atualizar_banco_com_contexto_final()` e commit atual;
12. marcação `sent` no ponto atual;
13. mesmos rollbacks, retries e autocura.

Também permanecem:

- requeue sem erro de 30 segundos para mensagem anterior;
- requeue sem erro de 5 segundos quando lock é recusado;
- requeue sem erro de 300 segundos para vínculo fila/conversa inconsistente;
- retry genérico de 2 minutos;
- limite atual de tentativas;
- espera atual de 1,5 segundo quando a fila está vazia;
- exatamente um processo de `flow_worker` em produção;
- toda a verdade lógica de `tests/unit/test_fluxo_turno_abc.py`.

Nenhum passo ganha retorno especial. O item de handoff passa pelo mesmo passo 2
com a identidade pela qual foi enfileirado e segue para a mesma validação, lock,
histórico, sender e persistência dos demais itens. Não se adiciona retorno de
ciclo, `continue` ou reagendamento específico desta feature.

### 7.2 Transporte de contexto

Os três valores percorrem a cadeia existente, sem criar uma etapa nova no
worker:

```text
fila -> validar_banco_mensagem() -> contexto_banco
     -> valida_historico() -> contexto_historico
     -> flow_sender() -> resolver -> sender -> contexto_envio
     -> flow_sender() enriquece e devolve
```

O item da fila é um snapshot de entrada. Para o sender, porém, a fonte
autoritativa é o banco: `validar_banco_mensagem()` resolve o cliente, a conversa
e `user_id_cliente`; `valida_historico()` copia os valores resolvidos para o
`contexto_historico`.

Ao final da resolução — inclusive depois de criar vínculo ou reconciliar
cliente — `validar_banco_mensagem()` faz uma projeção final obrigatória pelo
`id_cliente`, `id_unidade` e `id_conversa` definitivos. Essa leitura retorna as
três chaves, ainda que o valor de alguma delas seja `None`:

- `wa_id`: `cliente.wa_id` do cliente canônico final;
- `user_id`: `user_id_cliente.user_id` do mesmo cliente na unidade atual;
- `username`: `conversa.username`, snapshot da conversa atual.

`cliente.username` continua sendo o valor global mais recente para cadastro e
Admin, mas não substitui silenciosamente o snapshot da conversa no contexto nem
no histórico do bot.

```python
identidades_banco = buscar_identidades_para_contexto(
    id_cliente=id_cliente_final,
    id_unidade=id_unidade,
    id_conversa=id_conversa_final,
    cursor=cursor,
)

contexto_banco.update(
    {
        "wa_id": identidades_banco["wa_id"],
        "user_id": identidades_banco["user_id"],
        "username": identidades_banco["username"],
    }
)
```

O `estado_ciclo` passa a transportar, como campos aditivos:

- `tipo_identidade_do_item` e `identidade_do_item`, reconstruídos imediatamente
  após o dequeue e imutáveis até a finalização daquele item;
- `wa_id_compartilhado`, somente quando o marcador persistido provar que o
  snapshot de WA veio do cartão oficial;
- `wa_id_canonico`, preenchido apenas depois da projeção bancária final;
- `id_phone_unidade`;
- `referencia_cache_cliente`, a única chave tipada admissível para resolver o
  cliente daquele item.

Turno, logs, finalização da fila, retry e autocura usam
`identidade_do_item`. A seleção do destinatário usa somente `wa_id`, `user_id` e
username provenientes do `contexto_banco`. Nenhum desses campos é recalculado a
partir do outro no meio do ciclo.

O cache de cliente não pode reutilizar a chave global atual de WA ID para um
user ID. O namespace lógico preserva a chave WA existente e acrescenta uma chave
escopada para user ID:

```text
WA ID:   cliente_cache:{wa_id}
user ID: cliente_cache:user:{id_phone_unidade}:{user_id}
```

A chave WA continua global. A chave de user ID sempre inclui a unidade e o tipo;
uma mesma string vista como WA ID e como user ID não colide. Os fallbacks em
memória seguem a mesma separação. TTL, precedência Redis -> banco, tolerância a
falha e quantidade de tentativas permanecem os atuais.

Um helper puro monta `referencia_cache_cliente` a partir de
`tipo_identidade_do_item`, `identidade_do_item` e `id_phone_unidade` ainda em
`montar_mensagem_fila()`. `atualizar_estado_com_mensagem()` a copia antes de
`validar_banco_mensagem()`, e a validação usa exatamente essa mesma referência.
Assim, se a validação falhar antes de devolver `contexto_banco`, a autocura ainda
conhece a chave correta. O reparo de FK stale remove somente essa referência; ele
não recalcula uma chave a partir do WA ID compartilhado ou do WA ID canônico e
não pode apagar a chave de outra unidade. No handoff, a confirmação de cache que
já ocorre depois do commit atual passa a apontar a chave de user ID usada para o
`id_cliente` canônico. Não há escrita antes do commit, ponto adicional de
confirmação, commit, retry, requeue ou ramo de autocura novo.

Um hit de cache pode ajudar a localizar o `id_cliente`, mas não substitui essa
projeção final. Se o banco não devolver o contrato completo, a validação falha;
não existe fallback silencioso para os campos brutos da fila ou do payload.

Contrato aditivo de entrada de `flow_sender()` e dos resolvers:

```python
contexto_historico.update(
    {
        "wa_id": contexto_banco["wa_id"],
        "user_id": contexto_banco["user_id"],
        "username": contexto_banco["username"],
    }
)
```

Além dos três snapshots canônicos, `valida_historico()` expõe no topo do
contexto um campo lógico separado para o validador da etapa 2:

```python
eh_contact_request = (
    mensagem_cliente_atual["tipo_mensagem"] == "contacts"
    and mensagem_cliente_atual["conteudo_texto"] == "contact_request"
)

contexto_historico["wa_id_compartilhado"] = (
    mensagem_cliente_atual.get("wa_id")
    if eh_contact_request
    else None
)
```

Esse valor vem do snapshot normalizado do item e serve somente para o validador
reconhecer a prova oficial. `contexto_historico["wa_id"]` continua sendo o WA ID
canônico relido do banco. É proibido usar o canônico como prova de que o payload
era `contact_request`, assim como é proibido usar `wa_id_compartilhado` como
destinatário. O `contexto_envio` continua refletindo apenas `wa_id`, `user_id` e
username canônicos/snapshots; não transporta o candidato como quarto campo.

`flow_sender(contexto_historico)` e os resolvers não leem novamente o banco e
não usam diretamente os identificadores brutos do payload. Uma única função
central resolve o destinatário:

```python
def resolver_destinatario_sender(
    contexto_historico,
    *,
    permitir_user_id=False,
):
    wa_id = contexto_historico.get("wa_id")
    user_id = contexto_historico.get("user_id")
    id_etapa_atual = contexto_historico.get("id_etapa_atual")

    if wa_id:
        return wa_id

    if permitir_user_id and id_etapa_atual in (None, 1, 2) and user_id:
        return user_id

    raise ValueError("Sender sem WA ID fora das etapas iniciais")
```

O `contexto_envio` devolvido em envio novo ou no caminho idempotente mantém o
contrato técnico já existente e apenas reflete os snapshots que chegaram no
`contexto_historico`:

```python
contexto_envio.update(
    {
        "wa_id": contexto_historico.get("wa_id"),
        "user_id": contexto_historico.get("user_id"),
        "username": contexto_historico.get("username"),
    }
)
```

Essa anexação pertence à fronteira de `flow_sender()`, não a um sender de etapa.
No ramo em que `resposta_bot_para_mensagem_atual` já existe, ela é executada
antes do retorno antecipado. Nos demais ramos, é executada sobre o resultado do
resolver antes de `flow_sender()` devolvê-lo. Assim nenhum caminho retorna um
formato parcial.

Esses campos não comandam commit ou transição. Eles acompanham o resultado para
a persistência existente e garantem o mesmo formato nos envios novos, nos
tratamentos e no retorno idempotente de resposta já registrada.

Regras finais:

- ausência no evento não apaga valor conhecido;
- WA ID lido do banco sempre vence user ID para o sender;
- user ID só pode ser destinatário quando o resolver da etapa habilita
  explicitamente `permitir_user_id=True`, a conversa está em `None/1/2` e não há
  WA ID;
- a resposta válida `contato_oficial_compartilhado`, embora parta da etapa 2,
  chama o helper com o padrão `False` e exige WA ID;
- username só é transportado e persistido; nunca entra em `to`;
- retry reconstrói os valores do banco;
- sender e resolver não executam SQL;
- não se cria commit, lock, retorno de ciclo, exceção de retry ou política de
  retry;
- `dequeue_message()` apenas amplia/renomeia os dados retornados;
- CTE, `WHERE`, `ORDER BY`, `FOR UPDATE SKIP LOCKED`, posse, retry e timestamps
  permanecem semanticamente idênticos.

### 7.3 Resolução e reconciliação dentro da validação existente

`validar_banco_mensagem()` passa a resolver na seguinte ordem:

1. localizar a unidade pelo mesmo `id_phone_unidade` atual;
2. se houver user ID, consultar `(user_id, id_unidade)`;
3. em evento de handoff, usar primeiro esse vínculo para reencontrar a conversa
   provisória; somente depois consultar o cliente canônico pelo WA ID;
4. em payload normal com WA ID, resolver/criar o cliente global pelo WA ID e
   registrar imediatamente o user ID que chegou junto;
5. em primeiro evento somente-user-ID sem vínculo, criar cliente provisório,
   vínculo e conversa na mesma transação;
6. em retorno somente-user-ID já mapeado, reutilizar o cliente e a conversa
   canônicos; se o cliente já possuir WA ID, acumulá-lo e não abrir a etapa 2;
7. devolver ao restante do ciclo o `id_cliente` e `id_conversa` finais.

As restrições de unicidade de `(user_id, id_unidade)` e
`(id_cliente, id_unidade)` continuam sendo a proteção de integridade. O plano não
cria lock nem ramo de retry para disputas; qualquer violação segue o rollback e o
tratamento atuais. O nome do cliente passa a ser atualizado por `id_cliente`,
pois a versão atual por telefone não atende clientes provisórios com WA ID nulo.

Quando WA ID e user ID provarem que o cliente provisório corresponde a cliente
antigo, aplica-se exatamente a seção 4.5. O commit já existente depois de
`validar_banco_mensagem()` confirma os efeitos; o rollback e o retry atuais
continuam responsáveis por falhas, sem ramificação específica desta feature.

O banco é a fonte da verdade do vínculo e dos identificadores passados aos
contextos. Esta reconciliação não consulta nem modifica `funil_envios`, não cria
exceção para denylist ou bloqueio, não remove fila antecipadamente e não encerra
o ciclo antes do lock, histórico, resolver ou sender. Esses componentes seguem
as regras que já possuem.

### 7.4 Persistência dos snapshots

- fila: snapshot normalizado/resolvido pelo webhook antes de existir conversa;
- histórico do cliente: snapshot do item da fila;
- histórico do bot: snapshots refletidos no `contexto_envio`, originados do
  `contexto_historico` que foi reconstruído pelo banco;
- conversa: preenche `user_id`, `wa_id` e o primeiro username não vazio; username
  da conversa não é sobrescrito;
- cliente: atualiza `wa_id` quando ocorre promoção válida e atualiza username
  sempre que a Meta trouxer um valor novo não vazio;
- `user_id_cliente`: relação canônica atual do cliente naquela unidade;
- resolver: recebe os valores pelo `contexto_historico`, escolhe o destinatário
  pelo helper e passa somente o escalar ao sender;
- sender: não persiste nem consulta identificadores; devolve seu contexto técnico
  normal, que `flow_sender()` enriquece com os snapshots no `contexto_envio`;
- na prova oficial, fila e histórico da conversa recebem cada identificador
  conhecido somente onde a respectiva coluna estiver `NULL`;
- valores não nulos de fila/histórico/conversa nunca são sobrescritos;
- flood continua sendo snapshot do evento e não sofre backfill, pois não possui
  `id_conversa`;
- conflito realmente contraditório entre dois clientes com WA IDs não nulos e
  diferentes nunca é resolvido por username ou aproximação.

### 7.5 Fronteiras arquiteturais e donos da persistência

A implementação da nova etapa e a renumeração preservam as responsabilidades
atuais:

- `core/integrations/whatsapp/messages/etapaN_messages.py` contém somente
  constantes, textos e builders puros. Não chama Meta, não valida resposta, não
  conhece evento/destino e não acessa banco;
- `core/integrations/whatsapp/pywa_functions/pywa_senders/etapaN.py` chama o
  builder da etapa, realiza somente o I/O da Meta e monta o `contexto_envio` no
  formato já existente. Recebe o destinatário escalar e os parâmetros técnicos;
  não recebe responsabilidade de validar conteúdo, escolher evento/transição ou
  executar SQL/commit;
- `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapaN.py`
  classifica o contexto normalizado e devolve resultado/valor. Não envia, não
  consulta banco e não escolhe destino;
- `resolver_etapaN.py` mantém a prioridade dos validadores, produz no máximo um
  evento, chama `resolver_destino_transicao()`, resolve o destinatário por meio
  do helper puro, chama o sender adequado e usa
  `anexar_transicao_ao_contexto_envio()`. Tratamentos não carregam evento e o
  resolver não faz SQL/commit;
- `flow_sender.py` conserva a barreira idempotente e apenas roteia pela etapa
  persistida: `None/1 -> resolver 1`, `2 -> resolver 2`, até `22 -> resolver 22`.
  A etapa 23 é terminal e não possui resolver. `flow_sender()` acrescenta os
  três snapshots antes de todo retorno, inclusive o idempotente. Ele também
  preserva a reconstrução idempotente já existente da confirmação do destino:
  ao recuperar uma resposta do bot, o evento único identifica a transição e o
  `status_dependente` booleano, já persistido na mesma transação da resposta,
  repõe o `status_dependente_final` absoluto sem reaplicar uma inversão. Valor
  ausente ou não booleano é inconsistência e falha de forma fechada; nunca é
  convertido silenciosamente para titular. Fora esse contrato existente, ele
  não valida conteúdo, executa SQL nem chama a Meta diretamente;
- `transicoes/eventos.py` e `chatbot.etapa_transicao` definem nomes e arestas,
  sem conter efeitos de dados;
- `persistencia_resposta.py` e `efeitos_transicao.py` continuam sendo os donos
  dos efeitos finais de negócio na transação já existente.

O resolver, por conhecer a etapa e o evento que está sendo tratado, é o chamador
de `resolver_destinatario_sender()`. Ele passa somente o escalar retornado ao
sender PyWa. Assim, nenhum sender recebe o dicionário completo para decidir por
conta própria se user ID é permitido.

A divisão transacional fica fixada desta forma:

1. `validar_banco_mensagem()` resolve, promove e, quando comprovado, reconcilia a
   identidade necessária antes do sender, usando o cursor, a transação e o
   commit que já existem depois da validação. Não escolhe evento, não movimenta
   etapa, não registra resposta do bot e não persiste o nome capturado;
2. resolver e sender produzem `contexto_envio` sem SQL;
3. `atualizar_banco_com_contexto_final()` mantém internamente a ordem atual:
   registrar/recuperar histórico do bot -> `persistir_movimento_conversa()` ->
   turnos sem avanço -> `atualizar_banco_conforme_transicao_de_etapa()` ->
   `resolver_intencao_encerramento()`;
4. o commit final permanece no ponto atual do `flow_worker`.

A reconciliação de identidade não é movida para `efeitos_transicao.py`, porque o
sender da etapa 3 precisa do WA ID canônico antes do envio. Ela também não é
duplicada: `atualizar_banco_conforme_transicao_de_etapa()` reconhece a aresta e
aplica somente os efeitos finais próprios da transição. Uma falha continua
seguindo o rollback/retry da transação correspondente, sem política nova.

## 8. Etapa especial obrigatória

### 8.1 Gatilho

Depois que o cliente responde o nome na etapa 1:

- se o contexto acumulado já possui WA ID, inclusive resolvido por
  `user_id_cliente`, pula a etapa especial e segue para
  “Para quem é o atendimento?”;
- se possui apenas user ID, entra obrigatoriamente na etapa especial;
- username não interfere na decisão.

O gate olha o contexto acumulado do primeiro evento, da resposta do nome e do
banco. Ele não olha apenas o payload atual.

### 8.2 Mensagem

```text
Olha, para prosseguir precisamos que compartilhe o seu número de telefone. Aperte no botão abaixo.
```

Esse texto pertence ao novo
`core/integrations/whatsapp/messages/etapa2_messages.py`, em uma constante e em
um builder puro, seguindo o padrão das demais etapas. O resolver escolhe o
destinatário e passa somente o escalar ao sender:

```python
destinatario = resolver_destinatario_sender(
    contexto_historico,
    permitir_user_id=True,
)

contexto_envio = enviar_etapa2_compartilhamento_contato(
    destinatario,
    id_phone_unidade,
    id_conversa,
)
```

O sender importa o builder e realiza o I/O:

```python
mensagem_bot = montar_mensagem_etapa2()

wa.request_contact_info(
    to=destinatario,
    sender=id_phone_unidade,
    text=mensagem_bot,
    tracker=f"contato:{id_conversa}:etapa:2",
)
```

Nesta etapa, `destinatario` será o `user_id` lido do banco porque o WA ID ainda
não existe. O sender não recebe o valor diretamente do payload.

Não haverá:

- botão “Prefiro não informar”;
- entrada de telefone por texto;
- confirmação manual posterior;
- coleta de username;
- pausa ou rota alternativa.

O mesmo arquivo de mensagens expõe uma retomada neutra própria para os
tratamentos da etapa 2. Os builders de mídia, reforço escolar, financeiro e
contexto usam essa retomada e o mesmo componente oficial; não concatenam
automaticamente o prefixo de tratamento com a mensagem inaugural iniciada por
“Olha, para prosseguir...”. O plano fixa o contrato semântico, sem obrigar uma
segunda frase literal antes da implementação final.

### 8.3 Validação

Enquanto aguarda:

- primeiro, reconhecer
  `contacts + contact_request + wa_id_compartilhado` válido;
- depois, tratar qualquer outro `contacts` como contexto inválido;
- nas demais entradas, mídia: tratamento clássico de mídia + repetição;
- depois, dúvida sobre reforço escolar/banca/cursinho: tratamento universal +
  repetição;
- depois, pergunta financeira: tratamento financeiro + repetição;
- por fim, texto residual, mesmo que contenha um número: contexto específico e
  repetição do pedido oficial;
- contato manual/vCard já caiu no segundo item e nunca é reinterpretado como
  texto;
- somente `contacts` com origem `contact_request` e WA ID compartilhado extraído
  avança.

Todos os tratamentos reapresentam o pedido oficial com formulação neutra,
preservando o componente de compartilhamento e sem repetir uma abertura que
pressuponha sucesso na resposta anterior.

Essa ordem é obrigatória. O validador universal de mídia atual classifica
`contacts` como mídia/não texto; se ele rodar antes do reconhecimento oficial,
o clique correto nunca alcançará a transição. Da mesma forma, texto residual só
pode cair em contexto depois de reforço e financeiro, para que uma pergunta
mista como “qual o valor da banca?” receba o tratamento correto.

Depois do compartilhamento válido, o WA ID é persistido e volta ao sender pelo
`contexto_historico` reconstruído a partir do banco. A resposta seguinte usa esse
WA ID para enviar “Para quem é o atendimento?”. A promoção/reconciliação da
identidade já terminou em `validar_banco_mensagem()` antes desse envio. O
movimento 2 -> 3 e os efeitos finais da aresta continuam exclusivamente em
`atualizar_banco_com_contexto_final()` ->
`atualizar_banco_conforme_transicao_de_etapa()`.

### 8.4 Contrato exato das novas arestas

As três arestas afetadas ficam fechadas desta forma:

1. `1 -> 2`, evento `nome_cliente_valido_sem_wa_id`: o resolver da etapa 1 usa
   o validador de nome atual, comprova pelo contexto bancário que ainda não há WA
   ID, resolve o destino pelo mapa, envia o pedido oficial da nova etapa 2 ao
   user ID e anexa `primeiro_nome_cliente`. O efeito final persiste o nome por
   `id_cliente`, nunca por telefone;
2. `1 -> 3`, evento `nome_cliente_valido_com_wa_id`: o mesmo validador de nome
   resolve a aresta pelo mapa e envia ao WA ID o conteúdo da antiga etapa 2,
   renumerada para 3. O mesmo helper de efeito da saída anterior persiste o nome
   por `id_cliente`; reexecuções no retry são idempotentes e mantêm o mesmo
   resultado;
3. `2 -> 3`, evento `contato_oficial_compartilhado`: o resolver da etapa 2
   reconhece primeiro `contacts + contact_request + wa_id_compartilhado`, exige
   `wa_id_canonico` no contexto bancário, resolve a aresta e envia a etapa 3 a
   esse WA ID. `efeitos_transicao.py` reconhece explicitamente origem 2, evento e
   destino 3, mas não repete a promoção/reconciliação já concluída antes do
   sender.

O helper compartilhado de persistência do nome recebe o evento e o destino
efetivos do `contexto_envio`. Ele não mantém hardcode do legado
`EVENTO_NOME_CLIENTE_VALIDO`, de destino 2 nem textos de log “1 -> 2”; os logs e
as validações de destino refletem corretamente 1 -> 2 ou 1 -> 3. A idempotência
é de resultado: o efeito pode ser invocado novamente pelo caminho atual de retry
sem produzir nome divergente nem depender de telefone.

Texto, mídia, dúvida sobre reforço escolar, financeiro e contato manual tratados
na etapa 2 permanecem na etapa 2, repetem o pedido quando aplicável e não
carregam evento de transição. O contato oficial válido é reconhecido antes dos
tratamentos; nas demais entradas a ordem é mídia -> reforço -> financeiro ->
contexto. Nenhuma dessas decisões ocorre no sender nem dentro da função de
efeito.

## 9. Catálogo e mapa de transição

O catálogo final terá 23 etapas:

| ID | Etapa | Funil | Terminal |
|---:|---|:---:|:---:|
| 1 | Saudação e nome | não | não |
| 2 | Compartilhamento oficial do contato | não | não |
| 3 | Destino do atendimento | não | não |
| 4 | Confirmação do destino do atendimento | não | não |
| 5 | Profissão | não | não |
| 6 | Nome do dependente | não | não |
| 7 | Idade | não | não |
| 8 | Oferta | não | não |
| 9 | Oferta adiada | não | não |
| 10 | Retorno ao atendimento | não | não |
| 11 | Email | não | não |
| 12 | Introdução à triagem | não | não |
| 13–18 | Perguntas 1–6 da triagem | não | não |
| 19 | Agendamento | sim | não |
| 20 | Satisfação — nota | sim | não |
| 21 | Satisfação — opção de comentário | sim | não |
| 22 | Satisfação — comentário | sim | não |
| 23 | Finalização | sim | sim, bloqueio de 30 dias |

A baseline V1.0.5 já possui 22 etapas. Na migração futura, as etapas atuais
2..22 serão remapeadas para 3..23 sem apagar dados. A etapa 1 permanece no
mesmo ID e a única etapa realmente adicionada sobre essa baseline é a etapa 2
de compartilhamento oficial.

Conversas já existentes conservam seu progresso: uma conversa atual na etapa 2
vai para a futura etapa 3, a atual 3 vai para a futura 4 e assim por diante. Elas
não são devolvidas à etapa especial. Isso é seguro para a baseline, na qual o
WA ID ainda é obrigatório; somente atendimentos privados processados pelo código
novo entram na etapa 2 quando terminarem a captura do nome sem WA ID canônico.

Mapa final:

```python
TRANSICOES = (
    (1, "nome_cliente_valido_com_wa_id", 3),
    (1, "nome_cliente_valido_sem_wa_id", 2),
    (2, "contato_oficial_compartilhado", 3),
    (3, "destino_atendimento_definido", 4),
    (4, "destino_atendimento_confirmado", 5),
    (5, "profissao_dependente_valida", 6),
    (5, "profissao_titular_valida", 7),
    (6, "nome_dependente_valido", 7),
    (7, "idade_valida", 8),
    (8, "oferta_aceita", 11),
    (8, "oferta_adiada", 9),
    (9, "cliente_retornou", 10),
    (10, "retorno_confirmado", 11),
    (10, "retorno_adiado", 9),
    (11, "email_valido", 12),
    (12, "triagem_iniciada", 13),
    (13, "triagem_pergunta_1_respondida", 14),
    (14, "triagem_pergunta_2_respondida", 15),
    (15, "triagem_pergunta_3_respondida", 16),
    (16, "triagem_pergunta_4_respondida", 17),
    (17, "triagem_pergunta_5_respondida", 18),
    (18, "triagem_pergunta_6_respondida", 19),
    (19, "agendamento_confirmado", 20),
    (20, "satisfacao_avaliada", 21),
    (21, "comentario_satisfacao_aceito", 22),
    (21, "comentario_satisfacao_recusado", 23),
    (22, "comentario_satisfacao_recebido", 23),
)
```

Haverá resolvers para 1..22. A etapa 23 é terminal e não possui resolver.

### 9.1 Destino do atendimento preservado

A etapa atual 2 passa à futura etapa 3 conservando sua interface e seu
validador contextual:

- os botões visíveis continuam `Para mim` e `Para um dependente`;
- o texto legado `Para outra pessoa` e as frases inequívocas já catalogadas para
  titular, dependente, parentescos e destinos genéricos continuam aceitos;
- caixa, acentos, pontuação, espaços e vírgulas ausentes seguem a normalização
  atual;
- mídia, dúvida sobre reforço escolar, pergunta financeira ou qualquer conteúdo
  fora dos conjuntos reconhecidos permanecem como tratamento na etapa 3;
- a escolha continua sendo persistida pelos efeitos transacionais existentes e
  encaminha ambas as opções à confirmação, sem salto direto para profissão ou
  nome do dependente.

### 9.2 Confirmação do destino preservada

A confirmação implantada na V1.0.4 e presente na baseline V1.0.5 passa da etapa
atual 3 para a futura etapa 4 sem ampliar sua gramática. Na baseline corrigida,
ela produz o evento único `destino_atendimento_confirmado` e sempre segue de 3
para a profissão atual 4; depois da renumeração, a mesma regra segue da
confirmação futura 4 para a profissão futura 5:

- aceita somente o clique nos botões `Sim`/`Não` ou o texto digitado
  `Sim`/`Não`, após a normalização já existente;
- `Sim` mantém o `status_dependente` definido na etapa anterior;
- `Não` persiste o polo oposto e segue adiante, sem voltar à etapa 3;
- qualquer outro texto que não tenha sido classificado antes como reforço
  escolar ou financeiro recebe tratamento de contexto e repete a etapa 4;
- mídia, dúvida sobre reforço escolar e pergunta financeira permanecem como
  tratamentos sem evento e sem avanço;
- o contexto carrega `status_dependente_final` absoluto, nunca uma ordem de
  inversão. O efeito transacional faz `SET` idempotente, cria o placeholder do
  dependente quando o valor final é verdadeiro e remove o placeholder quando o
  valor final é falso;
- titular e dependente produzem o mesmo evento
  `destino_atendimento_confirmado` e seguem obrigatoriamente para a profissão na
  etapa 5. Somente a resposta da profissão bifurca para o nome do dependente na
  etapa 6 ou para a idade do titular na etapa 7;
- o caminho de resposta do bot já existente reconstrói esse mesmo valor absoluto
  a partir do `status_dependente` booleano persistido na conversa. Ausência ou
  tipo inválido interrompe o ciclo para retry, sem assumir `False` e sem inverter
  novamente a resposta original.

Essa convergência não altera a identidade nem o destinatário do atendimento:
as regras de WA ID canônico, fallback de user ID antes do compartilhamento e
exigência de WA ID da futura etapa 3 em diante permanecem exatamente as mesmas.

### 9.3 Triagem por faixa etária preservada

O catálogo canônico compartilhado por WhatsApp e Funil continua em
`core/triagem/perguntas.py`, com as chaves renumeradas de 12..17 para 13..18:

- `valida_historico.ETAPAS_TRIAGEM` passa do intervalo atual 11..17 para
  12..18; a introdução futura 12 também relê nome, idade e destino para que o
  sender monte corretamente a primeira pergunta;
- titular usa as seis perguntas adultas com `você`;
- dependente menor de 18 anos usa as seis perguntas infantis com o nome;
- dependente adulto usa as seis perguntas adultas com o nome;
- a elegibilidade mínima de 4 anos em unidade com BPA ou 5 anos sem BPA
  continua pertencendo à validação de idade anterior à triagem;
- status de dependente, nome e idade são relidos do banco em cada ciclo; dados
  ausentes ou inconsistentes falham de forma fechada;
- as respostas continuam restritas a `Nunca`, `Às vezes` e `Frequentemente`;
- a unicidade e a idempotência de `respostas_desafios (id_conversa, id_etapa)`
  permanecem iguais.

O contexto de agendamento que hoje é carregado nos ciclos 17/18 passa aos ciclos
18/19: a resposta da sexta pergunta precisa do link para enviar a etapa 19 e os
tratamentos da própria etapa 19 precisam repetir a mesma mensagem.

Confirmação, tratamentos e triagem por idade não exigem coluna nova. Suas
mudanças futuras são de numeração, catálogo, validadores, mensagens e projeções
já previstas; o desenho físico de identidade da seção 5 permanece intacto.

## 10. Senders

Todos os resolvers recebem os identificadores já resolvidos pelo banco no
`contexto_historico`. Antes de chamar o sender de etapa, o resolver faz a seleção
central e consciente da etapa:

```python
destinatario = resolver_destinatario_sender(
    contexto_historico,
    permitir_user_id=envio_inicial_antes_do_wa_id,
)
```

Isso evita espalhar regras divergentes pelos arquivos de etapa e impede que um
erro posterior seja mascarado por fallback para user ID. O valor booleano só é
`True` nos envios da etapa 1 e no pedido/repetição de compartilhamento da etapa
2. A resposta `contato_oficial_compartilhado` usa o padrão `False`: se o WA ID
não estiver no contexto bancário, nenhuma mensagem da etapa 3 é enviada. O
helper devolve apenas o escalar usado no mesmo método PyWa atual. Username não
participa.

Regras:

- antes do contato oficial, sem WA ID: user ID lido do banco;
- no evento válido de compartilhamento: WA ID primeiro persistido e depois lido
  do banco no contexto;
- depois da promoção: WA ID obrigatório em todos os senders;
- se evento posterior omitir WA ID, o banco preserva o valor canônico;
- username nunca é `to`;
- nenhuma função acrescenta ou remove o nono dígito do destinatário.

O sender de etapa devolve seu contexto técnico normal. A fronteira de
`flow_sender()` acrescenta `wa_id`, `user_id` e username ao `contexto_envio`
antes de qualquer retorno, inclusive no caminho idempotente, sem consultar banco
e sem alterar a persistência. O helper é exclusivo da resolução de destinatário
outbound e é chamado pelo resolver; bloqueio, desbloqueio e flood não o
reutilizam. Esses componentes recebem somente a identidade tipada do evento
inbound, que pode continuar sendo user ID quando a Meta omitir WA ID mesmo após
a etapa 2, sem mudar seus algoritmos nem autorizar fallback no sender.

### 10.1 Tratamentos atuais preservados

A implementação futura não volta ao conjunto de validadores anterior à V1.0.5.
Toda etapa que possui tratamento financeiro continua possuindo também o
tratamento universal de dúvida sobre reforço escolar, inclusive a nova etapa 2.
O tipo técnico permanece `duvida_reforco_escolar`.

A gramática implantada é congelada durante a renumeração. Ela reconhece reforço
escolar/pedagógico, banca escolar, supletivo, EJA, Encceja, cursinho,
pré-vestibular/preparatório, aula ou professor particular, apoio,
acompanhamento, recuperação e nivelamento escolar, além de tarefa/dever de casa.
Matérias como matemática ou português só disparam quando ligadas a intenção de
aula, ensino ou ajuda; a palavra isolada não basta. Banca examinadora,
avaliadora, acadêmica, de concurso ou de TCC permanece excluída, assim como usos
não escolares de “reforço”. Formas curtas de `banca`/`reforço` continuam sujeitas
aos contextos controlados do validador atual. Ampliar ou reduzir esse vocabulário
é tarefa separada, não efeito da migração de identidade.

Na etapa especial, o validador do contato oficial válido roda primeiro, pois
`contacts + contact_request + wa_id_compartilhado` é a prova que autoriza a
transição. Contato manual ou inválido não satisfaz essa prova. Para as demais
entradas, e nas outras etapas, a prioridade permanece:

```text
mídia/tipo não suportado -> reforço escolar -> financeiro -> contexto/regra da etapa
```

Assim, uma frase mista como “qual o valor da banca?” recebe o tratamento de
reforço escolar, não o financeiro. Tratamentos ficam na etapa atual, retornam
`tratamento=True`, não carregam evento e não alteram transação, retry nem
contadores além do comportamento transversal já existente. As mensagens
financeiras preservam a expressão atual “valores de investimento”.

A profissão atual da etapa 4 passa à futura etapa 5 e continua obrigatória para
titular e dependente. A confirmação sempre apresenta essa pergunta; depois de
persisti-la, `status_dependente` escolhe a futura etapa 6, com o nome do
dependente, ou a futura etapa 7, com a idade do titular. Seus adaptadores
contextuais de reforço e financeiro também são renumerados e continuam
protegendo declarações inequívocas de vínculo profissional com banca, cursinho,
supletivo ou reforço. O classificador universal não é enfraquecido para as
demais etapas.

Essa bifurcação também é fail-closed: `status_dependente` precisa ser um
booleano persistido tanto no resolver quanto no efeito da profissão. Ausência
ou tipo inválido interrompe o ciclo para retry, sem transformar `None` em
titular por coerção.

Cada mensagem de tratamento deve reapresentar a pergunta de forma neutra. Não é
permitido concatenar cegamente a mensagem inaugural quando ela começa com
expressões que pressupõem avanço ou resposta válida, como `Entendi`, `Certo`,
`Perfeito`, `Maravilha` ou `Prazer`. Mídia, reforço, financeiro e contexto
preservam os componentes, botões, rodapés e variantes titular/dependente da
etapa, mas usam uma retomada semanticamente coerente.

## 11. Funil

WA ID continua obrigatório para o comercial e para materializar o lead. A
implementação deve adaptar o fluxo atual — `buscar_dados_lead_funil()`,
`montar_observacoes_lead()` e `montar_payload_oportunidade()` — sem criar uma
arquitetura paralela.

Regras:

- WA ID + username: enviar os dois nas observações;
- somente WA ID: enviar WA ID;
- somente username: nunca materializar;
- user ID: nunca mostrar ao comercial;
- username aparece com exatamente um `@`;
- elegibilidade começa na etapa 19 e abrange 19..23;
- a etapa especial impede que uma conversa sem WA ID alcance a etapa 19.

O Funil usa `conversa.username` para representar o snapshot daquele atendimento
e o coloca, quando existir, junto às informações de contato antes da seção de
triagem. `cliente.username` continua disponível como valor canônico atual, mas
não reescreve retroativamente o lead antigo.

No contrato futuro do repositório, `buscar_dados_lead_funil()` seleciona
`cliente.wa_id` como telefone obrigatório e `conversa.username` como username
do atendimento, devolve ambos no dicionário do snapshot e filtra
`respostas_desafios.id_etapa BETWEEN 13 AND 18`. Não usa
`cliente.username` como atalho e não projeta `user_id` para a integração.

O detalhamento implantado na V1.0.5 também é obrigatório:

- `buscar_dados_lead_funil()` lê as respostas das futuras etapas 13..18 em
  ordem crescente;
- `core/triagem/perguntas.py` é a única fonte dos textos exibidos no WhatsApp e
  reconstruídos no Funil;
- `montar_observacoes_lead()` apresenta “Perguntas e respostas da triagem” com
  seis blocos ordenados, cada um contendo número, pergunta completa e resposta;
- não volta a existir resumo quantitativo como “Nunca: 2 vezes”;
- titular usa a variante adulta com `você`; dependente usa o nome e a variante
  infantil ou adulta conforme a idade;
- ausência, duplicidade, desordem ou resposta fora de `Nunca`, `Às vezes` e
  `Frequentemente` impede a montagem do lead;
- ausência de username não impede o lead; ausência de WA ID continua impedindo.

## 12. Bloqueio, desbloqueio e Django Admin

`cliente_bloqueado_meta` exige WA ID ou user ID. Para bloquear/desbloquear:

1. carregar os snapshots do registro;
2. usar WA ID se existir;
3. senão usar user ID;
4. combinar com `phone_id_unidade`;
5. username serve somente à exibição.

O guard não carrega nem decide etapa. Ele usa user ID somente quando o envelope
do próprio evento não possui WA ID. Essa condição ocorre no período inicial e
pode continuar ocorrendo depois da etapa 2 se a Meta mantiver o WA ID privado.
Nesse caso, o uso é apenas para proteger e transportar o evento inbound; no
worker, `user_id_cliente` resolve o cliente e o WA ID canônico. Isso não autoriza
user ID como destinatário de etapa posterior. Quando WA ID do remetente estiver
presente no envelope, ele é sempre prioritário.

Essa adaptação é necessária porque todo evento inbound sem WA ID também passa
pelas proteções do webhook. Denylist e bloqueio Meta continuam preferindo WA ID e
usando user ID somente como fallback do próprio envelope. O anti-flood, porém,
possui um resolvedor próprio de aliases oficialmente comprovados: ele agrega as
janelas de `user_id` e `wa_id`, deduplica por WAMID e adota o WA ID como referência
canônica após a prova. O limite de 15 eventos em 5 segundos e a ordem Meta ->
banco do desbloqueio permanecem; os TTLs auxiliares e o caminho HTTP 503 seguem a
seção 6.3. Nada disso faz parte do fluxo transacional do `flow_worker`.

Ao excluir um bloqueado no Admin, o sistema continua chamando primeiro o
desbloqueio na Meta e só exclui localmente após sucesso, conforme a regra atual.

Esta tarefa não cria consolidação especial de bloqueios durante a reconciliação,
nem adiciona row lock ou desvio no worker para esse fim. O guard, a ordem
Meta -> banco do desbloqueio e o comportamento atual do Admin permanecem.

Admin:

- Unidade exige, exibe e edita `id_portfolio`;
- Cliente exibe WA ID anulável e username opcional;
- Fila, histórico, conversa, bloqueio e flood exibem os três snapshots;
- `user_id_cliente` é consultável, pesquisável por cliente/unidade/user ID e
  somente leitura; vínculos são alterados apenas pelo fluxo transacional;
- buscas aceitam WA ID, user ID e username;
- `__str__` não presume WA ID e usa fallback legível para user ID/chave;
- username não altera ações, filtros de identidade ou permissões.

## 13. PyWa 4.x

A atualização da biblioteca será feita em mudança isolada e com versão exata
confirmada no dia da implementação. Não se usará uma versão futura presumida.

Antes do deploy serão validados:

- criação de `WhatsApp(...)` com Graph API v26.0 central;
- envio normal para WA ID;
- envio inicial para user ID somente antes do compartilhamento obrigatório;
- `request_contact_info(to=user_id, sender=phone_id, ...)`;
- parsing de `ContactsOrigin.CONTACT_REQUEST`;
- `ContactList.first_wa_id` e fallback controlado de `Phone.phone`;
- bloqueio e desbloqueio com WA ID e, quando o envelope inbound não o possuir,
  user ID escopado pela unidade, sem ampliar o fallback dos senders;
- ativação/desativação de WABA e número;
- um smoke test real em ambiente de teste.

Não haverá fallback automático entre versões da Graph API.

## 14. Arquivos e passos de implementação

### Passo 1 — Contratos puros

Criar/alterar, com arquivo completo no apêndice definitivo:

- `core/integrations/whatsapp/identidade.py`;
- `callback/webhook/services/identidade_meta.py`;
- testes usando os quatro JSONs de `payloads/`.

### Passo 2 — Banco declarativo

Atualizar, com arquivo completo:

- `core/database/deploy_database/bank_script.py`;
- `core/database/deploy_database/floodscript.py`;
- `core/database/deploy_database/turno_cliente_script.py`;
- `core/database/deploy_database/povoar_etapas.py`;
- `core/database/deploy_database/etapa_transicao_script.py`;
- `callback/webhook/models.py`;
- `callback/webhook/admin.py`.

O DDL cria `chatbot.user_id_cliente`; o model correspondente usa
`id_user_id_cliente = models.BigAutoField(primary_key=True)`, `models.PROTECT` na
FK de cliente e `models.CASCADE` na FK de unidade, em correspondência a
`ON DELETE RESTRICT`/`ON DELETE CASCADE` do PostgreSQL. Ele será registrado no
Admin em modo somente leitura. O mesmo passo inclui `ativou_user_id` no
CHECK/choices de conversa.

### Passo 3 — Webhook e fila

Atualizar, com arquivo completo:

- parser/serviço de POST;
- população idempotente da fila;
- `callback/webhook/services/flood_guard.py`;
- bloqueio guard;
- repositório de turno;
- `core/cache/runtime/cache_flood_redis.py`;
- `core/cache/cache_flood_memoria.py`;
- `core/repositories/seguranca/bloqueio_meta.py`;
- demais caches Redis e fallbacks em memória que recebem identidade técnica.

Turno e bloqueio escolhem uma única coluna conforme
`tipo_identidade_do_item`. O parser mantém `wa_id_remetente` separado de
`wa_id_compartilhado`; este último só participa do anti-flood quando um
`contact_request` oficial, autenticado e inequívoco fornece a prova pré-commit.

O anti-flood resolve o vínculo permanente por `user_id_cliente` e, antes do
commit do worker, usa uma ponte Redis pendente de 15 segundos escrita
atomicamente nas duas direções. Redis, memória e fallback SQL somam os eventos
dos aliases oficialmente vinculados, com deduplicação por WAMID; novos eventos
incrementam a referência canônica WA ID. Um cache negativo de 5 segundos evita
consultar o RDS a cada evento sem vínculo, e o vínculo confirmado permanece em
cache por 1 hora. Conflito ou indisponibilidade que impeça uma decisão segura
devolve HTTP 503 para reentrega e nunca cria equivalência ou bloqueio por
hipótese. O limite continua 15 WAMIDs distintos em 5 segundos. Essa continuidade
fica nas camadas próprias do webhook/cache/repositório e não cria efeito lateral
dentro da reconciliação transacional.

### Passo 4 — Repositórios e transporte do worker

Atualizar, com arquivo completo:

- fila;
- cliente;
- conversa;
- histórico;
- bloqueio/flood;
- estado do ciclo;
- validação de banco;
- validação de histórico;
- contexto de envio.

Criar também o repositório de `user_id_cliente` e os helpers restritos de
reconciliação. A resolução pelo vínculo deve acontecer antes da criação de
cliente provisório; no handoff, antes da busca prioritária do cliente pelo WA
ID, para não perder a conversa nova.

`flow_worker.py` recebe somente campos adicionais nos dicionários que já
trafegam pelo ciclo. `contexto_banco` alimenta `contexto_historico`, o resolver
recebe esse contexto, passa somente o destinatário escalar ao sender e
`flow_sender()` faz `contexto_envio` refletir os mesmos snapshots. Não se
adicionam retornos terminais, requeues, `continue`, commits, locks ou tratamento
genérico novo.

`montar_mensagem_fila()` calcula a identidade tipada/congelada e sua única
referência de cache; `atualizar_estado_com_mensagem()` registra ambas antes da
validação. Depois, o estado recebe o candidato compartilhado e o WA ID canônico
quando disponíveis. Ordem, logs, finalização, retry e autocura usam a identidade
do item; o reparo stale remove somente a referência registrada. A implementação
não pode reconstruir essa chave pelo WA ID compartilhado/canônico nem remover
cache de outra unidade.

### Passo 5 — Etapa especial e renumeração

Criar e entregar completos, com as fronteiras da seção 7.5:

- `core/integrations/whatsapp/messages/etapa2_messages.py`;
- `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa2.py`;
- `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa2.py`;
- `workers/worker_flow/response_flow/etapas/resolver_etapa2.py`.

Atualizar explicitamente `flow_sender.py`, `transicoes/eventos.py`,
`transicoes/resolver_transicao.py` sem mudar seu algoritmo e
`transacoes/efeitos_transicao.py`. Esse último reconhece 1 -> 2, 1 -> 3 e
2 -> 3; as duas saídas da etapa 1 chamam o mesmo efeito de persistência do nome
por `id_cliente`, com evento/destino efetivos e sem hardcode legado, e 2 -> 3 não
repete SQL de identidade.

Renumerar mecanicamente todos os arquivos atuais 2..22 para 3..23, incluindo
mensagens, senders, validadores, resolvers, constantes, imports, IDs usados nos
efeitos, testes, catálogo e mapa. O conteúdo/regra das etapas atuais não muda e
a etapa terminal 23 não ganha resolver.

Nos caminhos físicos, a movimentação ocorre em ordem decrescente — 22 -> 23 até
2 -> 3 — ou por nomes temporários equivalentes. Só depois é criado o novo
arquivo da etapa 2, evitando sobrescrever módulos da baseline.

A renumeração inclui explicitamente:

- a confirmação atual 3 -> futura 4, seu bloco idempotente em
  `flow_sender.py`, seu evento único `destino_atendimento_confirmado`, a saída
  obrigatória para a profissão e os efeitos de valor absoluto reconstruídos
  somente de `status_dependente` booleano persistido;
- a profissão atual 4 -> futura 5 e os adaptadores contextuais
  `validador_reforco_escolar_etapa4.py` ->
  `validador_reforco_escolar_etapa5.py` e
  `validador_financeiro_etapa4.py` ->
  `validador_financeiro_etapa5.py`, com imports e testes ajustados. A etapa 5
  permanece obrigatória nos dois fluxos e somente ela bifurca dependente para 6
  ou titular para 7;
- a introdução à triagem atual 11 -> futura 12;
- `core/triagem/perguntas.py`, cujas chaves atuais 12..17 passam a 13..18;
- `valida_historico.ETAPAS_TRIAGEM`, que passa de 11..17 para 12..18;
- `core/repositories/fluxo/contextos/triagem.py`, os módulos numerados de
  triagem, `pywa_senders/triagem_base.py` e o contexto atual da etapa 18, que
  passa a representar o agendamento na etapa 19; a carga desse contexto muda
  dos ciclos 17/18 para 18/19;
- `core/repositories/funil/leads.py`, com filtro das respostas 13..18;
- `core/integrations/funil/oportunidades.py`, com conjunto esperado 13..18;
- `core/integrations/whatsapp/messages/triagem_componentes.py`;
- `REGRAS_DE_NEGOCIO.md`, `PADROES_DE_ARQUITETURA.md`,
  `ROTINA_IMPLEMENTACAO_ETAPAS.md` e `tests/README.md`, para que a documentação
  aplicada não mantenha IDs anteriores;
- testes de confirmação, triagem etária, Funil, tratamentos, efeitos,
  transições, deploy, roteamento e terminalidade.

### Passo 6 — Senders e Meta

Centralizar a seleção consciente da etapa: WA ID sempre prioritário; user ID só
quando o resolver do envio da etapa 1 ou do pedido/repetição de compartilhamento
habilitar explicitamente o fallback. A resposta válida da etapa 2 e todos os envios
posteriores exigem WA ID. Alterar apenas as assinaturas/calls necessárias e
garantir o mesmo contrato no retorno idempotente de `flow_sender()`. Não
regredir textos, tratamentos, perguntas etárias ou regras das etapas atuais; a
mudança nelas é de numeração e de transporte dos novos snapshots.

O resolver chama o helper puro com a permissão explícita da etapa e passa apenas
o destinatário escalar ao sender. O sender não recebe o contexto inteiro para
decidir fallback. `flow_sender()` acrescenta os snapshots ao retorno de todo
resolver e ao retorno idempotente antes de devolver `contexto_envio`.

### Passo 7 — Funil, bloqueio e Admin

No Funil, manter WA ID obrigatório e acrescentar username somente como
informação opcional quando existir. Preservar o relatório atual com as seis
perguntas e respostas em ordem, usando o catálogo compartilhado e nunca o
resumo quantitativo antigo. Não transferir, reagendar ou conciliar itens de
`funil_envios` durante a reconciliação. Bloqueio e Admin recebem apenas as
adaptações declarativas necessárias aos campos anuláveis. Na implementação
futura, atualizar as choices e `MOTIVOS_ENCERRAMENTO_VALIDOS` com
`ativou_user_id`.

### Passo 8 — PyWa

Atualizar `requirements.txt`, adaptar apenas APIs incompatíveis e executar os
smokes reais antes de produção.

### Passo 9 — SQL manual final

O SQL abaixo é a migração-base completa para o schema atual. Ele deverá ser
revalidado contra o commit definitivo antes da execução, porque os serviços e o
banco ainda não receberam esta feature.

```sql
BEGIN;

SET LOCAL lock_timeout = '15s';
SET LOCAL statement_timeout = '0';

LOCK TABLE
    chatbot.unidade,
    chatbot.cliente,
    chatbot.etapa,
    chatbot.etapa_transicao,
    chatbot.conversa,
    chatbot.dependente,
    chatbot.fila_mensagens,
    chatbot.historico_mensagens,
    chatbot.respostas_desafios,
    chatbot.cliente_bloqueado_meta,
    chatbot.webhook_flood_evento,
    chatbot.funil_envios
IN ACCESS EXCLUSIVE MODE;

DO $preflight$
DECLARE
    etapas_atuais INTEGER;
    etapas_atuais_corretas INTEGER;
    transicoes_atuais INTEGER;
    transicoes_atuais_corretas INTEGER;
    filas_abertas INTEGER;
    conversas_processando INTEGER;
    funil_aberto INTEGER;
    definicao_motivo TEXT;
    motivos_atuais TEXT[];
    corpo_dequeue_atual TEXT;
BEGIN
    SELECT COUNT(*) INTO etapas_atuais FROM chatbot.etapa;
    SELECT COUNT(*) INTO transicoes_atuais FROM chatbot.etapa_transicao;

    SELECT COUNT(*)
    INTO etapas_atuais_corretas
    FROM chatbot.etapa AS etapa
    JOIN (
        VALUES
            (1,  'Saudação e nome do cliente',                         FALSE, 0,  FALSE),
            (2,  'Destino do atendimento',                             FALSE, 0,  FALSE),
            (3,  'Confirmação do destino do atendimento',              FALSE, 0,  FALSE),
            (4,  'Profissão do cliente',                               FALSE, 0,  FALSE),
            (5,  'Nome do dependente',                                 FALSE, 0,  FALSE),
            (6,  'Idade do aluno',                                     FALSE, 0,  FALSE),
            (7,  'Oferta de aula experimental e avaliação cognitiva', FALSE, 0,  FALSE),
            (8,  'Oferta adiada e Instagram',                          FALSE, 0,  FALSE),
            (9,  'Confirmação de retorno ao atendimento',              FALSE, 0,  FALSE),
            (10, 'Email',                                              FALSE, 0,  FALSE),
            (11, 'Introdução à triagem cognitiva',                     FALSE, 0,  FALSE),
            (12, 'Triagem cognitiva - pergunta 1',                     FALSE, 0,  FALSE),
            (13, 'Triagem cognitiva - pergunta 2',                     FALSE, 0,  FALSE),
            (14, 'Triagem cognitiva - pergunta 3',                     FALSE, 0,  FALSE),
            (15, 'Triagem cognitiva - pergunta 4',                     FALSE, 0,  FALSE),
            (16, 'Triagem cognitiva - pergunta 5',                     FALSE, 0,  FALSE),
            (17, 'Triagem cognitiva - pergunta 6',                     FALSE, 0,  FALSE),
            (18, 'Agendamento após a triagem cognitiva',               FALSE, 0,  TRUE),
            (19, 'Pesquisa de satisfação - nota',                      FALSE, 0,  TRUE),
            (20, 'Pesquisa de satisfação - opção de comentário',       FALSE, 0,  TRUE),
            (21, 'Pesquisa de satisfação - comentário',                FALSE, 0,  TRUE),
            (22, 'Finalização do atendimento',                         TRUE,  30, TRUE)
    ) AS esperado(
        id_etapa,
        nome_etapa,
        encerra_automaticamente,
        bloqueio_dias,
        elegivel_funil
    )
      ON etapa.id_etapa = esperado.id_etapa
     AND etapa.nome_etapa = esperado.nome_etapa
     AND etapa.encerra_automaticamente = esperado.encerra_automaticamente
     AND etapa.bloqueio_dias = esperado.bloqueio_dias
     AND etapa.elegivel_funil = esperado.elegivel_funil;

    SELECT COUNT(*)
    INTO transicoes_atuais_corretas
    FROM chatbot.etapa_transicao AS transicao
    JOIN (
        VALUES
            (1,  'nome_cliente_valido',                    2),
            (2,  'destino_atendimento_definido',           3),
            (3,  'destino_atendimento_confirmado',          4),
            (4,  'profissao_dependente_valida',            5),
            (4,  'profissao_titular_valida',               6),
            (5,  'nome_dependente_valido',                 6),
            (6,  'idade_valida',                           7),
            (7,  'oferta_aceita',                         10),
            (7,  'oferta_adiada',                          8),
            (8,  'cliente_retornou',                       9),
            (9,  'retorno_confirmado',                    10),
            (9,  'retorno_adiado',                         8),
            (10, 'email_valido',                          11),
            (11, 'triagem_iniciada',                      12),
            (12, 'triagem_pergunta_1_respondida',         13),
            (13, 'triagem_pergunta_2_respondida',         14),
            (14, 'triagem_pergunta_3_respondida',         15),
            (15, 'triagem_pergunta_4_respondida',         16),
            (16, 'triagem_pergunta_5_respondida',         17),
            (17, 'triagem_pergunta_6_respondida',         18),
            (18, 'agendamento_confirmado',                19),
            (19, 'satisfacao_avaliada',                   20),
            (20, 'comentario_satisfacao_aceito',          21),
            (20, 'comentario_satisfacao_recusado',        22),
            (21, 'comentario_satisfacao_recebido',        22)
    ) AS esperado(id_etapa_origem, evento, id_etapa_destino)
      ON transicao.id_etapa_origem = esperado.id_etapa_origem
     AND transicao.evento = esperado.evento
     AND transicao.id_etapa_destino = esperado.id_etapa_destino;

    SELECT COUNT(*)
    INTO filas_abertas
    FROM chatbot.fila_mensagens
    WHERE status IN ('pending', 'processing');

    SELECT COUNT(*)
    INTO conversas_processando
    FROM chatbot.conversa
    WHERE processing IS TRUE;

    SELECT COUNT(*)
    INTO funil_aberto
    FROM chatbot.funil_envios
    WHERE status IN ('pending', 'processing');

    IF filas_abertas <> 0
       OR conversas_processando <> 0
       OR funil_aberto <> 0
    THEN
        RAISE EXCEPTION
            'Migração recusada: trabalho operacional aberto '
            '(fila=%, conversa=%, funil=%).',
            filas_abertas,
            conversas_processando,
            funil_aberto;
    END IF;

    IF etapas_atuais <> 22
       OR etapas_atuais_corretas <> 22
       OR transicoes_atuais <> 25
       OR transicoes_atuais_corretas <> 25
    THEN
        RAISE EXCEPTION
            'Migração recusada: catálogo/mapa atual não corresponde exatamente '
            'à V1.0.5 (etapas=%/%; transições=%/%).',
            etapas_atuais,
            etapas_atuais_corretas,
            transicoes_atuais,
            transicoes_atuais_corretas;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM chatbot.etapa
        WHERE id_etapa = 22
          AND nome_etapa = 'Finalização do atendimento'
          AND encerra_automaticamente IS TRUE
          AND bloqueio_dias = 30
          AND elegivel_funil IS TRUE
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: etapa final atual não corresponde à V1.0.5.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM chatbot.respostas_desafios
        WHERE id_etapa NOT BETWEEN 12 AND 17
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: resposta de triagem fora das etapas 12..17 da V1.0.5.';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'cliente'
          AND column_name = 'waid_telefone'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'fila_mensagens'
          AND column_name = 'cliente_telefone'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'historico_mensagens'
          AND column_name = 'cliente_telefone'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'cliente_bloqueado_meta'
          AND column_name = 'wa_id_cliente'
    ) OR NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND table_name = 'webhook_flood_evento'
          AND column_name = 'wa_id_cliente'
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: colunas legadas esperadas não foram encontradas.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'chatbot'
          AND column_name IN ('user_id', 'username', 'id_portfolio')
          AND table_name IN (
              'unidade',
              'cliente',
              'fila_mensagens',
              'historico_mensagens',
              'conversa',
              'cliente_bloqueado_meta',
              'webhook_flood_evento'
          )
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: schema aparenta estar parcial ou já migrado.';
    END IF;

    IF TO_REGCLASS('chatbot.user_id_cliente') IS NOT NULL THEN
        RAISE EXCEPTION
            'Migração recusada: tabela user_id_cliente já existe.';
    END IF;

    SELECT pg_get_constraintdef(oid)
    INTO definicao_motivo
    FROM pg_constraint
    WHERE conrelid = 'chatbot.conversa'::REGCLASS
      AND conname = 'ck_conversa_motivo_encerramento'
      AND contype = 'c'
      AND convalidated IS TRUE;

    SELECT ARRAY(
        SELECT DISTINCT ocorrencia[1]
        FROM regexp_matches(
            definicao_motivo,
            $regex$'([^']+)'$regex$,
            'g'
        ) AS ocorrencia
        ORDER BY ocorrencia[1]
    )
    INTO motivos_atuais;

    IF definicao_motivo IS NULL
       OR POSITION('MOTIVO_ENCERRAMENTO IS NULL' IN UPPER(definicao_motivo)) = 0
       OR motivos_atuais IS DISTINCT FROM ARRAY[
            'foi_agendado',
            'idade_invalida'
       ]::TEXT[]
    THEN
        RAISE EXCEPTION
            'Migração recusada: CHECK atual de motivo não corresponde exatamente à base esperada.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'chatbot.cliente'::REGCLASS
          AND conname = 'cliente_waid_telefone_key'
          AND contype = 'u'
          AND convalidated IS TRUE
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: UNIQUE global do WA ID legado não encontrada.';
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'chatbot.cliente_bloqueado_meta'::REGCLASS
          AND conname = 'uq_cliente_bloqueado_meta_wa_unidade'
          AND contype = 'u'
          AND convalidated IS TRUE
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: UNIQUE de bloqueio WA/unidade não encontrada.';
    END IF;

    SELECT p.prosrc
    INTO corpo_dequeue_atual
    FROM pg_proc AS p
    WHERE p.oid = TO_REGPROCEDURE('chatbot.dequeue_message()')
      AND p.prokind = 'f'
      AND p.pronargs = 0
      AND p.proretset IS TRUE
      AND p.prorettype = 'record'::REGTYPE
      AND p.proargnames = ARRAY[
          'id_mensagem',
          'cliente_telefone',
          'conteudo_texto',
          'tipo_mensagem',
          'id_phone_unidade',
          'unidade_telefone',
          'received_data_hora',
          'id_hash_msg',
          'retry_count'
      ]::TEXT[]
      AND p.proargmodes = ARRAY[
          't', 't', 't', 't', 't', 't', 't', 't', 't'
      ]::"char"[]
      AND p.proallargtypes = ARRAY[
          'int4'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'text'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'timestamptz'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'int4'::REGTYPE::OID
      ]::OID[];

    IF corpo_dequeue_atual IS NULL
       OR POSITION('WITH NEXT_JOB AS' IN UPPER(corpo_dequeue_atual)) = 0
       OR POSITION('FOR UPDATE SKIP LOCKED' IN UPPER(corpo_dequeue_atual)) = 0
       OR POSITION('RETRY_COUNT = F.RETRY_COUNT + 1' IN UPPER(corpo_dequeue_atual)) = 0
       OR POSITION('INTERVAL ''2 MINUTES''' IN UPPER(corpo_dequeue_atual)) = 0
    THEN
        RAISE EXCEPTION
            'Migração recusada: assinatura ou algoritmo atual de dequeue_message diverge da base esperada.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM chatbot.fila_mensagens
        WHERE LENGTH(cliente_telefone) > 50
    ) OR EXISTS (
        SELECT 1
        FROM chatbot.historico_mensagens
        WHERE LENGTH(cliente_telefone) > 50
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: WA ID legado excede VARCHAR(50).';
    END IF;
END
$preflight$;

-- Mapa explícito do estado atual. Antes do deploy, revisar este bloco e incluir
-- exatamente uma linha para cada unidade existente. Não inferir pelo WABA.
CREATE TEMP TABLE pg_temp.migracao_portfolios (
    id_unidade INTEGER PRIMARY KEY,
    id_portfolio VARCHAR(100) NOT NULL,
    CONSTRAINT ck_migracao_portfolio_nao_vazio
        CHECK (BTRIM(id_portfolio) <> '')
) ON COMMIT DROP;

INSERT INTO pg_temp.migracao_portfolios (id_unidade, id_portfolio)
VALUES
    (1, '1227425428614580');

DO $validar_mapa_portfolios$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM chatbot.unidade AS unidade
        FULL JOIN pg_temp.migracao_portfolios AS mapa
          ON mapa.id_unidade = unidade.id_unidade
        WHERE unidade.id_unidade IS NULL
           OR mapa.id_unidade IS NULL
    ) THEN
        RAISE EXCEPTION
            'Migração recusada: mapa de id_portfolio não cobre exatamente todas as unidades.';
    END IF;
END
$validar_mapa_portfolios$;

CREATE TEMP TABLE pg_temp.migracao_user_id_contagens
ON COMMIT DROP
AS
SELECT 'cliente' AS tabela, COUNT(*)::BIGINT AS registros
FROM chatbot.cliente
UNION ALL
SELECT 'conversa', COUNT(*) FROM chatbot.conversa
UNION ALL
SELECT 'dependente', COUNT(*) FROM chatbot.dependente
UNION ALL
SELECT 'fila_mensagens', COUNT(*) FROM chatbot.fila_mensagens
UNION ALL
SELECT 'historico_mensagens', COUNT(*) FROM chatbot.historico_mensagens
UNION ALL
SELECT 'respostas_desafios', COUNT(*) FROM chatbot.respostas_desafios
UNION ALL
SELECT 'cliente_bloqueado_meta', COUNT(*)
FROM chatbot.cliente_bloqueado_meta
UNION ALL
SELECT 'webhook_flood_evento', COUNT(*)
FROM chatbot.webhook_flood_evento
UNION ALL
SELECT 'funil_envios', COUNT(*) FROM chatbot.funil_envios;

CREATE TEMP TABLE pg_temp.migracao_respostas_etapas (
    id_resposta_desafio INTEGER PRIMARY KEY,
    id_etapa INTEGER NOT NULL
) ON COMMIT DROP;

INSERT INTO pg_temp.migracao_respostas_etapas (
    id_resposta_desafio,
    id_etapa
)
SELECT
    id_resposta_desafio,
    id_etapa
FROM chatbot.respostas_desafios;

DROP FUNCTION chatbot.dequeue_message();

ALTER TABLE chatbot.cliente
    RENAME COLUMN waid_telefone TO wa_id;

ALTER TABLE chatbot.fila_mensagens
    RENAME COLUMN cliente_telefone TO wa_id;

ALTER TABLE chatbot.historico_mensagens
    RENAME COLUMN cliente_telefone TO wa_id;

ALTER TABLE chatbot.cliente_bloqueado_meta
    RENAME COLUMN wa_id_cliente TO wa_id;

ALTER TABLE chatbot.webhook_flood_evento
    RENAME COLUMN wa_id_cliente TO wa_id;

ALTER TABLE chatbot.cliente
    RENAME CONSTRAINT cliente_waid_telefone_key
    TO cliente_wa_id_key;

ALTER TABLE chatbot.cliente_bloqueado_meta
    RENAME CONSTRAINT uq_cliente_bloqueado_meta_wa_unidade
    TO uq_cliente_bloqueado_meta_wa_id_unidade;

ALTER TABLE chatbot.unidade
    ADD COLUMN id_portfolio VARCHAR(100) NULL;

UPDATE chatbot.unidade AS unidade
SET id_portfolio = mapa.id_portfolio
FROM pg_temp.migracao_portfolios AS mapa
WHERE mapa.id_unidade = unidade.id_unidade;

ALTER TABLE chatbot.unidade
    ALTER COLUMN id_portfolio SET NOT NULL;

ALTER TABLE chatbot.cliente
    ADD COLUMN username VARCHAR(255) NULL,
    ALTER COLUMN wa_id DROP NOT NULL;

ALTER TABLE chatbot.fila_mensagens
    ADD COLUMN user_id VARCHAR(255) NULL,
    ADD COLUMN username VARCHAR(255) NULL,
    ALTER COLUMN wa_id TYPE VARCHAR(50),
    ALTER COLUMN wa_id DROP NOT NULL;

ALTER TABLE chatbot.historico_mensagens
    ADD COLUMN user_id VARCHAR(255) NULL,
    ADD COLUMN username VARCHAR(255) NULL,
    ALTER COLUMN wa_id TYPE VARCHAR(50),
    ALTER COLUMN wa_id DROP NOT NULL;

ALTER TABLE chatbot.conversa
    ADD COLUMN wa_id VARCHAR(50) NULL,
    ADD COLUMN user_id VARCHAR(255) NULL,
    ADD COLUMN username VARCHAR(255) NULL;

ALTER TABLE chatbot.cliente_bloqueado_meta
    ADD COLUMN user_id VARCHAR(255) NULL,
    ADD COLUMN username VARCHAR(255) NULL,
    ALTER COLUMN wa_id DROP NOT NULL;

ALTER TABLE chatbot.webhook_flood_evento
    ADD COLUMN user_id VARCHAR(255) NULL,
    ADD COLUMN username VARCHAR(255) NULL,
    ALTER COLUMN wa_id DROP NOT NULL;

CREATE TABLE chatbot.user_id_cliente (
    id_user_id_cliente BIGSERIAL PRIMARY KEY,
    id_cliente INTEGER NOT NULL,
    user_id VARCHAR(255) NOT NULL,
    id_unidade INTEGER NOT NULL,

    CONSTRAINT ck_user_id_cliente_user_id_nao_vazio
        CHECK (BTRIM(user_id) <> ''),

    CONSTRAINT fk_user_id_cliente_cliente
        FOREIGN KEY (id_cliente)
        REFERENCES chatbot.cliente(id_cliente)
        ON DELETE RESTRICT,

    CONSTRAINT fk_user_id_cliente_unidade
        FOREIGN KEY (id_unidade)
        REFERENCES chatbot.unidade(id_unidade)
        ON DELETE CASCADE,

    CONSTRAINT uq_user_id_cliente_user_unidade
        UNIQUE (user_id, id_unidade),

    CONSTRAINT uq_user_id_cliente_cliente_unidade
        UNIQUE (id_cliente, id_unidade)
);

CREATE INDEX idx_user_id_cliente_id_unidade
ON chatbot.user_id_cliente (id_unidade, id_cliente);

-- Conversas existentes herdam o WA ID global sem alterar o cliente.
UPDATE chatbot.conversa AS conversa
SET wa_id = cliente.wa_id
FROM chatbot.cliente AS cliente
WHERE cliente.id_cliente = conversa.id_cliente
  AND conversa.wa_id IS NULL;

ALTER TABLE chatbot.unidade
    ADD CONSTRAINT ck_unidade_id_portfolio_nao_vazio
    CHECK (BTRIM(id_portfolio) <> '');

ALTER TABLE chatbot.conversa
    DROP CONSTRAINT ck_conversa_motivo_encerramento,
    ADD CONSTRAINT ck_conversa_motivo_encerramento
        CHECK (
            motivo_encerramento IS NULL
            OR motivo_encerramento IN (
                'idade_invalida',
                'foi_agendado',
                'ativou_user_id'
            )
        );

ALTER TABLE chatbot.cliente
    ADD CONSTRAINT ck_cliente_wa_id_nao_vazio
        CHECK (wa_id IS NULL OR BTRIM(wa_id) <> ''),
    ADD CONSTRAINT ck_cliente_username_nao_vazio
        CHECK (username IS NULL OR BTRIM(username) <> '');

ALTER TABLE chatbot.fila_mensagens
    ADD CONSTRAINT ck_fila_wa_id_nao_vazio
        CHECK (wa_id IS NULL OR BTRIM(wa_id) <> ''),
    ADD CONSTRAINT ck_fila_user_id_nao_vazio
        CHECK (user_id IS NULL OR BTRIM(user_id) <> ''),
    ADD CONSTRAINT ck_fila_identidade_meta
        CHECK (
            NULLIF(BTRIM(wa_id), '') IS NOT NULL
            OR NULLIF(BTRIM(user_id), '') IS NOT NULL
        ),
    ADD CONSTRAINT ck_fila_username_nao_vazio
        CHECK (username IS NULL OR BTRIM(username) <> '');

ALTER TABLE chatbot.historico_mensagens
    ADD CONSTRAINT ck_historico_wa_id_nao_vazio
        CHECK (wa_id IS NULL OR BTRIM(wa_id) <> ''),
    ADD CONSTRAINT ck_historico_user_id_nao_vazio
        CHECK (user_id IS NULL OR BTRIM(user_id) <> ''),
    ADD CONSTRAINT ck_historico_identidade_meta
        CHECK (
            NULLIF(BTRIM(wa_id), '') IS NOT NULL
            OR NULLIF(BTRIM(user_id), '') IS NOT NULL
        ),
    ADD CONSTRAINT ck_historico_username_nao_vazio
        CHECK (username IS NULL OR BTRIM(username) <> '');

ALTER TABLE chatbot.conversa
    ADD CONSTRAINT ck_conversa_wa_id_nao_vazio
        CHECK (wa_id IS NULL OR BTRIM(wa_id) <> ''),
    ADD CONSTRAINT ck_conversa_user_id_nao_vazio
        CHECK (user_id IS NULL OR BTRIM(user_id) <> ''),
    ADD CONSTRAINT ck_conversa_identidade_meta
        CHECK (
            NULLIF(BTRIM(wa_id), '') IS NOT NULL
            OR NULLIF(BTRIM(user_id), '') IS NOT NULL
        ),
    ADD CONSTRAINT ck_conversa_username_nao_vazio
        CHECK (username IS NULL OR BTRIM(username) <> '');

ALTER TABLE chatbot.cliente_bloqueado_meta
    ADD CONSTRAINT ck_bloqueio_wa_id_nao_vazio
        CHECK (wa_id IS NULL OR BTRIM(wa_id) <> ''),
    ADD CONSTRAINT ck_bloqueio_user_id_nao_vazio
        CHECK (user_id IS NULL OR BTRIM(user_id) <> ''),
    ADD CONSTRAINT ck_bloqueio_identidade_meta
        CHECK (
            NULLIF(BTRIM(wa_id), '') IS NOT NULL
            OR NULLIF(BTRIM(user_id), '') IS NOT NULL
        ),
    ADD CONSTRAINT ck_bloqueio_username_nao_vazio
        CHECK (username IS NULL OR BTRIM(username) <> '');

ALTER TABLE chatbot.webhook_flood_evento
    ADD CONSTRAINT ck_flood_wa_id_nao_vazio
        CHECK (wa_id IS NULL OR BTRIM(wa_id) <> ''),
    ADD CONSTRAINT ck_flood_user_id_nao_vazio
        CHECK (user_id IS NULL OR BTRIM(user_id) <> ''),
    ADD CONSTRAINT ck_flood_identidade_meta
        CHECK (
            NULLIF(BTRIM(wa_id), '') IS NOT NULL
            OR NULLIF(BTRIM(user_id), '') IS NOT NULL
        ),
    ADD CONSTRAINT ck_flood_username_nao_vazio
        CHECK (username IS NULL OR BTRIM(username) <> '');

CREATE INDEX idx_unidade_id_portfolio
ON chatbot.unidade (id_portfolio);

ALTER INDEX chatbot.idx_fila_cliente_unidade_aberta
    RENAME TO idx_fila_wa_unidade_aberta;

ALTER INDEX chatbot.idx_fila_cliente_unidade_conversa_aberta
    RENAME TO idx_fila_wa_unidade_conversa_aberta;

CREATE INDEX idx_fila_user_unidade_aberta
ON chatbot.fila_mensagens (
    user_id,
    id_phone_unidade,
    status,
    received_data_hora,
    id_mensagem
)
WHERE user_id IS NOT NULL
  AND status IN ('pending', 'processing');

CREATE INDEX idx_fila_user_unidade_conversa_aberta
ON chatbot.fila_mensagens (
    user_id,
    id_phone_unidade,
    id_conversa,
    id_hash_msg,
    id_mensagem
)
WHERE user_id IS NOT NULL
  AND status IN ('pending', 'processing');

CREATE INDEX idx_conversa_wa_unidade
ON chatbot.conversa (wa_id, id_unidade, finalizou_em DESC)
WHERE wa_id IS NOT NULL;

CREATE INDEX idx_conversa_user_unidade
ON chatbot.conversa (user_id, id_unidade, finalizou_em DESC)
WHERE user_id IS NOT NULL;

CREATE UNIQUE INDEX uq_cliente_bloqueado_meta_user_id_unidade
ON chatbot.cliente_bloqueado_meta (user_id, id_unidade)
WHERE user_id IS NOT NULL;

CREATE UNIQUE INDEX uq_cliente_bloqueado_meta_cliente_unidade
ON chatbot.cliente_bloqueado_meta (id_cliente, id_unidade)
WHERE id_cliente IS NOT NULL;

CREATE INDEX idx_webhook_flood_evento_user_janela
ON chatbot.webhook_flood_evento (
    user_id,
    phone_id_unidade,
    received_at DESC
)
WHERE user_id IS NOT NULL;

-- O mapa é declarativo e será recriado depois do deslocamento 2..22 -> 3..23.
TRUNCATE TABLE chatbot.etapa_transicao RESTART IDENTITY;

INSERT INTO chatbot.etapa (
    id_etapa,
    nome_etapa,
    encerra_automaticamente,
    bloqueio_dias,
    elegivel_funil
)
VALUES (
    23,
    '__migracao_user_id_etapa_23__',
    FALSE,
    0,
    FALSE
);

DO $remapear_referencias$
DECLARE
    etapa_antiga INTEGER;
BEGIN
    -- A ordem decrescente evita colisão na UNIQUE
    -- respostas_desafios(id_conversa, id_etapa), inclusive em 12..17 -> 13..18.
    FOR etapa_antiga IN REVERSE 22..2 LOOP
        UPDATE chatbot.conversa
        SET id_etapa_atual = etapa_antiga + 1
        WHERE id_etapa_atual = etapa_antiga;

        UPDATE chatbot.historico_mensagens
        SET id_etapa = etapa_antiga + 1
        WHERE id_etapa = etapa_antiga;

        UPDATE chatbot.respostas_desafios
        SET id_etapa = etapa_antiga + 1
        WHERE id_etapa = etapa_antiga;
    END LOOP;
END
$remapear_referencias$;

UPDATE chatbot.etapa
SET nome_etapa = FORMAT('__migracao_user_id_%s__', id_etapa)
WHERE id_etapa BETWEEN 2 AND 23;

INSERT INTO chatbot.etapa (
    id_etapa,
    nome_etapa,
    encerra_automaticamente,
    bloqueio_dias,
    elegivel_funil
)
VALUES
    (1,  'Saudação e nome do cliente',                         FALSE, 0,  FALSE),
    (2,  'Compartilhamento oficial do contato',                FALSE, 0,  FALSE),
    (3,  'Destino do atendimento',                             FALSE, 0,  FALSE),
    (4,  'Confirmação do destino do atendimento',              FALSE, 0,  FALSE),
    (5,  'Profissão do cliente',                               FALSE, 0,  FALSE),
    (6,  'Nome do dependente',                                 FALSE, 0,  FALSE),
    (7,  'Idade do aluno',                                     FALSE, 0,  FALSE),
    (8,  'Oferta de aula experimental e avaliação cognitiva', FALSE, 0,  FALSE),
    (9,  'Oferta adiada e Instagram',                          FALSE, 0,  FALSE),
    (10, 'Confirmação de retorno ao atendimento',              FALSE, 0,  FALSE),
    (11, 'Email',                                              FALSE, 0,  FALSE),
    (12, 'Introdução à triagem cognitiva',                     FALSE, 0,  FALSE),
    (13, 'Triagem cognitiva - pergunta 1',                     FALSE, 0,  FALSE),
    (14, 'Triagem cognitiva - pergunta 2',                     FALSE, 0,  FALSE),
    (15, 'Triagem cognitiva - pergunta 3',                     FALSE, 0,  FALSE),
    (16, 'Triagem cognitiva - pergunta 4',                     FALSE, 0,  FALSE),
    (17, 'Triagem cognitiva - pergunta 5',                     FALSE, 0,  FALSE),
    (18, 'Triagem cognitiva - pergunta 6',                     FALSE, 0,  FALSE),
    (19, 'Agendamento após a triagem cognitiva',               FALSE, 0,  TRUE),
    (20, 'Pesquisa de satisfação - nota',                      FALSE, 0,  TRUE),
    (21, 'Pesquisa de satisfação - opção de comentário',       FALSE, 0,  TRUE),
    (22, 'Pesquisa de satisfação - comentário',                FALSE, 0,  TRUE),
    (23, 'Finalização do atendimento',                         TRUE,  30, TRUE)
ON CONFLICT (id_etapa)
DO UPDATE SET
    nome_etapa = EXCLUDED.nome_etapa,
    encerra_automaticamente = EXCLUDED.encerra_automaticamente,
    bloqueio_dias = EXCLUDED.bloqueio_dias,
    elegivel_funil = EXCLUDED.elegivel_funil;

INSERT INTO chatbot.etapa_transicao (
    id_etapa_origem,
    evento,
    id_etapa_destino
)
VALUES
    (1,  'nome_cliente_valido_com_wa_id',          3),
    (1,  'nome_cliente_valido_sem_wa_id',          2),
    (2,  'contato_oficial_compartilhado',          3),
    (3,  'destino_atendimento_definido',           4),
    (4,  'destino_atendimento_confirmado',          5),
    (5,  'profissao_dependente_valida',            6),
    (5,  'profissao_titular_valida',               7),
    (6,  'nome_dependente_valido',                 7),
    (7,  'idade_valida',                           8),
    (8,  'oferta_aceita',                         11),
    (8,  'oferta_adiada',                          9),
    (9,  'cliente_retornou',                      10),
    (10, 'retorno_confirmado',                    11),
    (10, 'retorno_adiado',                         9),
    (11, 'email_valido',                          12),
    (12, 'triagem_iniciada',                      13),
    (13, 'triagem_pergunta_1_respondida',         14),
    (14, 'triagem_pergunta_2_respondida',         15),
    (15, 'triagem_pergunta_3_respondida',         16),
    (16, 'triagem_pergunta_4_respondida',         17),
    (17, 'triagem_pergunta_5_respondida',         18),
    (18, 'triagem_pergunta_6_respondida',         19),
    (19, 'agendamento_confirmado',                20),
    (20, 'satisfacao_avaliada',                   21),
    (21, 'comentario_satisfacao_aceito',          22),
    (21, 'comentario_satisfacao_recusado',        23),
    (22, 'comentario_satisfacao_recebido',        23);

SELECT setval(
    pg_get_serial_sequence('chatbot.etapa', 'id_etapa'),
    23,
    TRUE
);

SELECT setval(
    pg_get_serial_sequence('chatbot.etapa_transicao', 'id_transicao'),
    27,
    TRUE
);

CREATE FUNCTION chatbot.dequeue_message()
RETURNS TABLE (
    id_mensagem INT,
    wa_id VARCHAR,
    user_id VARCHAR,
    username VARCHAR,
    conteudo_texto TEXT,
    tipo_mensagem VARCHAR,
    id_phone_unidade VARCHAR,
    unidade_telefone VARCHAR,
    received_data_hora TIMESTAMPTZ,
    id_hash_msg VARCHAR,
    retry_count INT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    WITH next_job AS (
        SELECT f.id_mensagem
        FROM chatbot.fila_mensagens AS f
        WHERE
            (
                f.status = 'pending'
                AND f.next_attempt_at <= NOW()
            )
            OR
            (
                f.status = 'processing'
                AND f.processing_started_at
                    < NOW() - INTERVAL '2 minutes'
            )
        ORDER BY
            CASE
                WHEN f.status = 'pending' THEN f.next_attempt_at
                WHEN f.status = 'processing' THEN f.processing_started_at
            END NULLS FIRST,
            f.id_mensagem
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    UPDATE chatbot.fila_mensagens AS f
    SET
        status = 'processing',
        retry_count = f.retry_count + 1,
        processing_started_at = NOW()
    FROM next_job
    WHERE f.id_mensagem = next_job.id_mensagem
    RETURNING
        f.id_mensagem,
        f.wa_id,
        f.user_id,
        f.username,
        f.conteudo_texto,
        f.tipo_mensagem,
        f.id_phone_unidade,
        f.unidade_telefone,
        f.received_data_hora,
        f.id_hash_msg,
        f.retry_count;
END;
$$;

DO $pos_validacao$
DECLARE
    colunas_invalidas INTEGER;
    colunas_obrigatorias_invalidas INTEGER;
    constraints_obrigatorias INTEGER;
    indices_obrigatorios INTEGER;
    etapas_finais_corretas INTEGER;
    transicoes_finais_corretas INTEGER;
    referencias_invalidas RECORD;
    corpo_dequeue_final TEXT;
    definicao_motivo_final TEXT;
    motivos_finais TEXT[];
BEGIN
    SELECT COUNT(*)
    INTO colunas_invalidas
    FROM (
        VALUES
            ('cliente',                 'wa_id',         50),
            ('cliente',                 'username',     255),
            ('fila_mensagens',          'wa_id',         50),
            ('fila_mensagens',          'user_id',      255),
            ('fila_mensagens',          'username',     255),
            ('historico_mensagens',     'wa_id',         50),
            ('historico_mensagens',     'user_id',      255),
            ('historico_mensagens',     'username',     255),
            ('conversa',                'wa_id',         50),
            ('conversa',                'user_id',      255),
            ('conversa',                'username',     255),
            ('cliente_bloqueado_meta',  'wa_id',         50),
            ('cliente_bloqueado_meta',  'user_id',      255),
            ('cliente_bloqueado_meta',  'username',     255),
            ('webhook_flood_evento',    'wa_id',         50),
            ('webhook_flood_evento',    'user_id',      255),
            ('webhook_flood_evento',    'username',     255)
    ) AS esperado(table_name, column_name, max_length)
    LEFT JOIN information_schema.columns AS coluna
      ON coluna.table_schema = 'chatbot'
     AND coluna.table_name = esperado.table_name
     AND coluna.column_name = esperado.column_name
    WHERE coluna.column_name IS NULL
       OR coluna.data_type <> 'character varying'
       OR coluna.character_maximum_length IS DISTINCT FROM esperado.max_length
       OR coluna.is_nullable <> 'YES'
       OR coluna.column_default IS NOT NULL;

    IF colunas_invalidas <> 0 THEN
        RAISE EXCEPTION
            'Pós-validação falhou: % coluna(s) ausente(s) ou incompatível(is).',
            colunas_invalidas;
    END IF;

    SELECT COUNT(*)
    INTO colunas_obrigatorias_invalidas
    FROM (
        VALUES
            ('unidade',          'id_portfolio',       'character varying', 100),
            ('user_id_cliente',  'id_user_id_cliente', 'bigint',            NULL),
            ('user_id_cliente',  'id_cliente',         'integer',           NULL),
            ('user_id_cliente',  'user_id',            'character varying', 255),
            ('user_id_cliente',  'id_unidade',         'integer',           NULL)
    ) AS esperado(table_name, column_name, data_type, max_length)
    LEFT JOIN information_schema.columns AS coluna
      ON coluna.table_schema = 'chatbot'
     AND coluna.table_name = esperado.table_name
     AND coluna.column_name = esperado.column_name
    WHERE coluna.column_name IS NULL
       OR coluna.data_type <> esperado.data_type
       OR coluna.character_maximum_length
            IS DISTINCT FROM esperado.max_length
       OR coluna.is_nullable <> 'NO'
       OR (
           esperado.column_name = 'id_user_id_cliente'
           AND (
               coluna.column_default IS NULL
               OR coluna.column_default NOT LIKE 'nextval(%'
           )
       )
       OR (
           esperado.column_name <> 'id_user_id_cliente'
           AND coluna.column_default IS NOT NULL
       );

    IF colunas_obrigatorias_invalidas <> 0 THEN
        RAISE EXCEPTION
            'Pós-validação falhou: % coluna(s) obrigatória(s) incompatível(is).',
            colunas_obrigatorias_invalidas;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('cliente',                'waid_telefone'),
                ('fila_mensagens',         'cliente_telefone'),
                ('historico_mensagens',    'cliente_telefone'),
                ('cliente_bloqueado_meta', 'wa_id_cliente'),
                ('webhook_flood_evento',   'wa_id_cliente')
        ) AS legado(table_name, column_name)
        JOIN information_schema.columns AS coluna
          ON coluna.table_schema = 'chatbot'
         AND coluna.table_name = legado.table_name
         AND coluna.column_name = legado.column_name
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: coluna legada de identidade permaneceu.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_inherits AS heranca
        CROSS JOIN (
            VALUES ('wa_id'), ('user_id'), ('username')
        ) AS esperado(attname)
        JOIN pg_attribute AS coluna_pai
          ON coluna_pai.attrelid = heranca.inhparent
         AND coluna_pai.attname = esperado.attname
         AND coluna_pai.attnum > 0
         AND coluna_pai.attisdropped IS FALSE
        LEFT JOIN pg_attribute AS coluna_filha
          ON coluna_filha.attrelid = heranca.inhrelid
         AND coluna_filha.attname = esperado.attname
         AND coluna_filha.attnum > 0
         AND coluna_filha.attisdropped IS FALSE
        WHERE heranca.inhparent = 'chatbot.historico_mensagens'::REGCLASS
          AND (
              coluna_filha.attname IS NULL
              OR coluna_filha.atttypid <> coluna_pai.atttypid
              OR coluna_filha.atttypmod <> coluna_pai.atttypmod
              OR coluna_filha.attnotnull <> coluna_pai.attnotnull
          )
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: partição de histórico divergente do pai.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM chatbot.unidade
        WHERE NULLIF(BTRIM(id_portfolio), '') IS NULL
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: unidade sem id_portfolio válido.';
    END IF;

    SELECT COUNT(*)
    INTO constraints_obrigatorias
    FROM (
        VALUES
            ('unidade',                 'ck_unidade_id_portfolio_nao_vazio',         'c'),
            ('cliente',                 'cliente_wa_id_key',                         'u'),
            ('cliente',                 'ck_cliente_wa_id_nao_vazio',                'c'),
            ('cliente',                 'ck_cliente_username_nao_vazio',             'c'),
            ('fila_mensagens',          'ck_fila_wa_id_nao_vazio',                   'c'),
            ('fila_mensagens',          'ck_fila_user_id_nao_vazio',                 'c'),
            ('fila_mensagens',          'ck_fila_identidade_meta',                   'c'),
            ('fila_mensagens',          'ck_fila_username_nao_vazio',                'c'),
            ('historico_mensagens',     'ck_historico_wa_id_nao_vazio',              'c'),
            ('historico_mensagens',     'ck_historico_user_id_nao_vazio',            'c'),
            ('historico_mensagens',     'ck_historico_identidade_meta',              'c'),
            ('historico_mensagens',     'ck_historico_username_nao_vazio',           'c'),
            ('conversa',                'ck_conversa_wa_id_nao_vazio',               'c'),
            ('conversa',                'ck_conversa_user_id_nao_vazio',             'c'),
            ('conversa',                'ck_conversa_identidade_meta',               'c'),
            ('conversa',                'ck_conversa_username_nao_vazio',            'c'),
            ('conversa',                'ck_conversa_motivo_encerramento',            'c'),
            ('cliente_bloqueado_meta',  'uq_cliente_bloqueado_meta_wa_id_unidade',   'u'),
            ('cliente_bloqueado_meta',  'ck_bloqueio_wa_id_nao_vazio',               'c'),
            ('cliente_bloqueado_meta',  'ck_bloqueio_user_id_nao_vazio',             'c'),
            ('cliente_bloqueado_meta',  'ck_bloqueio_identidade_meta',               'c'),
            ('cliente_bloqueado_meta',  'ck_bloqueio_username_nao_vazio',            'c'),
            ('webhook_flood_evento',    'ck_flood_wa_id_nao_vazio',                  'c'),
            ('webhook_flood_evento',    'ck_flood_user_id_nao_vazio',                'c'),
            ('webhook_flood_evento',    'ck_flood_identidade_meta',                  'c'),
            ('webhook_flood_evento',    'ck_flood_username_nao_vazio',               'c'),
            ('user_id_cliente',         'user_id_cliente_pkey',                      'p'),
            ('user_id_cliente',         'ck_user_id_cliente_user_id_nao_vazio',      'c'),
            ('user_id_cliente',         'fk_user_id_cliente_cliente',                'f'),
            ('user_id_cliente',         'fk_user_id_cliente_unidade',                'f'),
            ('user_id_cliente',         'uq_user_id_cliente_user_unidade',           'u'),
            ('user_id_cliente',         'uq_user_id_cliente_cliente_unidade',        'u')
    ) AS esperado(table_name, constraint_name, constraint_type)
    JOIN pg_constraint AS constraint_atual
      ON constraint_atual.conrelid = TO_REGCLASS(
          FORMAT('chatbot.%I', esperado.table_name)
      )
     AND constraint_atual.conname = esperado.constraint_name
     AND constraint_atual.contype::TEXT = esperado.constraint_type
     AND constraint_atual.convalidated IS TRUE;

    IF constraints_obrigatorias <> 32 THEN
        RAISE EXCEPTION
            'Pós-validação falhou: esperado 32 constraints do contrato; obtido %.',
            constraints_obrigatorias;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'chatbot.user_id_cliente'::REGCLASS
          AND conname = 'fk_user_id_cliente_cliente'
          AND contype = 'f'
          AND confdeltype = 'r'
          AND convalidated IS TRUE
    ) OR NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'chatbot.user_id_cliente'::REGCLASS
          AND conname = 'fk_user_id_cliente_unidade'
          AND contype = 'f'
          AND confdeltype = 'c'
          AND convalidated IS TRUE
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: ações das FKs de user_id_cliente divergentes.';
    END IF;

    SELECT PG_GET_CONSTRAINTDEF(oid)
    INTO definicao_motivo_final
    FROM pg_constraint
    WHERE conrelid = 'chatbot.conversa'::REGCLASS
      AND conname = 'ck_conversa_motivo_encerramento'
      AND contype = 'c'
      AND convalidated IS TRUE;

    SELECT ARRAY(
        SELECT DISTINCT ocorrencia[1]
        FROM regexp_matches(
            definicao_motivo_final,
            $regex$'([^']+)'$regex$,
            'g'
        ) AS ocorrencia
        ORDER BY ocorrencia[1]
    )
    INTO motivos_finais;

    IF definicao_motivo_final IS NULL
       OR POSITION(
           'MOTIVO_ENCERRAMENTO IS NULL'
           IN UPPER(definicao_motivo_final)
       ) = 0
       OR motivos_finais IS DISTINCT FROM ARRAY[
           'ativou_user_id',
           'foi_agendado',
           'idade_invalida'
       ]::TEXT[]
    THEN
        RAISE EXCEPTION
            'Pós-validação falhou: CHECK final de motivo divergente.';
    END IF;

    SELECT COUNT(*)
    INTO indices_obrigatorios
    FROM pg_indexes
    WHERE schemaname = 'chatbot'
      AND indexname IN (
          'idx_unidade_id_portfolio',
          'idx_fila_wa_unidade_aberta',
          'idx_fila_wa_unidade_conversa_aberta',
          'idx_fila_user_unidade_aberta',
          'idx_fila_user_unidade_conversa_aberta',
          'idx_conversa_wa_unidade',
          'idx_conversa_user_unidade',
          'uq_cliente_bloqueado_meta_wa_id_unidade',
          'uq_cliente_bloqueado_meta_user_id_unidade',
          'uq_cliente_bloqueado_meta_cliente_unidade',
          'idx_webhook_flood_evento_janela',
          'idx_webhook_flood_evento_user_janela',
          'uq_user_id_cliente_user_unidade',
          'uq_user_id_cliente_cliente_unidade',
          'idx_user_id_cliente_id_unidade'
      );

    IF indices_obrigatorios <> 15 THEN
        RAISE EXCEPTION
            'Pós-validação falhou: esperado 15 índices do contrato; obtido %.',
            indices_obrigatorios;
    END IF;

    IF EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('idx_unidade_id_portfolio'),
                ('idx_fila_wa_unidade_aberta'),
                ('idx_fila_wa_unidade_conversa_aberta'),
                ('idx_fila_user_unidade_aberta'),
                ('idx_fila_user_unidade_conversa_aberta'),
                ('idx_conversa_wa_unidade'),
                ('idx_conversa_user_unidade'),
                ('uq_cliente_bloqueado_meta_wa_id_unidade'),
                ('uq_cliente_bloqueado_meta_user_id_unidade'),
                ('uq_cliente_bloqueado_meta_cliente_unidade'),
                ('idx_webhook_flood_evento_janela'),
                ('idx_webhook_flood_evento_user_janela'),
                ('uq_user_id_cliente_user_unidade'),
                ('uq_user_id_cliente_cliente_unidade'),
                ('idx_user_id_cliente_id_unidade')
        ) AS esperado(indexname)
        LEFT JOIN LATERAL (
            SELECT
                indice_estado.indexrelid,
                indice_estado.indisvalid,
                indice_estado.indisready
            FROM pg_class AS indice
            JOIN pg_namespace AS namespace
              ON namespace.oid = indice.relnamespace
             AND namespace.nspname = 'chatbot'
            JOIN pg_index AS indice_estado
              ON indice_estado.indexrelid = indice.oid
            WHERE indice.relname = esperado.indexname
        ) AS estado ON TRUE
        WHERE estado.indexrelid IS NULL
           OR estado.indisvalid IS FALSE
           OR estado.indisready IS FALSE
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: índice obrigatório ausente ou inválido.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM (
            VALUES
                ('idx_unidade_id_portfolio',
                 '(ID_PORTFOLIO)', '', FALSE),
                ('idx_fila_wa_unidade_aberta',
                 '(WA_ID, ID_PHONE_UNIDADE, STATUS, RECEIVED_DATA_HORA, ID_MENSAGEM)',
                 'STATUS', FALSE),
                ('idx_fila_wa_unidade_conversa_aberta',
                 '(WA_ID, ID_PHONE_UNIDADE, ID_CONVERSA, ID_HASH_MSG, ID_MENSAGEM)',
                 'STATUS', FALSE),
                ('idx_fila_user_unidade_aberta',
                 '(USER_ID, ID_PHONE_UNIDADE, STATUS, RECEIVED_DATA_HORA, ID_MENSAGEM)',
                 'USER_ID IS NOT NULL', FALSE),
                ('idx_fila_user_unidade_conversa_aberta',
                 '(USER_ID, ID_PHONE_UNIDADE, ID_CONVERSA, ID_HASH_MSG, ID_MENSAGEM)',
                 'USER_ID IS NOT NULL', FALSE),
                ('idx_conversa_wa_unidade',
                 '(WA_ID, ID_UNIDADE, FINALIZOU_EM DESC)',
                 'WA_ID IS NOT NULL', FALSE),
                ('idx_conversa_user_unidade',
                 '(USER_ID, ID_UNIDADE, FINALIZOU_EM DESC)',
                 'USER_ID IS NOT NULL', FALSE),
                ('uq_cliente_bloqueado_meta_wa_id_unidade',
                 '(WA_ID, ID_UNIDADE)', '', TRUE),
                ('uq_cliente_bloqueado_meta_user_id_unidade',
                 '(USER_ID, ID_UNIDADE)', 'USER_ID IS NOT NULL', TRUE),
                ('uq_cliente_bloqueado_meta_cliente_unidade',
                 '(ID_CLIENTE, ID_UNIDADE)', 'ID_CLIENTE IS NOT NULL', TRUE),
                ('idx_webhook_flood_evento_janela',
                 '(WA_ID, PHONE_ID_UNIDADE, RECEIVED_AT DESC)', '', FALSE),
                ('idx_webhook_flood_evento_user_janela',
                 '(USER_ID, PHONE_ID_UNIDADE, RECEIVED_AT DESC)',
                 'USER_ID IS NOT NULL', FALSE),
                ('uq_user_id_cliente_user_unidade',
                 '(USER_ID, ID_UNIDADE)', '', TRUE),
                ('uq_user_id_cliente_cliente_unidade',
                 '(ID_CLIENTE, ID_UNIDADE)', '', TRUE),
                ('idx_user_id_cliente_id_unidade',
                 '(ID_UNIDADE, ID_CLIENTE)', '', FALSE)
        ) AS esperado(
            indexname,
            chave_esperada,
            predicado_esperado,
            unique_obrigatorio
        )
        LEFT JOIN pg_indexes AS indice
          ON indice.schemaname = 'chatbot'
         AND indice.indexname = esperado.indexname
        WHERE indice.indexname IS NULL
           OR POSITION(
               esperado.chave_esperada IN UPPER(indice.indexdef)
           ) = 0
           OR (
               esperado.predicado_esperado <> ''
               AND POSITION(
                   esperado.predicado_esperado IN UPPER(indice.indexdef)
               ) = 0
           )
           OR (
               esperado.unique_obrigatorio
               AND POSITION('CREATE UNIQUE INDEX' IN UPPER(indice.indexdef)) <> 1
           )
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: definição ou predicado de índice divergente.';
    END IF;

    IF (SELECT COUNT(*) FROM chatbot.user_id_cliente) <> 0 THEN
        RAISE EXCEPTION
            'Pós-validação falhou: user_id_cliente deveria nascer vazia.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM chatbot.fila_mensagens
        WHERE NULLIF(BTRIM(wa_id), '') IS NULL
          AND NULLIF(BTRIM(user_id), '') IS NULL
    ) OR EXISTS (
        SELECT 1
        FROM chatbot.historico_mensagens
        WHERE NULLIF(BTRIM(wa_id), '') IS NULL
          AND NULLIF(BTRIM(user_id), '') IS NULL
    ) OR EXISTS (
        SELECT 1
        FROM chatbot.conversa
        WHERE NULLIF(BTRIM(wa_id), '') IS NULL
          AND NULLIF(BTRIM(user_id), '') IS NULL
    ) OR EXISTS (
        SELECT 1
        FROM chatbot.cliente_bloqueado_meta
        WHERE NULLIF(BTRIM(wa_id), '') IS NULL
          AND NULLIF(BTRIM(user_id), '') IS NULL
    ) OR EXISTS (
        SELECT 1
        FROM chatbot.webhook_flood_evento
        WHERE NULLIF(BTRIM(wa_id), '') IS NULL
          AND NULLIF(BTRIM(user_id), '') IS NULL
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: registro operacional sem identidade.';
    END IF;

    IF EXISTS (
        WITH atual AS (
            SELECT 'cliente' AS tabela, COUNT(*)::BIGINT AS registros
            FROM chatbot.cliente
            UNION ALL
            SELECT 'conversa', COUNT(*) FROM chatbot.conversa
            UNION ALL
            SELECT 'dependente', COUNT(*) FROM chatbot.dependente
            UNION ALL
            SELECT 'fila_mensagens', COUNT(*) FROM chatbot.fila_mensagens
            UNION ALL
            SELECT 'historico_mensagens', COUNT(*)
            FROM chatbot.historico_mensagens
            UNION ALL
            SELECT 'respostas_desafios', COUNT(*)
            FROM chatbot.respostas_desafios
            UNION ALL
            SELECT 'cliente_bloqueado_meta', COUNT(*)
            FROM chatbot.cliente_bloqueado_meta
            UNION ALL
            SELECT 'webhook_flood_evento', COUNT(*)
            FROM chatbot.webhook_flood_evento
            UNION ALL
            SELECT 'funil_envios', COUNT(*) FROM chatbot.funil_envios
        )
        SELECT 1
        FROM pg_temp.migracao_user_id_contagens AS antes
        FULL JOIN atual AS depois USING (tabela)
        WHERE antes.registros IS DISTINCT FROM depois.registros
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: contagem operacional mudou durante a migração.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM pg_temp.migracao_respostas_etapas AS antes
        FULL JOIN chatbot.respostas_desafios AS depois
          ON depois.id_resposta_desafio = antes.id_resposta_desafio
        WHERE antes.id_resposta_desafio IS NULL
           OR depois.id_resposta_desafio IS NULL
           OR depois.id_etapa IS DISTINCT FROM antes.id_etapa + 1
    ) OR EXISTS (
        SELECT 1
        FROM chatbot.respostas_desafios
        WHERE id_etapa NOT BETWEEN 13 AND 18
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: respostas da triagem não foram remapeadas exatamente de 12..17 para 13..18.';
    END IF;

    SELECT COUNT(*)
    INTO etapas_finais_corretas
    FROM chatbot.etapa AS etapa
    JOIN (
        VALUES
            (1,  'Saudação e nome do cliente',                         FALSE, 0,  FALSE),
            (2,  'Compartilhamento oficial do contato',                FALSE, 0,  FALSE),
            (3,  'Destino do atendimento',                             FALSE, 0,  FALSE),
            (4,  'Confirmação do destino do atendimento',              FALSE, 0,  FALSE),
            (5,  'Profissão do cliente',                               FALSE, 0,  FALSE),
            (6,  'Nome do dependente',                                 FALSE, 0,  FALSE),
            (7,  'Idade do aluno',                                     FALSE, 0,  FALSE),
            (8,  'Oferta de aula experimental e avaliação cognitiva', FALSE, 0,  FALSE),
            (9,  'Oferta adiada e Instagram',                          FALSE, 0,  FALSE),
            (10, 'Confirmação de retorno ao atendimento',              FALSE, 0,  FALSE),
            (11, 'Email',                                              FALSE, 0,  FALSE),
            (12, 'Introdução à triagem cognitiva',                     FALSE, 0,  FALSE),
            (13, 'Triagem cognitiva - pergunta 1',                     FALSE, 0,  FALSE),
            (14, 'Triagem cognitiva - pergunta 2',                     FALSE, 0,  FALSE),
            (15, 'Triagem cognitiva - pergunta 3',                     FALSE, 0,  FALSE),
            (16, 'Triagem cognitiva - pergunta 4',                     FALSE, 0,  FALSE),
            (17, 'Triagem cognitiva - pergunta 5',                     FALSE, 0,  FALSE),
            (18, 'Triagem cognitiva - pergunta 6',                     FALSE, 0,  FALSE),
            (19, 'Agendamento após a triagem cognitiva',               FALSE, 0,  TRUE),
            (20, 'Pesquisa de satisfação - nota',                      FALSE, 0,  TRUE),
            (21, 'Pesquisa de satisfação - opção de comentário',       FALSE, 0,  TRUE),
            (22, 'Pesquisa de satisfação - comentário',                FALSE, 0,  TRUE),
            (23, 'Finalização do atendimento',                         TRUE,  30, TRUE)
    ) AS esperado(
        id_etapa,
        nome_etapa,
        encerra_automaticamente,
        bloqueio_dias,
        elegivel_funil
    )
      ON etapa.id_etapa = esperado.id_etapa
     AND etapa.nome_etapa = esperado.nome_etapa
     AND etapa.encerra_automaticamente = esperado.encerra_automaticamente
     AND etapa.bloqueio_dias = esperado.bloqueio_dias
     AND etapa.elegivel_funil = esperado.elegivel_funil;

    SELECT COUNT(*)
    INTO transicoes_finais_corretas
    FROM chatbot.etapa_transicao AS transicao
    JOIN (
        VALUES
            (1,  'nome_cliente_valido_com_wa_id',          3),
            (1,  'nome_cliente_valido_sem_wa_id',          2),
            (2,  'contato_oficial_compartilhado',          3),
            (3,  'destino_atendimento_definido',           4),
            (4,  'destino_atendimento_confirmado',          5),
            (5,  'profissao_dependente_valida',            6),
            (5,  'profissao_titular_valida',               7),
            (6,  'nome_dependente_valido',                 7),
            (7,  'idade_valida',                           8),
            (8,  'oferta_aceita',                         11),
            (8,  'oferta_adiada',                          9),
            (9,  'cliente_retornou',                      10),
            (10, 'retorno_confirmado',                    11),
            (10, 'retorno_adiado',                         9),
            (11, 'email_valido',                          12),
            (12, 'triagem_iniciada',                      13),
            (13, 'triagem_pergunta_1_respondida',         14),
            (14, 'triagem_pergunta_2_respondida',         15),
            (15, 'triagem_pergunta_3_respondida',         16),
            (16, 'triagem_pergunta_4_respondida',         17),
            (17, 'triagem_pergunta_5_respondida',         18),
            (18, 'triagem_pergunta_6_respondida',         19),
            (19, 'agendamento_confirmado',                20),
            (20, 'satisfacao_avaliada',                   21),
            (21, 'comentario_satisfacao_aceito',          22),
            (21, 'comentario_satisfacao_recusado',        23),
            (22, 'comentario_satisfacao_recebido',        23)
    ) AS esperado(id_etapa_origem, evento, id_etapa_destino)
      ON transicao.id_etapa_origem = esperado.id_etapa_origem
     AND transicao.evento = esperado.evento
     AND transicao.id_etapa_destino = esperado.id_etapa_destino;

    IF (SELECT COUNT(*) FROM chatbot.etapa) <> 23
       OR etapas_finais_corretas <> 23
       OR (SELECT MIN(id_etapa) FROM chatbot.etapa) <> 1
       OR (SELECT MAX(id_etapa) FROM chatbot.etapa) <> 23
       OR (SELECT COUNT(*) FROM chatbot.etapa_transicao) <> 27
       OR transicoes_finais_corretas <> 27
    THEN
        RAISE EXCEPTION
            'Pós-validação falhou: conteúdo exato do catálogo/mapa divergente.';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM chatbot.etapa
        WHERE nome_etapa LIKE '__migracao_user_id_%'
    ) THEN
        RAISE EXCEPTION
            'Pós-validação falhou: nome temporário permaneceu.';
    END IF;

    SELECT
        (
            SELECT COUNT(*)
            FROM chatbot.conversa AS c
            LEFT JOIN chatbot.etapa AS e
              ON e.id_etapa = c.id_etapa_atual
            WHERE c.id_etapa_atual IS NOT NULL
              AND e.id_etapa IS NULL
        ) AS conversa,
        (
            SELECT COUNT(*)
            FROM chatbot.historico_mensagens AS h
            LEFT JOIN chatbot.etapa AS e
              ON e.id_etapa = h.id_etapa
            WHERE h.id_etapa IS NOT NULL
              AND e.id_etapa IS NULL
        ) AS historico,
        (
            SELECT COUNT(*)
            FROM chatbot.respostas_desafios AS r
            LEFT JOIN chatbot.etapa AS e
              ON e.id_etapa = r.id_etapa
            WHERE e.id_etapa IS NULL
        ) AS respostas
    INTO referencias_invalidas;

    IF referencias_invalidas.conversa <> 0
       OR referencias_invalidas.historico <> 0
       OR referencias_invalidas.respostas <> 0
    THEN
        RAISE EXCEPTION
            'Pós-validação falhou: referências de etapa inválidas.';
    END IF;

    SELECT p.prosrc
    INTO corpo_dequeue_final
    FROM pg_proc AS p
    WHERE p.oid = TO_REGPROCEDURE('chatbot.dequeue_message()')
      AND p.prokind = 'f'
      AND p.pronargs = 0
      AND p.proretset IS TRUE
      AND p.prorettype = 'record'::REGTYPE
      AND p.proargnames = ARRAY[
          'id_mensagem',
          'wa_id',
          'user_id',
          'username',
          'conteudo_texto',
          'tipo_mensagem',
          'id_phone_unidade',
          'unidade_telefone',
          'received_data_hora',
          'id_hash_msg',
          'retry_count'
      ]::TEXT[]
      AND p.proargmodes = ARRAY[
          't', 't', 't', 't', 't', 't', 't', 't', 't', 't', 't'
      ]::"char"[]
      AND p.proallargtypes = ARRAY[
          'int4'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'text'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'timestamptz'::REGTYPE::OID,
          'varchar'::REGTYPE::OID,
          'int4'::REGTYPE::OID
      ]::OID[];

    IF corpo_dequeue_final IS NULL
       OR POSITION('WITH NEXT_JOB AS' IN UPPER(corpo_dequeue_final)) = 0
       OR POSITION('F.STATUS = ''PENDING''' IN UPPER(corpo_dequeue_final)) = 0
       OR POSITION('F.NEXT_ATTEMPT_AT <= NOW()' IN UPPER(corpo_dequeue_final)) = 0
       OR POSITION('F.STATUS = ''PROCESSING''' IN UPPER(corpo_dequeue_final)) = 0
       OR POSITION('FOR UPDATE SKIP LOCKED' IN UPPER(corpo_dequeue_final)) = 0
       OR POSITION('LIMIT 1' IN UPPER(corpo_dequeue_final)) = 0
       OR POSITION('RETRY_COUNT = F.RETRY_COUNT + 1' IN UPPER(corpo_dequeue_final)) = 0
       OR POSITION('PROCESSING_STARTED_AT = NOW()' IN UPPER(corpo_dequeue_final)) = 0
       OR POSITION('INTERVAL ''2 MINUTES''' IN UPPER(corpo_dequeue_final)) = 0
    THEN
        RAISE EXCEPTION
            'Pós-validação falhou: assinatura ou invariantes da dequeue divergentes.';
    END IF;
END
$pos_validacao$;

COMMIT;
```

Esse comando **não deve ser executado agora**. Antes da futura execução será
comparado ao DDL efetivamente implementado e receberá um SQL de reversão próprio.

## 15. Testes essenciais

### 15.1 Payload e webhook

- cada um dos quatro fixtures é interpretado corretamente;
- WA ID principal vence `from` equivalente;
- user ID principal vence `from_user_id` equivalente;
- campos equivalentes divergentes são descartados com HTTP 200;
- `display_phone_number` nunca vira cliente;
- sem WA ID e user ID: HTTP 200, sem fila;
- username ausente: atendimento normal;
- `contacts` oficial persiste `conteudo_texto='contact_request'`;
- `contacts` manual persiste `conteudo_texto='other'` e não satisfaz a etapa;
- origem em `messages[0].origin` e em `contacts[*].origin` é reconhecida;
- origens ausentes, desconhecidas ou conflitantes persistem `other`;
- um único WA ID explícito de `contacts[*].phones[*]` é aceito;
- múltiplos WA IDs distintos não escolhem o primeiro e não avançam;
- `CONTACT_INFO.json` mantém `user_id` como identidade do item e extrai o número
  do cartão separadamente como `wa_id_compartilhado`;
- teste sintético de `contact_request` com WA ID no envelope, user ID e WA ID no
  cartão ainda congela o item pelo user ID e só usa WA canônico após a prova;
- `wa_id_compartilhado` não vira identidade de denylist, bloqueio, turno, cache
  de cliente ou autocura antes da validação bancária; a única exceção é servir
  como prova efêmera da ponte anti-flood quando vier de `contact_request`
  oficial, autenticado e inequívoco;
- `valida_historico()` expõe `wa_id_compartilhado` somente para o item oficial e
  mantém `contexto_historico['wa_id']` reservado ao WA ID canônico do banco;
- `phone` só é normalizado no último fallback oficial;
- WA ID explícito preserva todos os dígitos, inclusive o nono;
- `phone` brasileiro sem WA ID explícito segue a normalização `55 + DDD + 8`;
- os arrays externos continuam processando somente um evento por POST;
- somente user ID já mapeado é resolvido pelo banco no worker sem criar outro
  cliente provisório;
- evento somente-user-ID já mapeado em etapa posterior é aceito no transporte,
  resolve WA ID canônico no worker e envia exclusivamente a esse WA ID;
- evento em etapa 3 ou posterior cujo vínculo não devolva WA ID canônico falha
  antes de chamar a Meta;
- WA ID + user ID + username registra o vínculo proativamente;
- fora do handoff, denylist, bloqueio e turno recebem somente
  `wa_id_remetente or user_id`; no handoff, o anti-flood também recebe o
  `wa_id_compartilhado` exclusivamente como prova da ponte pendente;
- no handoff, a chave de turno continua sendo a identidade com que o item foi
  enfileirado; não existe consulta dual por aliases;
- flood mantém uma única janela lógica por sujeito oficialmente comprovado e
  unidade, soma os contadores de user ID e WA ID, promove novos incrementos para
  o WA ID canônico e deduplica cada evento pelo WAMID;
- 8 eventos por user ID, o `contact_request` oficial e 6 eventos imediatos por
  WA ID — ainda antes do commit do worker — atingem juntos o limite de 15;
- a mesma sequência sem vínculo oficial mantém contadores separados;
- contato manual, contato ambíguo, unidade diferente e identidades de pessoas
  distintas não criam equivalência;
- conflito na ponte ou indisponibilidade da prova compartilhada devolve HTTP
  503 para reentrega e não bloqueia o cliente na Meta;
- WAMID continua idempotente.

### 15.2 Banco e snapshots

- todas as colunas finais existem com os nomes exatos;
- colunas individuais de snapshot aceitam `NULL`;
- `unidade.id_portfolio` e as três colunas de negócio de `user_id_cliente`
  rejeitam `NULL`; `id_portfolio` e `user_id` também rejeitam vazio;
- `user_id_cliente` possui exatamente duas FKs, com `PROTECT/RESTRICT` para
  cliente e `CASCADE` para unidade;
- `user_id_cliente` rejeita dois clientes para `(user_id, unidade)` e rejeita
  dois user IDs atuais para `(cliente, unidade)`;
- registros operacionais rejeitam ausência simultânea de WA ID e user ID;
- username novo atualiza o valor canônico mutável em `cliente.username`; os
  snapshots seguem a política histórica desta seção;
- backfill de reconciliação preenche somente snapshots `NULL` da conversa
  atual; qualquer valor não nulo permanece intacto;
- payload normal com WA ID + user ID executa imediatamente o mesmo backfill
  `NULL-only`, além de registrar o vínculo;
- snapshots antigos não ligados à conversa reconciliada não mudam;
- ausência posterior de username preserva o canônico;
- pai e partições do histórico permanecem alinhados.

### 15.3 Turno, retry e atomicidade

- `(WA, phone A)` não mistura com `(WA, phone B)`;
- `(user ID, phone A)` não mistura com `(user ID, phone B)`;
- a mesma string usada uma vez como WA ID e outra como user ID não colide por
  causa do namespace tipado;
- o mesmo user ID em unidades diferentes não colide em cache, turno, flood nem
  autocura;
- identidades tipadas diferentes só compartilham a janela anti-flood quando uma
  prova oficial as vincula ao mesmo cliente e à mesma unidade; coincidência de
  texto, username, nome ou horário nunca produz essa união;
- primeiro evento somente-user cria cliente provisório + vínculo + conversa no
  mesmo commit;
- segundo evento somente-user reutiliza o provisório e não duplica cliente;
- cliente canônico que já possui user ID antigo na unidade troca para o novo
  user ID oficialmente provado sem violar nenhuma das duas unicidades;
- evento de contato reencontra primeiro a conversa pelo vínculo, preserva o
  turno e promove WA ID;
- WA ID novo completa o provisório idempotentemente;
- WA ID do cliente canônico reatribui a conversa nova, preservando seu
  `id_conversa`, etapa, fila e histórico;
- conversa canônica antiga ativa é encerrada antes da reatribuição com
  `ativou_user_id`, limpando também `processing/processing_started_at`, sem
  violar `idx_conversa_unica_ativa`;
- conversa adicional inesperada do provisório impede `DELETE`, não é reatribuída
  por aproximação;
- cliente provisório só é excluído depois de `NOT EXISTS` explícito para
  `conversa`, `dependente`, `cliente_bloqueado_meta` e `user_id_cliente`;
- uma referência remanescente em qualquer uma dessas quatro tabelas impede o
  `DELETE`, sem acionar `CASCADE` nem `SET NULL`;
- conflito real entre WA IDs não nulos diferentes não funde clientes;
- testes A/B/C passam sem mudança de verdade;
- ordem de commits/rollbacks é idêntica;
- `bot_resposta_atual()` permanece no mesmo ponto;
- reagendamentos mantêm 30 s, 5 s, 300 s e 2 min conforme o ramo atual;
- retry reconstrói WA ID/user ID/username do banco;
- no retry do mesmo `contact_request`, `identidade_do_item` continua sendo o
  user ID original mesmo depois de `fila_mensagens.wa_id` ter sido comprovado;
- `identidade_do_item` não muda depois de `validar_banco_mensagem()`;
- cache hit de cliente ainda executa a projeção final das identidades no banco;
- reparo de cache stale remove somente `referencia_cache_cliente`, sem remover a
  chave WA ou a chave de user ID de outra unidade;
- falha de FK dentro de `validar_banco_mensagem()` antes de existir
  `contexto_banco` ainda encontra no `estado_ciclo` a referência tipada montada
  antes da validação;
- reconciliação aponta a chave user ID usada para o cliente canônico somente no
  ponto de confirmação posterior ao commit já existente;
- ausência de qualquer chave do contrato bancário falha sem usar o snapshot da
  fila como substituto;
- falha em cada ponto anterior ao commit desfaz toda a reconciliação;
- retry posterior ao commit reencontra o cliente canônico e a mesma conversa;
- `contexto_historico` recebe os três snapshots do banco em envio normal e retry;
- `contexto_envio` não ganha quarto snapshot de WA compartilhado;
- `contexto_envio` preserva os mesmos campos tanto em envio novo quanto no
  retorno idempotente;
- a anexação dos snapshots ocorre antes do retorno antecipado de resposta já
  registrada em `flow_sender()`;
- nenhuma ação terminal ou requeue novo é criada;
- nenhuma mensagem é marcada `sent` antes do ponto atual;
- a ordem interna de `atualizar_banco_com_contexto_final()` permanece histórico
  do bot -> movimento -> turnos sem avanço -> efeitos da transição -> intenção
  de encerramento.

### 15.4 Etapa especial

- WA ID acumulado, inclusive via `user_id_cliente`, pula 1 -> 3;
- somente user ID desconhecido e sem WA acumulado leva 1 -> 2;
- 1 -> 2 e 1 -> 3 usam o mesmo efeito por `id_cliente`, nunca por telefone; a
  reexecução em retry é idempotente e mantém o mesmo nome/resultado;
- o helper de nome registra e valida evento/destino efetivos nas duas arestas,
  sem constante ou mensagem de log hardcoded em 1 -> 2;
- etapa 2 envia `request_contact_info` ao user ID obtido do banco por meio do
  contexto;
- texto, mídia, financeiro e contato manual não avançam;
- dúvida sobre reforço escolar também não avança e tem prioridade sobre o
  financeiro quando os dois classificadores reconhecerem a frase;
- não existe recusa nem confirmação posterior;
- `contact_request` válido fornece WA ID e leva 2 -> 3;
- o efeito final reconhece explicitamente 2 -> 3 sem repetir a
  promoção/reconciliação de identidade;
- tratamentos da etapa 2 não carregam evento e não avançam;
- o sender de “Para quem é o atendimento?” usa o novo WA ID persistido e lido do
  banco, nunca o valor bruto recebido diretamente do payload;
- os resolvers dos envios da etapa 1 e do pedido/repetição da etapa 2 permitem
  explicitamente fallback para user ID quando WA ID ainda não existe;
- `contato_oficial_compartilhado` sem WA ID bancário falha antes de enviar a
  etapa 3;
- etapa 3 em diante sem WA ID falha antes de chamar a Meta;
- username nunca é usado no campo `to`;
- nenhuma conversa sem WA ID chega à etapa 19.

### 15.5 Confirmação, tratamentos e triagem preservados

- a futura etapa 4 aceita somente botão ou texto normalizado `Sim`/`Não`;
- `Sim` mantém o destino escolhido na etapa 3 e `Não` persiste o oposto;
- qualquer outra frase que não tenha sido classificada antes como reforço
  escolar ou financeiro, inclusive tentativas de linguagem natural, repete a
  confirmação como tratamento de contexto;
- titular e dependente produzem `destino_atendimento_confirmado` e sempre seguem
  da confirmação 4 para a profissão 5; somente a profissão bifurca dependente
  para 6 ou titular para 7;
- retry da confirmação exige `status_dependente` booleano persistido, reconstrói
  dele o valor final absoluto e nunca reaplica uma inversão; valor ausente ou de
  outro tipo falha de forma fechada;
- trocar para dependente cria o placeholder necessário de forma idempotente e
  trocar para titular remove somente o placeholder da conversa;
- em etapas com financeiro, a prioridade permanece mídia -> reforço escolar ->
  financeiro -> contexto/regra específica;
- a profissão futura 5 não classifica como dúvida escolar uma declaração
  profissional inequívoca com banca, cursinho, supletivo ou reforço;
- mensagens de tratamento reapresentam a etapa com texto neutro, sem repetir
  aberturas de confirmação ou avanço;
- o catálogo de perguntas usa as futuras etapas 13..18 e seleciona corretamente
  titular adulto, dependente infantil ou dependente adulto;
- a pergunta reconstruída no retry é a mesma variante etária, relida do banco;
- a migração preserva as seis respostas existentes e desloca seus IDs atuais
  12..17 para 13..18 sem colisão.

### 15.6 Arquitetura

- `etapa2_messages.py` contém o texto/builder e não chama Meta nem banco;
- o sender da etapa 2 usa o builder, realiza somente I/O Meta e não escolhe
  evento ou destino;
- o validador da etapa 2 reconhece o contexto oficial antes do validador
  universal de mídia, sem enviar ou consultar banco;
- o resolver produz o evento, consulta o mapa, resolve o destinatário, chama o
  sender e anexa a transição, sem SQL/commit;
- `flow_sender()` roteia resolvers 1..22, não possui resolver 23 e acrescenta os
  snapshots também no retorno idempotente;
- nenhum arquivo de `messages`, sender, validador ou resolver executa SQL ou
  `commit`, e nenhum sender escolhe evento;
- `validar_banco_mensagem()` é o único dono da promoção/reconciliação anterior
  ao sender; `atualizar_banco_com_contexto_final()` ->
  `atualizar_banco_conforme_transicao_de_etapa()` são os donos do movimento e
  dos efeitos finais.

### 15.7 Funil, bloqueio e Admin

- funil recusa lead sem WA ID;
- funil inclui `@username` somente quando existir;
- user ID nunca aparece no funil;
- username ausente não impede um lead que possua WA ID;
- o snapshot do username vem de `conversa.username`, nunca de
  `cliente.username`;
- `alice` e `@alice` são exibidos como exatamente `@alice`, e ausência não cria
  linha vazia nas observações;
- quando presente, username aparece junto ao contato e antes da triagem;
- a etapa 18 futura ainda não é elegível; exatamente 19..23 são elegíveis;
- o Funil consulta exatamente as respostas das futuras etapas 13..18;
- as seis perguntas e respostas aparecem completas e em ordem nas observações;
- os textos reconstruídos no Funil são idênticos aos do catálogo usado pelo
  WhatsApp para a mesma faixa etária;
- os 12 textos canônicos de pergunta permanecem intactos; somente suas chaves
  mudam de 12..17 para 13..18;
- o resumo quantitativo antigo por quantidade de alternativas não reaparece;
- reconciliação não move nem altera `funil_envios` e não cria regra concorrente
  nova no `worker_funil`;
- bloqueio/desbloqueio prioriza WA ID e usa user ID como fallback;
- exclusão Admin preserva a ordem Meta -> banco;
- models/Admin não quebram com WA ID nulo;
- unidade exige e exibe `id_portfolio`;
- Admin de `user_id_cliente` é somente leitura.

## 16. Sequência de deploy futura

1. congelar e commitar a baseline definitiva posterior à V1.0.5;
2. regenerar o apêndice de código completo deste plano;
3. implementar em branch separada;
4. executar testes unitários e de integração;
5. capturar payloads reais em ambiente de teste;
6. validar PyWa/Graph v26.0;
7. gerar e revisar SQL final e SQL de reversão;
8. garantir fila, conversa processing e funil sem trabalho aberto;
9. parar webhook, flow worker e funil worker;
10. executar SQL;
11. atualizar código e dependências;
12. subir webhook e executar smoke;
13. subir flow worker e funil worker;
14. verificar logs, fila, transições e funil.

## 17. Gates finais

O plano só poderá ser aplicado se:

- não existir `telefone_informado` nem `username_informado`;
- os nomes das colunas forem exatamente os da seção 5;
- `id_portfolio` estiver escrito corretamente, obrigatório e preenchido em toda
  unidade;
- `user_id_cliente` possuir PK técnica, duas unicidades, FKs e CHECK definidos
  neste plano;
- WA ID explícito nunca sofrer alteração de dígitos;
- `phone` só for fallback de `contact_request` oficial;
- `wa_id_remetente`, `wa_id_compartilhado` e `wa_id_canonico` permanecerem
  separados até a validação bancária;
- o validador da etapa 2 receber `wa_id_compartilhado` separado e nunca usar o
  WA ID canônico como prova da origem do payload;
- username nunca for identidade técnica;
- WA ID for obrigatório para chegar ao funil;
- somente a etapa especial 2 for adicionada sobre a baseline V1.0.5;
- catálogo tiver 23 etapas e mapa 27 transições;
- somente etapa 23 encerrar e bloquear por 30 dias;
- etapa 23 não tiver resolver;
- a confirmação futura 4 continuar aceitando exclusivamente `Sim`/`Não` e
  persistir o valor final absoluto de forma idempotente, sempre avançar para a
  profissão futura 5 e exigir `status_dependente` booleano no replay;
- a profissão futura 5 conservar seus validadores contextuais para não barrar
  vínculos profissionais inequívocos com serviços escolares e ser a única
  etapa que bifurca dependente para 6 ou titular para 7;
- contato oficial válido ser reconhecido antes dos tratamentos da etapa 2 e,
  nas entradas comuns, a prioridade permanecer mídia -> reforço -> financeiro
  -> contexto;
- toda retomada de tratamento ser semanticamente neutra e preservar os
  componentes da etapa;
- o catálogo compartilhado de triagem usar 13..18 e manter as variantes por
  idade e pessoa atendida;
- o Funil exibir as seis perguntas/respostas ordenadas, nunca o resumo por
  quantidade, e acrescentar username apenas quando existir;
- nenhum sender usar username;
- nenhum sender usar user ID quando WA ID lido do banco existir;
- somente os resolvers dos envios da etapa 1 e do pedido/repetição de
  compartilhamento da etapa 2 habilitarem explicitamente o fallback para user
  ID e passarem o escalar ao sender;
- a resposta `contato_oficial_compartilhado` e a etapa 3 em diante exigirem WA
  ID antes de chamar a Meta;
- `contexto_historico` receber os identificadores do banco e
  `contexto_envio` refletir os mesmos snapshots em todos os caminhos;
- a projeção bancária final ocorrer mesmo em cache hit e não possuir fallback
  silencioso para fila ou payload;
- o item de handoff conservar a mesma chave e consulta de turno, sem busca dual
  por aliases;
- `identidade_do_item` permanecer tipada e imutável durante turno, logs, retry,
  finalização e autocura do item;
- cache por WA ID conservar escopo global e cache por user ID incluir tipo e
  unidade, com a autocura removendo somente a referência efetivamente usada;
- evento inbound somente-user-ID continuar processável depois da etapa 2, mas
  nenhum envio dessa etapa em diante ocorrer sem WA ID canônico do banco;
- primeiro evento somente-user criar vínculo antes da conversa seguinte;
- payload conjunto criar/atualizar vínculo imediatamente;
- troca oficialmente provada de user ID na mesma unidade consolidar primeiro a
  linha provisória e manter uma única linha canônica;
- conversa canônica ativa ser encerrada antes de reatribuir a nova;
- nenhuma exclusão de provisório depender de `ON DELETE CASCADE` ou
  `ON DELETE SET NULL`, e os quatro gates explícitos de `conversa`, `dependente`,
  `cliente_bloqueado_meta` e `user_id_cliente` retornarem zero;
- reconciliação não alterar `funil_envios`, não criar bypass de bloqueio e não
  consolidar bloqueios como efeito lateral;
- não existir requeue ou retorno terminal novo no `flow_worker`;
- nenhuma função SQL de lock/unlock tiver seu algoritmo alterado;
- `dequeue_message()` mantiver seu CTE e comportamento;
- commits, rollbacks, retries, locks, turnos e autocura permanecerem nos mesmos
  pontos;
- `atualizar_banco_com_contexto_final()` preservar sua ordem interna atual e
  continuar chamando `atualizar_banco_conforme_transicao_de_etapa()` como único
  dono dos efeitos finais;
- 1 -> 2 e 1 -> 3 reutilizarem o mesmo efeito de persistência do nome por
  `id_cliente`, usando evento/destino efetivos e resultado idempotente, e 2 -> 3
  reconhecer o evento sem duplicar a reconciliação;
- mensagens, senders, validadores, resolvers e `flow_sender()` respeitarem as
  fronteiras da seção 7.5, sem SQL/commit fora das camadas transacionais;
- `bot_resposta_atual()` e reagendamentos permanecerem intocados;
- a espera de fila vazia permanecer em 1,5 segundo;
- testes com os quatro fixtures e payloads reais passarem;
- SQL de migração não apagar clientes, conversas, fila ou histórico;
- em runtime, somente cliente estritamente provisório e sem referências ser
  excluído depois da reatribuição canônica comprovada.

## 18. Riscos residuais documentados

1. Os fixtures ainda não provam o formato exato que chegará em produção.
2. Um mesmo usuário privado pode gerar um provisório em cada unidade ainda não
   vinculada até fornecer WA ID; após a prova, `user_id_cliente` impede repetição
   naquela unidade. Username não pode ser usado para uni-los.
3. Alternância anômala entre um evento somente-WA e outro somente-user-ID sem
   payload conjunto, vínculo já salvo ou `contact_request` não pode ser
   reconciliada por aproximação.
4. A janela já conhecida Meta -> banco continua existindo: envio confirmado e
   queda antes da persistência pode duplicar resposta em retry. Esta feature não
   amplia nem resolve esse problema.
5. Uma falha durante a promoção user ID -> WA ID segue rollback/retry/autocura
   atuais. A idempotência do vínculo evita repetir efeitos após o commit.
6. Um conflito realmente contraditório — user ID já ligado a um cliente com WA
   ID não nulo diferente do WA oficial atual — não é fundido automaticamente e
   exige investigação. Esse caso é diferente do provisório com WA ID nulo.
7. A segurança aqui assume o requisito operacional atual de exatamente um
   processo de `flow_worker`. Executar dois flow workers exige nova revisão de
   fencing/posse e não é autorizado por este plano.

O antigo reset da janela anti-flood na promoção `user_id` -> `wa_id` não é mais
um risco aceito. A implementação prática deve somar as duas rajadas como uma só
sempre que a associação estiver oficialmente comprovada, inclusive na ponte
pré-commit criada pelo compartilhamento oficial do contato.

## 19. Veredito

Com estes limites, `user_id` entra como fallback de destinatário e identidade de
negócio somente nas etapas iniciais e como vínculo canônico por
cliente/unidade. No transporte inbound, ele continua aceito em qualquer etapa
quando for o único identificador entregue pela Meta; o worker então exige o WA
ID canônico do banco antes de qualquer envio posterior. Username entra apenas
como snapshot e informação adicional opcional no Funil. WA ID continua sendo o
destinatário prioritário, torna-se obrigatório depois do compartilhamento e
permanece obrigatório para o Funil.

A lógica transacional central não é redesenhada: pontos de commit, rollback,
retry, dequeue, turno, lock da conversa, `bot_resposta_atual()` e `sent`
continuam nos mesmos lugares. A reconciliação executa somente os efeitos de dados
aprovados usando a validação e o cursor já existentes, sem novo lock, retorno de
ciclo, requeue ou ramificação do `flow_worker`.

O anti-flood também preserva a continuidade de identidade: quando a prova
oficial demonstrar que `user_id` e `wa_id` pertencem ao mesmo cliente na mesma
unidade, as rajadas dos dois identificadores compõem uma única janela de 15
WAMIDs distintos em 5 segundos. A ponte pendente protege inclusive a troca
imediata anterior ao commit do worker; depois dele, o vínculo persistido confirma
a associação. WAMIDs repetidos contam uma vez, e qualquer conflito ou ausência
de prova segura gera reentrega por HTTP 503, não união ou bloqueio presumido.

O desenho fecha o caso normal de privacidade sem permitir dois `id_cliente` para
a mesma pessoa depois da prova oficial. O handoff user ID -> WA ID, a conversa
canônica anterior, o transporte pelos contextos e o fallback limitado do sender
exigem os testes integrados listados antes de qualquer deploy.

O único risco funcional conhecido e deliberadamente aceito continua sendo a
janela rara entre o envio confirmado pela Meta e sua persistência final no banco,
na qual um retry pode duplicar a resposta externa. A continuidade anti-flood não
acrescenta um segundo risco aceito e elimina o reset de janela que a versão
anterior deste plano tolerava.

Sobre essa identidade nova, o comportamento funcional da V1.0.5 permanece
reconhecível: confirmação binária, tratamentos atuais, triagem por faixa etária,
perguntas e respostas detalhadas no Funil e terminalidade de 30 dias são apenas
renumerados, nunca redesenhados.
