# Regras de negócio do Chatbot - V1

## Finalidade

Este documento é a fonte de verdade para interpretar o comportamento do sistema.
Antes de classificar algo como bug ou alterar o worker, webhook, fila, histórico,
conversa, cache ou banco de dados, estas regras devem ser consultadas.

Uma proteção que aparentemente descarta, bloqueia ou repete um processamento pode
ser uma decisão deliberada da V1. Alterar uma dessas regras representa uma mudança
de produto, e não apenas uma refatoração técnica.

## Definições

- **Cliente:** identificado por `wa_id` ou `cliente_telefone`.
- **Unidade:** identificada por `phone_number_id` ou `id_phone_unidade`.
- **Turno:** interação do par `(cliente_telefone, id_phone_unidade)` que aguarda
  uma resposta do bot.
- **Mensagem aceita:** mensagem que passou pelas validações do webhook e foi
  persistida em `chatbot.fila_mensagens`.
- **Mensagem respondida:** mensagem da fila que possui histórico do bot com
  `status_envio = 'sent'`, vinculado ao seu `id_mensagem_fila` e ao hash da
  mensagem original do cliente.
- **Fonte de verdade:** dado persistido no PostgreSQL. O Redis acelera consultas,
  mas não substitui o banco de dados como fonte definitiva.

## 1. Um turno por vez

Para cada par `(cliente_telefone, id_phone_unidade)`, a V1 deve manter no máximo
uma mensagem aberta ainda sem resposta própria do bot. A decisão não depende
somente de `fila_mensagens.status`; ela combina filas abertas com a resposta do
bot especificamente vinculada a cada mensagem.

- A prioridade é determinada exclusivamente pela ordem de chegada, e não pelo
  tamanho, conteúdo ou aparente importância da mensagem.
- A primeira mensagem válida será persistida na fila.
- Enquanto essa primeira mensagem estiver `pending` ou `processing` e ainda não
  possuir sua própria resposta persistida do bot, qualquer mensagem posterior do
  mesmo cliente para a mesma unidade será descartada pelo webhook.
- A mensagem descartada não será inserida na fila nem no histórico. Para o banco,
  ela nunca existiu.
- Quando todas as filas `pending` ou `processing` já possuírem sua própria
  resposta do bot, o webhook poderá aceitar a primeira mensagem do próximo turno,
  mesmo que a limpeza da fila anterior ainda não tenha chegado ao commit de
  `fila_mensagens.status = 'sent'`.
- A decisão é serializada por `pg_advisory_xact_lock`, utilizando unidade e
  cliente como chaves.

Exemplo de comportamento esperado:

```text
cliente: oi
cliente: olá, quero solicitar determinada coisa
```

Nesse exemplo, `oi` chegou primeiro e é a única mensagem válida do turno. O bot
deverá responder somente a `oi`. A mensagem `olá, quero solicitar determinada
coisa` será descartada no webhook e não aparecerá na fila nem no histórico.

O objetivo não é escolher a mensagem mais completa ou mais útil. O objetivo é
garantir uma única entrada por turno e impedir que várias mensagens enviadas
antes da resposta do bot sejam interpretadas como etapas independentes.

### 1.1. Por que `fila_mensagens.status = 'sent'` não é a única fonte da decisão

`sent` continua sendo o estado terminal que confirma a conclusão administrativa
da fila. Porém, ele não é a única prova de que o turno funcional foi respondido.
A prova mais importante para recuperação é o histórico do bot vinculado à
mensagem específica por:

```text
id_conversa
id_mensagem_fila
id_hash_cliente_origem
```

Se a Meta confirmou o envio, o histórico do bot foi persistido e
`last_message_from` foi atualizado para `bot`, o cliente já recebeu a resposta.
O worker ainda pode cair antes do commit separado que altera a fila para `sent`.
Utilizar somente o status da fila faria o webhook descartar a resposta seguinte
do cliente durante essa janela, embora ela já pertença legitimamente ao próximo
turno.

