# Desafios para a proxima versao

Este documento registra fragilidades conhecidas da V1 e ideias para a V2.

A V1 prioriza simplicidade, controle manual e consistencia suficiente para primeira producao. Algumas situacoes raras foram aceitas conscientemente para nao transformar o worker e o webhook em uma arquitetura mais complexa antes da hora.

## Principio atual da V1

Na V1, a regra mais importante do worker e:

```text
Marcar a mensagem da fila como sent deve ser sempre a ultima coisa do ciclo.
```

Essa regra existe para garantir o contexto de turno.

Na V1, a ideia base e:

```text
cada turno/etapa deve trabalhar com 1 mensagem valida do cliente e 1 resposta do bot.
```

Ou seja, enquanto o bot ainda nao concluiu a resposta daquele turno, novas mensagens do cliente para a mesma unidade nao devem entrar no fluxo.

O que muda no inicio da conversa e que a etapa 1 tem um comportamento especial: o bot inicia a etapa 2 logo depois de finalizar a etapa 1, no mesmo ciclo.

Exemplo:

```text
etapa 1:
cliente: ola
bot: saudacao

inicio da etapa 2 no mesmo ciclo:
bot: pergunta para quem e o atendimento
```

Nesse caso, a primeira mensagem do cliente abre a conversa, a saudacao fecha a etapa 1 e a pergunta do bot ja deixa a conversa posicionada na etapa 2 aguardando resposta do cliente.

Enquanto a mensagem nao esta `sent`, ela permanece `pending` ou `processing`.

Isso permite que o webhook aplique uma regra simples:

```text
Se ja existe mensagem pending ou processing para o mesmo wa_id + phone_id_unidade, ignora a nova mensagem.
```

Com isso, o webhook nao precisa entender etapa, historico, conversa ou `last_message_from`. Ele atua como porteiro barato. O worker atua como cerebro do fluxo.

Na V2, pode ser avaliado um modelo mais flexivel de contexto por turno.

Exemplo de possibilidade futura:

```text
analisar ate 3 mensagens do cliente e ate 3 mensagens do bot por turno
```

Isso permitiria interpretar melhor casos em que o cliente manda ideias quebradas em varias mensagens curtas. Ainda sera decidido se a V2 tera IA para interpretar esse contexto ou se continuara com regras deterministicas por etapa.

## Desafio 1 - Microjanela entre resposta do bot e liberacao do proximo turno

### Cenario

Fluxo esperado do worker:

```text
1. Worker processa a mensagem do cliente.
2. Worker envia resposta do bot pela Meta.
3. Worker registra historico do bot.
4. Worker atualiza conversa, incluindo last_message_from='bot'.
5. Worker marca a mensagem da fila como sent.
6. Worker faz commit final.
```

Existe uma microjanela teorica entre:

```text
last_message_from='bot'
```

e:

```text
fila_mensagens.status='sent'
```

Se o cliente enviar uma nova mensagem exatamente nesse intervalo, o webhook ainda pode encontrar a mensagem anterior como `processing`.

Como a regra do webhook e:

```text
pending/processing bloqueia nova mensagem
```

a nova mensagem sera ignorada.

### Impacto

Uma mensagem valida de um cliente real poderia ser ignorada.

Na pratica, isso e quase impossivel para um humano, porque o cliente teria que:

```text
receber a mensagem no WhatsApp
ler ou perceber a mensagem
digitar ou tocar na resposta
enviar
Meta processar
Meta chamar o webhook
nosso servidor receber o POST
```

tudo isso entre dois updates finais do worker.

Esse cenario e mais provavel com:

- robo;
- automacao;
- teste artificial;
- timing extremo da Meta;
- servidor travando exatamente no fim do ciclo.

### Observacao transacional importante

Se `last_message_from='bot'` e `status='sent'` forem atualizados na mesma transacao e so houver commit no final, outro request do webhook nao enxerga `last_message_from='bot'` antes do commit.

Mesmo assim, ele ainda enxerga a mensagem antiga como `processing`, porque o dequeue ja foi commitado antes.

Entao a decisao do webhook continua sendo:

```text
existe processing -> ignora
```

### Solucoes possiveis na V2

Opcao 1 - Aceitar a microjanela

Continuar com a regra simples:

```text
pending/processing bloqueia sempre
sent libera o proximo turno
```

Essa e a opcao mais simples e provavelmente suficiente.

Opcao 2 - Criar tabela de eventos ignorados

Registrar mensagens ignoradas por `fila_aberta` em uma tabela leve ou log estruturado.

Depois, seria possivel auditar:

```text
cliente respondeu durante janela de fila processing?
isso aconteceu com frequencia?
```

Opcao 3 - Reprocessamento seletivo

Criar um mecanismo futuro que recupere mensagens ignoradas em casos muito especificos.

Isso exige cuidado, porque pode reabrir o problema de multiplas mensagens por turno.

Opcao 4 - Webhook consultar estado da conversa

Usar `last_message_from='bot'` no webhook para liberar mensagens mesmo com fila `processing`.

Esta opcao nao e recomendada para a V1, porque quebra a regra simples:

```text
uma mensagem aberta por cliente/unidade
```

Para funcionar bem, exigiria novas regras no indice, no worker e no historico.

## Desafio 2 - Envio duplicado se o worker cair depois de enviar pela Meta e antes do commit

### Cenario

Fluxo possivel:

```text
1. Worker recebe mensagem do cliente.
2. Worker monta resposta.
3. Worker envia mensagem pela Meta.
4. Meta aceita o envio.
5. Antes do worker registrar historico/atualizar conversa/marcar sent/commit, o processo cai.
```

Como a Meta e externa ao banco, o envio nao participa da transacao PostgreSQL.

Se o worker cair depois que a Meta aceitou a mensagem, mas antes do commit do banco, o banco nao registra que o bot respondeu.

Depois:

```text
1. A mensagem antiga fica processing ate timeout.
2. O worker pega a mensagem novamente.
3. O banco parece nao ter historico do envio anterior.
4. O worker pode enviar a mesma resposta de novo.
```

### Impacto

O cliente pode receber mensagem duplicada do bot.

Esse risco e mais real que a microjanela do desafio 1, porque envolve queda entre chamada externa e commit local.

### Por que rollback nao resolve totalmente

Rollback protege o banco.

Mas rollback nao desfaz uma mensagem ja enviada pela Meta.

Entao o sistema pode ficar neste estado:

```text
Meta: mensagem enviada
Banco: mensagem nao registrada
```

### Solucoes possiveis na V2

Opcao 1 - Outbox de mensagens do bot

Criar uma tabela de outbox:

```text
bot_outbox
- id_outbox
- id_conversa
- id_mensagem_fila
- id_etapa
- payload
- status: pending, sending, sent, failed
- id_hash_msg_meta
- tentativas
- criado_em
- enviado_em
```

Fluxo:

```text
1. Worker decide que precisa enviar mensagem.
2. Worker cria registro na outbox.
3. Commit.
4. Um sender/outbox processor envia para Meta.
5. Sender atualiza outbox como sent com id_hash da Meta.
6. Worker ou processo de reconciliacao atualiza conversa/historico.
```

Vantagem:

- reduz duplicidade;
- permite retry controlado;
- permite auditoria;
- separa decisao de envio do envio externo.

Desvantagem:

- arquitetura mais complexa;
- mais tabelas;
- mais estados;
- exige reconciliacao.

Opcao 2 - Idempotency key interna

Gerar uma chave deterministica para cada mensagem do bot:

```text
id_conversa + etapa + tipo_resposta + id_mensagem_cliente
```

Antes de enviar, verificar se ja existe registro com essa chave.

Limitacao:

Se o envio ocorreu na Meta mas o banco caiu antes de salvar a chave, ainda pode duplicar.

Opcao 3 - Registrar intencao antes de enviar

Antes de chamar a Meta:

```text
INSERT historico/status pending para mensagem do bot
COMMIT
```

Depois envia Meta e atualiza para `sent`.

Vantagem:

- se cair depois, o banco sabe que havia uma intencao de envio.

Desvantagem:

- se a Meta falhar, o banco mostra uma mensagem planejada mas nao enviada;
- exige tratar status `pending/failed` no historico do bot;
- complica o fluxo atual.

Opcao 4 - Aceitar risco na V1

Para primeira producao, aceitar que queda exatamente entre Meta e commit pode duplicar resposta.

Mitigacoes:

- logs claros;
- `validar_historico` idempotente quando houver historico confirmado;
- operacao com um worker unico;
- monitoramento manual.