O webhook atual usa o histórico específico do bot como prova de resposta. Ele não
libera uma mensagem apenas porque o `last_message_from` geral da conversa está
como `bot`; cada fila aberta precisa possuir sua própria resposta correspondente.

### 1.2. Recuperação detalhada entre resposta do bot e `sent`

#### Etapa 1 - A foi respondida, mas o worker caiu

```text
Fila A: processing
Histórico do cliente A: existe
Histórico do bot A: existe
last_message_from: bot
Lock da conversa: ocupado
```

O worker cai antes de marcar A como `sent`. A resposta já chegou ao WhatsApp do
cliente, mas A permanece `processing` por aproximadamente 2 minutos.

#### Etapa 2 - o cliente envia B

O webhook encontra A aberta, mas também encontra a resposta do bot vinculada
especificamente a A. B é a primeira mensagem do próximo turno e pode entrar:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 3 - outro worker seleciona B imediatamente

Se o lock da conversa ainda pertencer ao worker que caiu:

```text
tentar_lock_conversa(B) => False
```

B permanece `processing`. A recusa do lock não exclui B e não a trata como erro
de processamento.

```text
Fila A: processing, respondida
Fila B: processing, sem resposta
```

#### Etapa 4 - o cliente envia C

O webhook examina individualmente todas as filas abertas:

| Fila | Status | Resposta própria do bot |
|---|---|---|
| A | `processing` | Sim |
| B | `processing` | Não |

Como B ainda não possui resposta própria:

```text
todas_abertas_respondidas = False
```

C é descartada e nunca entra no banco. O `last_message_from = 'bot'` deixado por
A não libera C, porque não existe histórico do bot vinculado especificamente a B.

#### Etapa 5 - B adquire o lock antes da recuperação de A

Se o lock antigo já tiver expirado, B poderá adquiri-lo. Em seguida,
`reagendar_se_houver_mensagem_anterior()` encontrará A, que é mais antiga e ainda
está aberta.

B será devolvida para `pending` por 30 segundos, e o retry utilizado para essa
espera será compensado:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

C e quaisquer mensagens posteriores continuarão bloqueadas por B.

#### Etapa 6 - A retorna após o timeout

Depois de aproximadamente 2 minutos:

1. A fica elegível novamente;
2. o lock antigo já expirou após 110 segundos;
3. outro worker adquire o lock;
4. encontra o histórico do bot vinculado a A;
5. não envia uma resposta duplicada;
6. marca A como `sent`;
7. libera o lock.

```text
Fila A: sent
Fila B: pending
```

#### Etapa 7 - B é processada

B adquire o lock, não encontra mensagem anterior aberta e segue normalmente.
Enquanto B não possuir sua própria resposta do bot, qualquer C será descartada.

Depois que a resposta de B for persistida, a primeira mensagem do próximo turno
poderá entrar, inclusive na pequena janela anterior ao commit de `sent` de B.

### 1.3. Limite prático de mensagens abertas

Na recuperação descrita, o sistema poderá manter temporariamente:

```text
1 mensagem antiga respondida, mas ainda processing
+
1 mensagem nova sem resposta
```

Isso não cria uma sequência ilimitada. Assim que B entra sem resposta própria,
C, D, E e todas as mensagens seguintes são descartadas pelo webhook. O advisory
lock do turno também impede que B e C sejam aceitas simultaneamente por uma
corrida entre requisições.

Implementação principal:

- `core/repositories/turno_cliente.py`
- `callback/webhook/services/populating_fila_mensagens.py`

## 2. Idempotência na entrada do webhook

- `fila_mensagens.id_hash_msg` é único.
- A repetição do mesmo evento pela Meta não deve criar outra linha na fila.
- `ON CONFLICT DO NOTHING` é o comportamento esperado para o mesmo
  `id_hash_msg`.
- Uma mensagem nova possui outro hash e continua sujeita à regra de turno.

Ignorar um webhook duplicado não é bug.

## 3. Primeira mensagem do turno

A primeira mensagem válida deverá ser persistida na fila quando não existir outra
mensagem aberta sem resposta para o mesmo cliente e unidade.

É considerado bug quando a primeira mensagem, ou a única mensagem enviada no
turno, é ignorada sem que alguma regra explícita deste documento seja aplicável.

## 4. Estados e tentativas da fila

Estados utilizados:

- `pending`: aguardando processamento.
- `processing`: reservada por um worker.
- `sent`: processamento e resposta concluídos.
- `failed`: permitido pelo schema, mas não é o destino utilizado atualmente
  quando o limite de tentativas é atingido.

Regras da V1:

- O dequeue altera a mensagem para `processing` e incrementa `retry_count`.
- Uma mensagem `processing` abandonada poderá ser retomada depois de 2 minutos.
- Erros tratados reagendam a mensagem para 2 minutos depois, enquanto ainda
  houver tentativa disponível.
- O limite é de 3 tentativas de processamento.
- Ao identificar `retry_count >= 3`, a mensagem é excluída.
- Não existe uma quarta tentativa.

A exclusão ao atingir o limite de 3 tentativas é uma regra de negócio confirmada
da V1, e não um bug. Alterar esse comportamento para `failed`, dead-letter ou um
número maior de tentativas exige uma nova decisão de produto.

Implementação principal:

- `core/database/deploy/bank_script.py`, função `chatbot.dequeue_message()`
- `workers/tratamento_erros_externos/expection_process.py`
- `core/repositories/updates.py`
- `core/repositories/deletes.py`

## 5. Ordenação e exclusão mútua

- Uma conversa deve ser processada por apenas um worker por vez.
- O lock da conversa poderá ser retomado se estiver abandonado por mais de 110
  segundos.
- `lock_version` impede que um worker antigo libere o lock adquirido por um
  worker mais novo.
- Uma mensagem não poderá ultrapassar outra mensagem anterior ainda aberta na
  mesma conversa.
- A ordem utiliza `received_data_hora` e, em caso de empate, `id_mensagem`.
- Uma mensagem posterior que encontrar outra anterior aberta será reagendada sem
  consumir uma tentativa de erro.

Implementação principal:

- `core/database/deploy/bank_script.py`, funções `lock_conversa()` e
  `unlock_conversa()`
- `core/repositories/querys.py`
- `workers/worker_flow/suport_functions.py`

## 6. Conversa ativa e bloqueio por 30 dias

- Poderá existir somente uma conversa ativa para o mesmo cliente e unidade.
- Essa garantia é protegida pelo índice parcial `idx_conversa_unica_ativa`.
- Uma conversa finalizada na etapa 7 permanecerá bloqueada por 30 dias.
- Durante esse período, novas mensagens para a mesma unidade não iniciarão outro
  atendimento.
- Depois dos 30 dias, o cliente poderá iniciar uma nova conversa com a mesma
  unidade.

Implementação principal:

- `core/database/deploy/bank_script.py`
- `core/repositories/querys.py`
- `workers/worker_flow/valida_banco.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`

## 7. Histórico da mensagem do cliente

Depois que uma mensagem da fila for aceita pelo worker:

- Ela será registrada no histórico como `quem_enviou = 'cliente'`.
- Sua identificação lógica utilizará conversa, `id_mensagem_fila` e
  `id_hash_msg`.
- Durante um retry, o registro existente deverá ser reutilizado.
- A etapa persistida no histórico deverá ser reutilizada; o retry não poderá
  reinterpretar a mensagem em outra etapa.
- `last_message_from` deverá permanecer como `cliente` enquanto não existir uma
  resposta do bot persistida para aquela mensagem.
- `last_interaction_at` deverá utilizar o horário persistido da mensagem, e não o
  horário em que o retry ocorreu.