## Desafio 3 - Mensagem valida ignorada por fila aberta apos resposta do bot

Este desafio e parecido com a microjanela, mas visto pelo lado do webhook.

### Cenario

```text
1. Worker ja enviou a resposta do bot.
2. Worker ainda nao marcou a mensagem antiga como sent.
3. Cliente envia nova mensagem.
4. Webhook encontra mensagem antiga como processing.
5. Webhook ignora a nova mensagem por fila_aberta.
```

### Impacto

O cliente pode precisar mandar a mensagem de novo.

### Por que foi aceito na V1

A regra da V1 e simples:

```text
fila aberta = turno ainda fechado
sent = turno liberado
```

Essa regra e facil de entender, barata de executar e evita multiplas mensagens por turno.

### Solucoes futuras

- medir frequencia real desse evento;
- registrar logs estruturados de mensagens ignoradas por `fila_aberta`;
- se isso acontecer muito, avaliar tabela de eventos ignorados;
- evitar resolver isso consultando `last_message_from` no webhook antes de haver evidencias reais.

## Desafio 4 - Mensagens ignoradas nao ficam no historico

### Cenario

Na V1, mensagens extras do cliente enquanto existe fila aberta sao ignoradas no webhook.

Elas nao entram em:

- fila;
- historico;
- fluxo do worker.

### Impacto

O historico representa apenas mensagens uteis para o fluxo de negocio, nao tudo que o cliente tentou enviar.

Isso e bom para o fluxo, mas reduz auditoria.

### Solucao futura

Criar uma tabela separada para eventos ignorados:

```text
webhook_evento_ignorado
- id_evento
- wa_id
- phone_id
- motivo
- id_hash_msg
- tipo_mensagem
- recebido_em
- payload_resumido
```

Importante: essa tabela nao deve ser usada pelo fluxo principal.

Ela deve servir apenas para auditoria, suporte e monitoramento.

## Desafio 5 - V1 usa um unico worker

Na V1, o sistema roda apenas um worker.

Mesmo assim, o corpo do worker ja foi pensado com protecoes para race condition:

- `dequeue_message()` com `FOR UPDATE SKIP LOCKED`;
- status `pending` e `processing`;
- timeout para mensagens travadas em `processing`;
- `lock_conversa`;
- `unlock_conversa` com `lock_version`;
- checagem de mensagem anterior aberta;
- `reagendar_se_houver_mensagem_anterior`;
- commits e rollbacks centralizados em `worker_flow.py`.

Isso significa que a V1 ainda e simples, mas o desenho ja prepara caminho para multiplos workers.

## Ideia futura - Separar fila, historico e estado oficial do turno

Durante a evolucao do projeto, surgiu uma ideia para reduzir microjanelas e diminuir risco de duplicidade:

```text
1. Worker pega a mensagem da fila.
2. Worker salva a mensagem do cliente no historico.
3. Worker remove ou finaliza a mensagem da fila.
4. Worker usa outro estado oficial para indicar que o bot ainda precisa responder.
```

Essa ideia muda o papel da fila.

Na V1, a fila faz dois papeis:

```text
1. transporte da mensagem;
2. trava de turno aberto.
```

Ou seja:

```text
pending/processing = turno fechado para novas mensagens do cliente
sent = turno liberado
```

Na ideia futura, a fila seria apenas transporte.

O estado oficial do turno ficaria em outro lugar, provavelmente na tabela `conversa` ou em uma nova tabela.

Exemplo de fluxo futuro:

```text
1. cliente envia mensagem
2. webhook coloca na fila
3. worker pega mensagem da fila
4. worker salva mensagem do cliente no historico
5. worker atualiza conversa.turno_status = 'bot_processando'
6. worker remove/finaliza mensagem da fila
7. commit
8. bot envia resposta
9. worker salva historico do bot
10. worker atualiza conversa.turno_status = 'aguardando_cliente'
11. commit
```

Nesse modelo, o webhook nao olharia mais apenas para `pending/processing`.

Ele consultaria o estado oficial:

```text
se conversa.turno_status != 'aguardando_cliente', ignora
```

ou:

```text
se conversa.turno_aberto_para_cliente = false, ignora
```

### Vantagens possiveis

- fila fica apenas como mecanismo de transporte;
- historico registra a mensagem do cliente mais cedo;
- o turno passa a ter um estado explicito;
- pode facilitar recuperacao de falhas parciais;
- pode permitir aceitar/rejeitar mensagens com base em estado de negocio mais detalhado.