## 8. Histórico e idempotência da resposta do bot

A resposta do bot é vinculada à mensagem original por:

- `id_conversa`;
- `id_mensagem_fila`;
- `id_hash_cliente_origem`.

Se `resposta_bot_para_mensagem_atual` já existir:

- a Meta não deverá ser chamada novamente;
- o histórico do bot não deverá ser duplicado;
- o contexto da conversa deverá ser reparado a partir dos dados persistidos;
- `last_message_from` deverá terminar como `bot`;
- a fila poderá seguir para `sent`.

As proteções `if resposta_bot_atual`, presentes nos fluxos normais e de
tratamento, são regras essenciais de idempotência da V1.

Implementação principal:

- `workers/worker_flow/valida_historico.py`
- `workers/worker_flow/response_flow/flow_sender.py`
- `workers/worker_flow/response_flow/flow_treat_context.py`
- `workers/worker_flow/response_flow/flow_treat_unsupported_type.py`
- `workers/worker_flow/suport_functions.py`

## 9. Semântica de `last_message_from`

- Mensagem do cliente persistida e ainda sem resposta: `cliente`.
- Resposta do bot persistida: `bot`.
- Retry sem resposta do bot mantém ou repara o campo para `cliente`.
- Retry com resposta do bot existente mantém ou repara o campo para `bot`.
- O campo representa o último lado com mensagem persistida para o estado atual;
  ele não é apenas uma marcação de que a conversa já foi iniciada.

## 10. Etapas da conversa

- Uma resposta normal do bot poderá manter a etapa ou avançar no máximo uma
  etapa.
- A etapa nunca poderá retroceder.
- A etapa nunca poderá saltar mais de uma posição.
- A atualização utilizará o estado persistido e será protegida no `UPDATE` da
  conversa.
- Um retry com resposta do bot existente reutilizará a etapa do histórico do
  bot.
- Tratamentos que apenas orientam o cliente poderão responder sem avançar a
  etapa.

Retrocesso ou salto de etapa é bug, salvo se uma nova regra de produto for
documentada.

## 11. Tipos de mensagem na V1

- `text` e `interactive` seguem o fluxo normal de validação.
- Mídias e anexos não são respostas suportadas pelo fluxo normal da V1.
- Uma mídia recebida deverá ser registrada no histórico.
- O bot enviará uma orientação para o cliente continuar por texto ou botão.
- Essa orientação não avançará a etapa, mas alterará `last_message_from` para
  `bot` depois de ser persistida.

Desconsiderar o conteúdo da mídia para fins de avanço de etapa não é bug.

## 12. Flood, payload e assinatura

- A regra atual de rajada curta considera 15 eventos em 5 segundos.
- Redis é a primeira fonte de avaliação de flood.
- Banco e memória funcionam como fallbacks previstos.
- Um cliente identificado como flood poderá ser bloqueado na Meta e não deverá
  ser enfileirado.
- Conversas explicitamente bloqueadas também não serão enfileiradas.
- Payload acima de `WEBHOOK_MAX_BODY_BYTES` deverá ser rejeitado com HTTP 413
  antes de parse, flood, cache ou banco.
- Assinatura Meta inválida deverá ser rejeitada com HTTP 403 antes de qualquer
  confiança no conteúdo do payload.

Payload grande e assinatura inválida bloqueiam a requisição na entrada, mas não
devem bloquear diretamente um cliente na Meta. Um atacante poderia montar um
payload inválido utilizando o `wa_id` de um cliente real. Bloquear esse número
atingiria a vítima informada pelo atacante, e não necessariamente a origem da
requisição.

Portanto, HTTP 413 ou 403 sem bloqueio Meta é o comportamento final e esperado da
V1, e não uma implementação parcial.

Implementação principal:

- `callback/webhook/services/post_flow.py`
- `callback/webhook/services/flood_guard.py`
- `core/cache/runtime/cache_flood_redis.py`
- `core/cache/cache_flood_memoria.py`

## 13. Commits e estados intermediários do worker

O worker possui checkpoints duráveis separados:

1. claim da fila como `processing`;
2. cliente, conversa e vínculo da mensagem;
3. lock da conversa;
4. histórico do cliente e `last_message_from = 'cliente'`;
5. histórico do bot, etapa e `last_message_from = 'bot'`;
6. fila marcada como `sent`;
7. unlock da conversa.

Uma queda entre checkpoints normalmente deixa informações suficientes para que
o timeout e o retry reconheçam o estado intermediário. O objetivo é evitar a
perda da mensagem aceita, mesmo admitindo duplicidade rara.

As decisões de `commit`, `rollback` e `close` da conexão do ciclo pertencem ao
`flow_worker.py`. Repositórios e módulos internos executam operações utilizando a
conexão ou o cursor recebido, sem assumir a propriedade da transação.

## 14. Duplicidade aceita como exceção rara

O sistema busca entrega pelo menos uma vez, e não exatamente uma vez.

A principal janela aceita de duplicidade é:

```text
Meta confirmou ou efetivou o envio
        -> worker caiu ou perdeu a confirmação
        -> histórico do bot ainda não foi confirmado no banco
```

Nesse intervalo, o retry não encontra uma resposta persistida e poderá enviar
novamente. Depois do commit do histórico do bot, o retry deverá reconhecer a
resposta e não repetir o envio.

Duplicidade frequente, determinística ou ocorrida depois de a resposta do bot já
estar persistida é bug. Duplicidade excepcional na janela externa entre Meta e
banco é um trade-off conhecido e aceito na V1.

## 15. O que é bug na V1

São bugs, entre outros:

- a primeira ou única mensagem válida do turno ser ignorada sem uma regra
  aplicável;
- uma mensagem aceita desaparecer antes de concluir a política prevista de
  tentativas;
- o bot enviar novamente quando a resposta atual já estiver persistida;
- `last_message_from` permanecer como `cliente` quando a resposta atual do bot já
  estiver persistida, ou como `bot` quando ainda não existir resposta persistida;
- uma etapa retroceder ou saltar mais de uma posição;
- duas mensagens do mesmo turno avançarem a conversa como se fossem turnos
  independentes;
- uma mensagem posterior ultrapassar outra anterior ainda aberta na conversa;
- uma falha prevista encerrar permanentemente o worker sem tentativa de
  recuperação.

## 16. O que não é bug na V1

Não são bugs:

- ignorar qualquer segunda mensagem quando a primeira mensagem do mesmo cliente e
  unidade ainda estiver aberta e sem resposta própria do bot;
- ignorar a repetição do mesmo webhook ou `id_hash_msg`;
- reutilizar histórico existente durante um retry;
- responder a uma mídia com orientação sem avançar a etapa;
- excluir a mensagem ao atingir a terceira tentativa;
- aguardar os timeouts da fila ou do lock antes de um novo processamento;
- uma duplicidade extremamente rara na janela entre Meta e commit do bot;
- rejeitar payload grande ou assinatura inválida sem bloquear o número informado
  na Meta.

## 17. Trade-off pendente: falha ao enfileirar

Comportamento atual:

- se a transação de inserção na fila falhar, será executado rollback;
- o webhook registrará `insert_exception`;
- mesmo assim, a resposta HTTP final para a Meta será 200;
- portanto, a mensagem poderá não estar persistida, embora a Meta possa
  considerá-la entregue.

Existem alternativas técnicas, mas cada uma altera o contrato operacional:

- retornar HTTP 5xx para solicitar uma nova entrega da Meta;
- persistir primeiro em uma inbox ou fila durável alternativa;
- manter HTTP 200 e aceitar o risco atual.

Essa decisão ainda não foi confirmada como regra definitiva da V1. O status HTTP
e a infraestrutura não devem ser alterados sem uma decisão explícita. Como o
objetivo declarado é não ignorar a primeira mensagem válida, este ponto deverá
permanecer registrado como risco conhecido.

## 18. Cache, fallback e autocura

Tabelas e consultas de baixa volatilidade ou alta frequência devem priorizar
Redis e possuir fallback para a fonte de verdade no banco quando o cache estiver
indisponível, inválido ou inconsistente de maneira detectável.

Princípios obrigatórios:

- Redis é um acelerador; o banco continua sendo a fonte de verdade.
- Uma falha do Redis não deverá interromper o fluxo quando houver fallback seguro
  no banco.
- Depois de consultar o banco por fallback, o sistema deverá tentar reparar o
  Redis com os dados atuais.
- Uma falha na tentativa de reparo do cache não deverá apagar dados válidos do
  banco.
- Quando um valor stale causar erro de integridade, ele deverá ser removido ou o
  cache completo deverá ser recarregado para que o próximo retry consulte o banco
  e se recupere.
- Operações administrativas que exijam banco e cache coerentes deverão ser
  bloqueadas se o Redis não puder ser validado ou atualizado.

### 18.1. Cache de unidades

- Utiliza hash Redis, quantidade esperada e versão mantida em
  `chatbot.cache_controle`.
- Webhook e worker conferem periodicamente a versão do Redis contra a versão do
  banco e recarregam o cache quando encontram divergência.
- O Django Admin incrementa a versão e recria o cache depois de salvar ou excluir
  uma unidade.
- Se o Redis falhar, webhook e worker utilizam fallback no banco e tentam
  recarregar o cache.
- Se um `id_unidade` stale causar violação de FK no worker, o cache de unidades é
  recarregado antes do retry.

### 18.2. Cache de clientes

- Relaciona `wa_id` ao `id_cliente` e possui TTL.
- Miss, valor inválido ou Redis indisponível levam a consulta ao banco.
- Um cliente criado ou encontrado no banco será salvo no cache somente depois do
  commit que confirmar sua existência.
- Se um `id_cliente` stale causar violação de FK, a chave será removida para que o
  retry reconstrua o valor correto pelo banco.

### 18.3. Cache de conversas bloqueadas

- O bloqueio de 30 dias utiliza Redis com TTL calculado a partir de
  `finalizou_em`.
- Quando o Redis falha, o banco é consultado e o cache é criado ou removido para
  refletir o resultado persistido.
- Quando o worker encontra uma conversa bloqueada que ainda não estava no cache,
  ele registra a chave com o TTL restante e remove a mensagem da fila.
- Depois de expirado o período, a chave não deverá mais bloquear o cliente.
- Esse cache possui mecanismo próprio de reparo e não deverá ser incluído nos
  reparos de FK de cliente e unidade do `flow_worker.py`.

### 18.4. Escopo da autocura

- A autocura cobre falhas detectadas, versão divergente de unidades e erros FK
  de cliente ou unidade.
- Em produção, alterações manuais diretamente no banco são proibidas. Dados que
  afetam cache devem ser modificados pelos fluxos oficiais da aplicação ou pelo
  Django Admin.
- Edições manuais no banco são permitidas somente em desenvolvimento. Nesse
  ambiente, atrasos de sincronização poderão ser corrigidos pelo reset de cache
  destinado a DEV.
- O sistema não precisa comparar banco e Redis em toda leitura para detectar uma
  edição manual que viole o contrato de produção.

Dentro desse contrato, a autocura implementada atende às regras da V1. Suporte a
edições manuais silenciosas em produção não é requisito.

Implementação principal:

- `core/cache/cache_unidade.py`
- `core/cache/runtime/cache_cliente.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`
- `core/repositories/cache_control.py`
- `workers/worker_flow/suport_functions.py`

## 19. Regras do Django Admin