### Desvantagens

- exige nova coluna ou nova tabela;
- webhook passa a consultar estado de conversa/turno;
- aumenta custo por mensagem;
- exige tratar estados intermediarios;
- exige logica de recuperacao mais complexa;
- exige que o banco saiba diferenciar varios estados do turno.

Estados possiveis que poderiam existir:

```text
aguardando_cliente
cliente_respondeu
bot_processando
bot_enviado
erro_validacao_cliente
erro_envio_bot
turno_finalizado
```

### Relacao com etapa

A tabela `conversa.id_etapa_atual` ja representa bem a etapa atual do fluxo.

O conceito de turno e mais operacional:

```text
quem deve falar agora?
existe uma resposta do cliente sendo processada?
o bot ja respondeu?
o cliente pode enviar nova mensagem?
```

Por isso, talvez a V2 nao precise de uma tabela `turno`.

Pode ser suficiente adicionar colunas de estado operacional na propria tabela `conversa`, caso esse modelo seja adotado.

### Decisao para a V1

Nao aplicar essa ideia na V1.

Na V1, manter:

```text
fila pending/processing bloqueia novas mensagens
fila sent libera proximo turno
```

Essa decisao mantem o webhook simples e evita criar estados intermediarios antes de necessidade real em producao.

## Evolucao esperada para V2 - Worker como classe

Na V2, o worker deve deixar de ser apenas uma funcao solta e virar uma classe.

Hoje:

```text
worker_flow()
```

Futuro:

```text
WorkerChatbot
```

Ideia:

```python
class WorkerChatbot:
    def __init__(self, worker_id, config):
        self.worker_id = worker_id
        self.config = config

    def run_forever(self):
        while True:
            self.processar_ciclo()

    def processar_ciclo(self):
        ...
```

O corpo que hoje esta dentro de `worker_flow()` vira o corpo da classe.

As protecoes contra race condition continuam as mesmas, mas ficam encapsuladas por instancia.

## V2 - Multiplas instancias de worker

Com worker em classe, sera possivel criar:

- um controlador manual de workers;
- um gerenciador que cria workers conforme demanda;
- workers com identificador proprio;
- logs por worker;
- limites por worker;
- desligamento controlado;
- restart controlado.

Exemplo conceitual:

```python
workers = [
    WorkerChatbot(worker_id="worker-1", config=config),
    WorkerChatbot(worker_id="worker-2", config=config),
]

for worker in workers:
    iniciar_em_thread_ou_processo(worker)
```

## V2 - Async, paralelismo e processos

Opcoes futuras:

### Threads

Mais simples para iniciar multiplas instancias dentro do mesmo processo.

Cuidados:

- conexao de banco nao deve ser compartilhada entre threads;
- cada ciclo deve abrir sua propria conexao ou pegar uma do pool;
- logs precisam identificar `worker_id`.

### Processos

Mais isolado e mais parecido com producao.

Cuidados:

- cada processo tem sua propria memoria;
- Redis/cache local por processo pode divergir;
- observabilidade precisa ser melhor.

### Async

Pode ajudar se houver muitas chamadas de rede, como Meta e APIs externas.

Mas o projeto atual usa `psycopg2` e chamadas sincronas. Migrar para async exigiria mais mudancas.

Para V2, talvez seja melhor primeiro evoluir para multiplos workers sincronizados antes de migrar para async.

## V2 - Pool de conexoes

Hoje, cada ciclo pode fazer:

```python
conn = get_conn(application_name="worker_chatbot")
```

Isso e simples e seguro.

Na V2, se houver muitos workers, pode ser interessante usar pool de conexoes.

Possibilidades:

- `psycopg2.pool.SimpleConnectionPool`;
- `psycopg2.pool.ThreadedConnectionPool`;
- pool externo como PgBouncer;
- pool gerenciado pela infraestrutura.

Cuidados:

- nunca compartilhar a mesma conexao entre workers simultaneos;
- devolver conexao ao pool sempre no `finally`;
- rollback antes de devolver conexao com erro;
- definir `application_name` por worker, se possivel.

## V2 - Controlador de workers

Um controlador futuro pode:

- iniciar N workers;
- parar workers;
- reiniciar worker travado;
- ajustar quantidade conforme fila;
- expor status;
- registrar heartbeat;
- detectar worker sem progresso.