O Django Admin é uma superfície operacional controlada, e não uma forma livre de
editar as tabelas do fluxo.

### 19.1. Tabelas somente para visualização

Cliente, dependente, etapa, conversa, fila, histórico, respostas de desafio,
eventos de flood e controle de cache utilizam administração somente leitura:

- não permitem adicionar;
- não permitem alterar;
- não permitem excluir;
- exibem os campos somente para consulta operacional.

### 19.2. Clientes bloqueados na Meta

- O administrador não poderá criar manualmente um bloqueio.
- O bloqueio será decidido pelo sistema e executado diretamente na Meta.
- Isso também evita tentar bloquear pessoas que nunca iniciaram contato, operação
  que a Meta não permite nesse fluxo.
- O administrador poderá somente desbloquear, removendo individualmente um
  registro existente.
- Desbloqueio em massa é proibido.
- A ordem obrigatória é Meta primeiro, banco depois.
- Se o desbloqueio na Meta falhar, o registro deverá permanecer no banco.
- Como esse bloqueio impede o contato na própria Meta, não existe atualmente uma
  chave Redis equivalente para ser removida nessa operação administrativa.

### 19.3. Unidades

- A criação de uma unidade registra primeiro o número na Meta.
- Se a Meta falhar, a unidade não será criada no banco.
- Antes da alteração no banco, o Redis deverá passar pelo preflight.
- Depois do save, a versão das unidades será incrementada e o cache recarregado.
- A exclusão desregistra primeiro o número na Meta.
- Se a Meta falhar durante a exclusão, a unidade permanecerá no banco.
- Se o Redis falhar depois de a Meta responder, o banco deverá permanecer sem
  alteração e o administrador deverá receber uma mensagem para tentar novamente.
- Exclusão em massa de unidades é proibida.

### 19.4. Papel de `status_ativo`

`status_ativo` não representa vinculação ou desvinculação do número no WABA.

- O campo está reservado ao controle comercial da unidade.
- Futuramente, ele poderá desativar o atendimento de unidades com pagamento
  vencido.
- Uma futura tabela `payment` poderá automatizar essa decisão, mas ela não faz
  parte da V1.
- Na V1, pagamentos e contratos poderão ser controlados manualmente, contrato por
  contrato.
- Alterar `status_ativo` deverá atualizar banco e cache de unidades, mas não
  deverá registrar ou remover o número na Meta.

O fato de uma edição de `status_ativo` não chamar a Meta é comportamento esperado,
e não uma lacuna.

### 19.5. Desvinculação definitiva de uma unidade

Para encerrar o vínculo de uma unidade com o sistema:

1. remover o número do `waba_id` pela conta oficial na plataforma da Meta;
2. excluir a unidade individualmente pelo Django Admin;
3. concluir a exclusão no banco e a atualização do cache de unidades.

A exclusão administrativa continua protegida pela validação Meta-first do código
e pelo preflight do Redis. A exclusão em massa permanece proibida.

Implementação principal:

- `callback/webhook/admin.py`
- `core/integrations/whatsapp/tools/ativando_numero.py`
- `core/integrations/whatsapp/tools/desativando_numero.py`

## 20. Disponibilidade e recuperação automática

“O sistema não deve cair nunca” é um requisito de resiliência operacional e
recuperação automática. Isso não significa afirmar que o interpretador Python, a
máquina ou a rede jamais poderão falhar.

Sempre deverá existir uma camada capaz de conter a falha e manter ou restaurar o
serviço:

- falha do Redis utiliza fallback quando existe uma fonte segura no banco;
- falha de uma mensagem não encerra o processamento das demais;
- o worker captura falhas, preserva ou reagenda o estado quando possível e
  continua o loop;
- `flow_worker.py` mantém o loop de consumo e os tratamentos por tipo de exceção;
- se `worker_flow()` escapar com uma exceção, `main_worker.py` registra a falha,
  aguarda 5 segundos e inicia outro loop;