Possivel tabela futura:

```text
worker_status
- worker_id
- status
- ultimo_ciclo_em
- mensagem_atual
- criado_em
- atualizado_em
```

## V2 - Banco reconhecendo estados intermediarios

Na V1, o worker evita fazer commit a cada `INSERT`, `UPDATE` ou `DELETE`.

A regra atual e:

```text
commit por bloco logico
```

Principalmente no fluxo de resposta do bot:

```text
historico cliente
historico bot
update conversa
update etapa
update last_message_from
marcar fila como sent
commit final
```

Isso evita que o banco exponha estados incompletos como se fossem verdades oficiais.

Para a V2, pode ser estudada uma arquitetura em que o banco reconhece estados intermediarios. Isso permitiria commits mais frequentes, inclusive depois de comandos individuais de `INSERT`, `UPDATE` e `DELETE`.

Mas, para isso ser seguro, esses estados intermediarios precisam virar parte oficial do modelo.

Exemplos de estados:

```text
cliente_salvo_no_historico
bot_resposta_planejada
bot_enviando
bot_enviado_meta
historico_bot_salvo
conversa_atualizada
fila_finalizada
turno_finalizado
```

Com esse modelo, se o worker cair no meio, o proximo ciclo nao adivinha o que aconteceu. Ele consulta o estado intermediario e sabe de onde continuar.

Possiveis mudancas necessarias:

- tabela de outbox para mensagens do bot;
- tabela ou colunas de checkpoint do processamento;
- status mais granular para mensagens do bot;
- estado operacional do turno na conversa ou em tabela propria;
- funcoes SQL novas para lock/unlock de turno, outbox ou checkpoint;
- jobs de reconciliacao;
- idempotency keys para envios externos.

Essa arquitetura e mais robusta, mas tambem mais complexa.

Estimativa conceitual:

```text
V1 atual: cerca de 10 tabelas conceituais e 74 colunas de dominio.
V2 com estados intermediarios: algo como 13 a 15 tabelas conceituais e 110 a 140 colunas de dominio.
```

Decisao para a V1:

```text
nao fazer commit por comando
nao expor estados intermediarios desnecessarios
manter commit por bloco logico
manter sent como ultima etapa do ciclo
```

## Outras fragilidades transacionais para observar

### Commit apos vincular mensagem a conversa

Hoje o worker vincula a mensagem a uma conversa e faz commit antes de processar o restante.

Isso e util para rastreabilidade e recuperacao.

Mas significa que, se cair depois disso, a mensagem volta futuramente ja vinculada a conversa.

O fluxo atual lida bem com isso, mas o `validar_historico` deve considerar que uma mensagem pode ja ter `id_conversa` mesmo sem historico completo.

### Lock recusado deixa mensagem processing ate timeout

Quando o lock da conversa e recusado, a mensagem pode permanecer `processing` ate o timeout de 2 minutos.

Isso evita brigar pelo lock repetidamente, mas pode adicionar atraso.

Para V2, avaliar se vale reagendar imediatamente a mensagem quando o lock for recusado.

### Falha no unlock

Se o unlock falhar, a conversa fica `processing` ate expirar pelo timeout de `lock_conversa`.

O `lock_version` impede liberar lock errado, o que e bom.

Para V2, pode haver alerta especifico para falha no unlock.

### Historico parcial

Quando `validar_historico` e `flow_sender` entrarem, sera importante evitar historico parcial confuso.

Exemplo:

```text
historico cliente salvo
historico bot nao salvo
conversa nao atualizada
fila nao sent
```

O `validar_historico` deve conseguir identificar e completar o fluxo.

### Reenvio apos falha externa

Toda chamada externa antes do commit final pode gerar duplicidade se a chamada externa teve sucesso e o banco nao registrou.

Isso vale para:

- Meta;
- APIs externas;
- servicos de agenda;
- notificacoes futuras.

Na V2, chamadas externas importantes devem avaliar padrao outbox.

## V2 - Otimizacoes SQL para perguntas objetivas

Na V1, o projeto ja usa bem a ideia de deixar o SQL responder perguntas objetivas do banco.

Exemplos atuais positivos:

```text
existe mensagem aberta no turno?
qual estado da conversa?
existe mensagem anterior aberta na mesma conversa?
ja existe resposta do bot para esta mensagem do cliente?
```