- o webhook responde de maneira controlada a entradas inválidas e falhas
  conhecidas;
- chamadas externas à Meta falham de forma controlada, sem confirmar no banco
  uma operação recusada pela Meta;
- caches degradam para fallback ou negam uma operação administrativa que
  produziria inconsistência.

Para a produção 24x7, o deploy futuro deverá utilizar Docker e uma política de
reinício do container ou processo. As camadas serão complementares:

```text
operação individual falha
    -> exception ou fallback trata
    -> flow_worker continua
    -> main_worker reinicia o fluxo se ele escapar
    -> Docker reinicia o processo ou container se necessário
```

A URL pública e os containers de produção deverão permanecer disponíveis 24x7.
Falhas previstas não poderão produzir encerramento permanente do serviço nem
corrupção silenciosa. A infraestrutura Docker ainda é uma etapa futura do deploy;
os loops e fallbacks da aplicação já formam a base dessa estratégia.

Implementação principal:

- `workers/worker_flow/main_worker.py`
- `workers/worker_flow/response_flow/flow_worker.py`
- `core/cache/redis_client.py`
- `callback/webhook/services/post_flow.py`

## 21. Matriz de aderência conferida no código

| Regra | Estado atual | Observação |
|---|---|---|
| Somente a primeira mensagem sem resposta do turno é válida | Implementada | As demais não entram na fila nem no histórico enquanto existir uma fila aberta sem resposta própria do bot. |
| Liberar o próximo turno por resposta específica do bot | Implementada | O histórico vinculado à fila permite recuperação antes de `fila.status='sent'`, sem liberar uma sequência ilimitada. |
| Bloqueio de 30 dias depois da etapa final | Implementada | Banco e cache utilizam janela ou TTL de 30 dias. |
| Flood acima da métrica | Implementada | Redis, banco e memória formam a cadeia de avaliação; flood pode bloquear na Meta. |
| Payload grande | Implementada conforme a regra | Retorna HTTP 413 e não bloqueia a identidade informada no payload. |
| Assinatura inválida | Implementada conforme a regra | Retorna HTTP 403 e não confia no payload nem bloqueia possível vítima informada nele. |
| Cache Redis com fallback para banco | Implementada nos caches principais | Unidades, clientes e conversas bloqueadas possuem estratégias de fallback. |
| Autocura Redis/banco | Implementada no contrato da V1 | Cobre falhas detectáveis e FK stale; edição direta no banco é proibida em produção. |
| Admin majoritariamente somente leitura | Implementada | As exceções operacionais são unidade e desbloqueio individual. |
| Admin somente desbloqueia clientes | Implementada | Meta primeiro; falha preserva o registro no banco. |
| Unidade Meta-first na criação e exclusão | Implementada | Falha da Meta impede a alteração do banco. |
| `status_ativo` sem chamada Meta | Implementada conforme a regra | O campo é comercial; a futura automação de pagamentos não pertence à V1. |
| Desvinculação definitiva da unidade | Definida operacionalmente | Remover do WABA oficial e excluir individualmente pelo Admin. |
| Worker continua ou reinicia depois de falha | Implementada em camadas | `main_worker.py` reinicia `worker_flow()` depois de uma exceção. |
| Deploy Docker 24x7 | Futuro | Containers e política de restart complementarão as proteções da aplicação. |

## 22. Orientação para futuras alterações

Antes de modificar o fluxo:

1. identificar qual regra deste documento está envolvida;
2. classificar a mudança como correção, refatoração ou alteração de produto;
3. preservar turno único, idempotência e limite de tentativas quando a tarefa não
   solicitar explicitamente o contrário;
4. mapear quedas antes e depois de cada commit;
5. testar fluxo normal, retry antes do bot, retry depois do bot e finalização da
   fila;
6. não tratar um comportamento esperado da V1 como bug apenas por ele parecer
   conservador ou incompleto.