Esse padrao deve continuar na V2.

A regra geral recomendada e:

```text
SQL responde existencia, vinculo, ultimo registro e estado.
Python decide o fluxo conversacional.
```

Ou seja, evitar trazer muitas linhas para Python apenas para fazer `if`, `for`, filtro ou comparacao que o banco poderia responder diretamente com indice.

### Candidato 1 - Ultima mensagem do bot e ultima mensagem do cliente

Hoje o `valida_historico` pode buscar algumas mensagens recentes e depois o Python procura:

```text
ultima mensagem do bot
ultima mensagem anterior do cliente
```

Na V2, se o `flow_sender` nao precisar do historico recente completo, isso pode virar uma consulta SQL objetiva.

Possibilidades:

```text
buscar_ultima_mensagem_bot(id_conversa)
buscar_ultima_mensagem_cliente(id_conversa)
```

ou uma query unica com:

```sql
DISTINCT ON (quem_enviou)
```

Objetivo:

```text
reduzir dados retornados
reduzir loops em Python
deixar o banco usar indice por conversa/data
```

Observacao:

```text
nao otimizar antes de saber exatamente quanto contexto o flow_sender da V2 precisara.
```

Se a V2 for analisar ate 3 mensagens do cliente e 3 do bot, ainda pode fazer sentido buscar um historico curto.

### Candidato 2 - Flood guard com multiplas regras

Na V1, o antiflood usa apenas uma regra:

```text
15 mensagens em 5 segundos
```

Por isso, o loop em Python sobre as regras nao e um problema.

Se a V2 voltar a ter varias regras, como:

```text
10 mensagens em 5 segundos
30 mensagens em 60 segundos
60 mensagens em 1 segundo
```

pode ser melhor criar uma consulta SQL que retorne diretamente:

```text
regra estourada
total da janela
maior total observado
```

Isso evita multiplas consultas ao banco para a mesma chave `wa_id + phone_id`.

### Candidato 3 - Dados de bloqueio Meta em uma consulta

Hoje, quando flood e detectado, o webhook busca dados de bloqueio em duas perguntas:

```text
id_cliente pelo wa_id
unidade pelo phone_id
```

Na V2, isso pode virar uma consulta unica retornando:

```text
id_cliente
id_unidade
phone_id_unidade
motivo
```

Ganho esperado:

```text
menos round trips ao banco quando flood acontece
codigo mais direto
```

Baixa prioridade:

```text
isso so roda quando flood ja foi detectado, nao em mensagem normal.
```

### Candidato 4 - Insercao na fila como funcao SQL unica

Hoje o webhook faz:

```text
1. advisory lock do turno
2. verifica se ja existe pending/processing
3. se puder, faz INSERT na fila
```

Na V2, isso poderia virar uma funcao SQL unica:

```text
try_enqueue_message(...)
```

Responsabilidades possiveis:

```text
adquirir advisory lock
verificar fila aberta
inserir mensagem
retornar status: inserted, fila_aberta, conflito_unico, dados_invalidos
```

Vantagens:

```text
menos round trips
decisao atomica no banco
webhook mais enxuto
```

Desvantagens:

```text
mais logica no banco
debug pode ficar menos intuitivo
maior complexidade antes de necessidade real
```

Decisao para V1:

```text
nao aplicar agora.
o fluxo atual ja esta seguro com advisory lock e indice parcial.
```

### O que nao deve virar SQL

Nem toda regra deve ir para o banco.

Devem continuar em Python:

```text
decisoes conversacionais por etapa
montagem de mensagens do bot
extracao e interpretacao do payload da Meta
regras que dependem de APIs externas
logs de negocio mais expressivos
fluxos que precisam ser lidos facilmente por desenvolvedores
```

SQL deve responder fatos.

Python deve decidir comportamento.

## Resumo da V2

Pontos principais para V2:

- transformar worker em classe;
- permitir multiplas instancias;
- manter protecoes atuais de race condition;
- avaliar pool de conexoes;
- avaliar controlador manual ou automatico de workers;
- criar observabilidade por worker;
- estudar outbox para mensagens do bot;
- registrar eventos ignorados se houver necessidade de auditoria;
- melhorar recuperacao de falhas entre Meta e commit;
- manter `sent` como ultima etapa do ciclo.
