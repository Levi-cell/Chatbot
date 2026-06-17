# Desafios e Evolucoes para a V2

Este documento registra os buracos conhecidos da V1, as decisoes aceitas para a primeira producao e as tarefas futuras que devem orientar a V2.

A V1 foi desenhada para ser simples, controlavel e suficientemente protegida para operar com poucas unidades no inicio. O objetivo da V2 nao e "corrigir bagunca"; e evoluir uma base que ja nasceu com protecoes importantes, mas que propositalmente evita uma arquitetura pesada antes de existir demanda real.

## Estado Atual da V1

### Alinhamento com o codigo real

Este documento deve ser lido com uma separacao clara:

```text
V1 ja aplicada no codigo
V1 em fechamento pelo plano atual
V2 futura
```

Ja esta aplicado no codigo da V1:

- webhook com regra de turno por cliente/unidade;
- webhook liberando nova mensagem quando a fila aberta ja tem resposta do bot registrada;
- `avaliar_turno_cliente_para_fila`;
- `valida_historico` registrando a mensagem do cliente;
- `valida_historico` buscando resposta do bot ja vinculada a mensagem atual;
- `reagendar_se_houver_mensagem_anterior` como segunda camada de ordem no worker;
- commits, rollbacks e close concentrados em `worker_flow.py`;
- worker ainda como funcao, com apenas uma instancia prevista para a V1.

Ainda esta em fechamento pelo plano atual da V1:

- chamada real do `flow_sender` dentro do `worker_flow`;
- sender da etapa 1 usando Meta/PyWa;
- `ErroEnvioMeta`;
- `BancoFalhouAposEnvioMeta`;
- `atualizar_banco_com_contexto_final`;
- registro da resposta do bot no historico apos envio real da Meta.

Portanto, quando este documento fala sobre `ErroEnvioMeta`, `BancoFalhouAposEnvioMeta` e `atualizar_banco_com_contexto_final`, ele esta considerando a V1 completa apos o plano atual ser aplicado. A V2 deve partir dessa V1 completa, nao do estado parcial anterior ao envio real do bot.

### Principio central

Na V1, a regra mais importante do worker continua sendo:

```text
Marcar a mensagem da fila como sent deve ser sempre a ultima coisa do ciclo.
```

Essa regra preserva o turno da conversa.

Conceito de turno na V1:

```text
1 mensagem valida do cliente
1 resposta do bot
sent libera o proximo turno
```

A etapa atual da conversa continua sendo representada por `conversa.id_etapa_atual`. O conceito de turno e operacional: ele responde perguntas como:

```text
quem falou por ultimo?
existe mensagem do cliente em processamento?
o bot ja respondeu aquela mensagem?
o cliente pode enviar a proxima mensagem?
```

### Etapa 1 na V1

A etapa 1 nao deve mais pular automaticamente para a etapa 2 no mesmo ciclo.

Fluxo esperado:

```text
cliente: ola
bot: mensagem da etapa 1
```

No futuro, a mensagem da etapa 1 pode ter botao, por exemplo:

```text
Estou pronto para agendar uma aula demonstrativa
```

O cliente clicando ou respondendo abre o proximo turno, e ai o fluxo segue para a etapa 2.

### Webhook na V1

O webhook e o porteiro do sistema. Ele deve ser barato, rapido e protetor.

Fluxo conceitual:

```text
1. validar Content-Type JSON
2. validar tamanho maximo do body
3. validar assinatura da Meta
4. parsear JSON
5. aplicar antiflood 15 mensagens em 5 segundos por wa_id + phone_id
6. validar unidade ativa
7. validar conversa bloqueada temporariamente
8. validar turno do cliente
9. inserir na fila
```

### Regra atual de turno no webhook

A V1 nao usa mais a regra antiga e cega:

```text
qualquer pending/processing bloqueia sempre
```

Agora o webhook avalia a fila aberta do mesmo cliente/unidade.

Se nao existe fila aberta:

```text
pode enfileirar
```

Se existe fila aberta sem resposta do bot registrada:

```text
nao enfileira
```

Se existe fila aberta, mas todas as mensagens abertas daquele cliente/unidade ja tem resposta do bot registrada:

```text
pode enfileirar por recuperacao
```

Uma fila aberta e considerada respondida quando existe prova no banco:

```text
conversa.last_message_from = 'bot'
historico_mensagens.quem_enviou = 'bot'
historico_mensagens.status_envio = 'sent'
historico_mensagens.id_mensagem_fila = fila_mensagens.id_mensagem
historico_mensagens.id_hash_cliente_origem = fila_mensagens.id_hash_msg
```

Essa regra resolve o buraco antigo em que o cliente poderia responder o bot, mas a fila anterior ainda nao estava marcada como `sent`.

### Worker na V1

Na V1 existe apenas um worker ativo.

Mesmo assim, o corpo do worker ja foi escrito pensando em race condition:

- `dequeue_message()` com `FOR UPDATE SKIP LOCKED`;
- status `pending` e `processing`;
- timeout para mensagem travada em `processing`;
- `lock_conversa`;
- `unlock_conversa` com `lock_version`;
- `reagendar_se_houver_mensagem_anterior`;
- commits e rollbacks centralizados em `worker_flow.py`;
- idempotencia por historico do bot vinculado a mensagem da fila;
- `sent` como ultima etapa do ciclo.

Isso permite que a V1 use um worker unico, mas com corpo preparado para evoluir para multiplas instancias na V2.

### Flow sender planejado para fechar a V1

O desenho esperado para fechar a V1 com envio real pela Meta e:

```text
1. valida_historico registra a mensagem do cliente
2. flow_sender decide a etapa
3. flow_sender chama o sender da etapa
4. sender da etapa envia pela Meta/PyWa
5. sender retorna contexto de sucesso com id_hash_msg_bot
6. worker chama atualizar_banco_com_contexto_final
7. banco registra historico do bot e last_message_from='bot'
8. worker comita
9. worker marca fila como sent
10. worker comita de novo
```

Se a Meta falhar:

```text
ErroEnvioMeta
rollback
nao registra historico do bot
nao atualiza last_message_from='bot'
nao marca sent
mensagem volta por retry
```

Se a Meta enviar, mas o banco falhar antes de registrar a resposta:

```text
BancoFalhouAposEnvioMeta
log critico
risco raro de duplicidade
mensagem volta por retry
```

## Buraco Principal Ainda Aberto na V1

## Desafio 1 - Meta enviou, mas banco/worker caiu antes de atualizar o banco

Este e o principal risco transacional restante da V1.

### Cenario

```text
1. Worker processa mensagem do cliente.
2. Worker chama flow_sender.
3. flow_sender chama sender da etapa.
4. Meta/PyWa envia a mensagem com sucesso.
5. Worker recebe id_hash_msg_bot.
6. Antes de atualizar historico do bot e conversa, o banco cai ou o processo cai.
```

Resultado:

```text
Meta: mensagem enviada ao cliente
Banco: nao sabe que a mensagem foi enviada
Fila: nao virou sent
```

Depois de 2 minutos, ou pelo tratamento de retry:

```text
1. Worker pega a mesma mensagem de novo.
2. valida_historico procura resposta do bot para aquela mensagem.
3. Banco nao tem resposta registrada.
4. flow_sender pode enviar a mesma resposta novamente.
```

### Impacto

O cliente pode receber uma resposta duplicada.

Esse risco nao e causado pelo webhook. Ele existe porque a Meta e um sistema externo e nao participa da transacao PostgreSQL.

Rollback protege o banco, mas nao desfaz uma mensagem ja enviada pela Meta.

### Status na V1

Aceito como risco raro para primeira producao.

Mitigacoes atuais:

- log critico especifico;
- retry controlado;
- um worker unico;
- idempotencia quando o banco ja tem historico do bot;
- webhook com recuperacao quando a fila aberta ja foi respondida pelo bot.

### Tarefa para V2

Criar uma solucao transacional mais forte para envio externo, provavelmente com outbox, checkpoint ou estado intermediario oficial.

## Casos Que a V1 Agora Trata Melhor

## Caso 1 - Worker caiu depois de registrar resposta do bot, mas antes de marcar sent

### Cenario

```text
1. Worker envia resposta pela Meta.
2. Worker insere historico do bot.
3. Worker atualiza conversa para last_message_from='bot'.
4. Worker comita.
5. Worker cai antes de marcar fila como sent.
```

### Comportamento na V1

O banco tem prova da resposta do bot.

O webhook pode aceitar uma nova mensagem do cliente mesmo com fila anterior aberta, porque a fila aberta ja esta respondida.

Se o worker pegar a mensagem antiga de novo:

```text
valida_historico encontra resposta_bot_para_mensagem_atual
flow_sender nao reenvia
worker marca a fila antiga como sent
```

Se o worker pegar uma mensagem nova antes de fechar a antiga:

```text
reagendar_se_houver_mensagem_anterior segura a mensagem nova
mensagem antiga fecha primeiro
mensagem nova processa depois
```

Esse caso deixou de ser o principal buraco da V1.

## Caso 2 - Cliente responde durante fila antiga processing, mas ja respondida pelo bot

### Cenario

```text
1. Bot ja respondeu a mensagem A.
2. Banco ja registrou historico do bot para A.
3. A ainda esta pending/processing, nao sent.
4. Cliente envia mensagem B.
```

### Comportamento na V1

O webhook avalia se a fila aberta esta respondida.

Se estiver:

```text
mensagem B entra na fila
```

O worker mantem a ordem com `reagendar_se_houver_mensagem_anterior`.

Esse fluxo reduz muito a chance de mensagem valida ser ignorada.

## Desafio 2 - Mensagens ignoradas nao ficam no historico

Na V1, mensagens bloqueadas no webhook nao entram no historico da conversa.

Exemplos:

- mensagem enquanto existe fila aberta sem resposta do bot;
- flood;
- unidade inativa;
- body invalido;
- assinatura invalida;
- content-type invalido;
- conversa temporariamente bloqueada.

### Impacto

O historico da conversa registra o fluxo util para o negocio, nao tudo que chegou no endpoint.

Isso simplifica o fluxo, mas reduz auditoria.

### Tarefa para V2

Avaliar uma tabela de eventos ignorados apenas para auditoria, suporte e metricas.

Ela nao deve dirigir o fluxo principal do chatbot.

Exemplo conceitual:

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

## Desafio 3 - Outbox para mensagens do bot

A V1 envia mensagem pela Meta diretamente dentro do ciclo do worker.

Isso e simples, mas cria o risco do desafio principal:

```text
Meta enviou
banco nao registrou
retry duplica
```

### Tarefa para V2

Estudar outbox de mensagens do bot.

Objetivo:

- registrar intencao de envio antes da chamada externa;
- controlar retry da Meta;
- separar decisao conversacional do envio externo;
- auditar payloads enviados;
- reduzir duplicidade quando processo cai;
- permitir reconciliacao.

Exemplo conceitual:

```text
bot_outbox
- id_outbox
- id_conversa
- id_mensagem_fila
- id_etapa
- tipo_mensagem
- payload
- status
- id_hash_msg_meta
- tentativas
- criado_em
- enviado_em
- erro
```

Possiveis estados:

```text
pending
sending
sent
failed
reconciled
```

## Desafio 4 - Banco reconhecendo estados intermediarios

Na V1, o sistema evita fazer commit apos cada `INSERT`, `UPDATE` ou `DELETE`.

A regra e:

```text
commit por bloco logico
```

Isso mantem o fluxo simples e evita expor estados incompletos como verdade oficial.

Na V2, se quisermos commits mais frequentes, o banco precisa reconhecer estados intermediarios oficialmente.

Isso significa que nao basta o Python "saber" que esta em um meio de fluxo. O banco precisa conseguir representar esse meio de fluxo de forma consultavel, auditavel e recuperavel.

Exemplos de estados intermediarios que poderiam existir:

```text
cliente_salvo_no_historico
resposta_bot_planejada
resposta_bot_enviando
resposta_bot_enviada_meta
historico_bot_salvo
conversa_atualizada
fila_finalizada
turno_finalizado
```

### O que o banco precisa ter para identificar esses estados

Para estados intermediarios serem seguros, o banco precisa ter pelo menos:

- chave de idempotencia da operacao;
- status operacional claro;
- timestamps de entrada e saida do estado;
- identificador do worker que assumiu o estado;
- contador de tentativas;
- ultimo erro;
- vinculo com `id_conversa`;
- vinculo com `id_mensagem_fila`;
- vinculo com `id_hash_msg` da mensagem do cliente;
- vinculo com `id_hash_msg_bot` quando a Meta confirmar envio;
- constraints que impecam duplicidade logica;
- indices para consultar rapidamente estado pendente/travado;
- funcoes SQL ou updates atomicos para avancar estado.

Exemplo conceitual de campos:

```text
estado_operacional
checkpoint_atual
idempotency_key
locked_by_worker
locked_at
tentativas
last_error
created_at
updated_at
completed_at
```

O ponto principal:

```text
se o worker cair, o proximo worker nao pode adivinhar o que aconteceu.
ele deve consultar o banco e saber exatamente de qual checkpoint continuar.
```

### Tarefas de back-end para detectar estados intermediarios

Na V2, o back-end deve ter tarefas especificas para:

- detectar estado parado ha tempo demais;
- detectar envio Meta confirmado mas nao persistido no historico;
- detectar historico do bot salvo mas conversa nao atualizada;
- detectar conversa atualizada mas fila nao finalizada;
- detectar fila `processing` expirada;
- detectar outbox `sending` travada;
- detectar resposta do bot planejada, mas nunca enviada;
- detectar divergencia entre `historico_mensagens`, `fila_mensagens`, `conversa` e Meta;
- decidir se deve continuar, reparar, alertar ou pausar.

Essas tarefas podem virar:

- jobs periodicos;
- funcoes administrativas;
- comandos manuais;
- processos de reconciliacao;
- checks no inicio do ciclo do worker.

### Tarefas de persistencia para estados intermediarios

Na V2, cada avanco importante deve salvar estado suficiente para recuperacao.

Exemplo conceitual:

```text
1. salvar intencao de resposta do bot
2. commit
3. enviar Meta
4. salvar id_hash_msg_bot
5. commit
6. inserir historico do bot
7. atualizar conversa
8. finalizar fila/turno
```

Isso so e seguro se cada estado intermediario tiver significado oficial.

Se nao houver esse modelo, commits frequentes aumentam risco de:

- duplicidade;
- mensagem perdida;
- conversa em estado incoerente;
- webhook liberando turno cedo demais;
- worker retomando do ponto errado.

### Tarefa para V2

Decidir se vale criar:

- colunas de checkpoint;
- tabela de turno operacional;
- outbox;
- status mais granular no historico do bot;
- funcoes SQL para avancar estados com seguranca.

Tambem decidir onde esses estados devem morar:

- na tabela `conversa`;
- em uma nova tabela `turno_operacional`;
- em uma tabela `bot_outbox`;
- em uma tabela de `processamento_mensagem`;
- ou em uma combinacao pequena dessas estruturas.

Decisao importante:

```text
nao criar estados intermediarios apenas em variaveis Python.
estado intermediario que precisa sobreviver a queda deve estar no banco.
```

## Desafio 5 - Worker como classe

Na V1:

```text
worker_flow()
```

Na V2, o worker deve virar classe.

Exemplo conceitual:

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

O corpo protegido contra race condition que hoje esta em `worker_flow()` deve virar o corpo operacional da classe.

### Tarefas para V2

- criar `WorkerChatbot`;
- manter commits/rollbacks claros por ciclo;
- manter `sent` como ultima operacao;
- incluir `worker_id` nos logs;
- permitir configuracao por instancia;
- preparar inicializacao e parada controlada.

## Desafio 6 - Controlador de workers

Na V1, um worker deve ser suficiente para poucas unidades.

Na V2, quando houver mais unidades e mais volume, sera necessario um controlador.

### Tarefas para V2

Criar controlador capaz de:

- iniciar N workers;
- parar workers;
- reiniciar worker travado;
- ajustar quantidade de workers conforme demanda;
- registrar heartbeat;
- expor status;
- controlar desligamento gracioso;
- separar logs por worker.

Possivel tabela futura:

```text
worker_status
- worker_id
- status
- ultimo_ciclo_em
- mensagem_atual
- total_processadas
- criado_em
- atualizado_em
```

## Desafio 7 - Multiplas instancias, paralelismo e pool de conexoes

A V1 abre conexao no ciclo do worker com:

```text
get_conn(application_name="worker_chatbot")
```

Isso e simples e seguro para um worker.

Na V2, com multiplos workers, sera necessario avaliar:

- pool de conexoes;
- PgBouncer;
- limite de conexoes no banco;
- `application_name` por worker;
- rollback antes de devolver conexao ao pool;
- conexao nunca compartilhada simultaneamente entre workers.

Opcoes:

- threads;
- processos;
- workers independentes;
- async no futuro, se fizer sentido.

Observacao:

```text
async nao deve ser a primeira evolucao obrigatoria.
```

Como o projeto usa chamadas sincronas e `psycopg2`, a evolucao mais natural e primeiro suportar multiplos workers sincronizados com isolamento correto.

## Desafio 8 - Redis, cache local e multiplos processos

Na V1, alguns fallbacks usam memoria local quando Redis/banco falham.

Com um processo unico, isso e aceitavel.

Na V2, com multiplos processos ou multiplos servidores:

```text
memoria local nao e compartilhada
```

### Tarefas para V2

- decidir o papel do Redis como fonte operacional temporaria;
- criar alerta quando Redis falhar;
- revisar fallback local para ambiente multi-worker;
- avaliar cache distribuido;
- criar reconciliacao quando fallback local registrar evento critico.

## Desafio 9 - Reconciliacao banco x Meta

A V1 tem utilitarios para listar bloqueios da Meta e comparar com o banco.

Ainda falta transformar isso em rotina operacional.

### Tarefas para V2

- criar job de reconciliacao banco x Meta;
- ler divergencias de bloqueio;
- reportar divergencias;
- opcionalmente corrigir divergencias com confirmacao;
- ler arquivos de alerta critico gerados pelo webhook;
- reconciliar bloqueios registrados fora do banco;
- gerar relatorio legivel para operacao.

## Desafio 10 - Alertas criticos

Na V1, logs existem e alguns erros criticos podem ser registrados.

Na V2, logs precisam virar alerta operacional.

Eventos que devem gerar alerta:

- `BancoFalhouAposEnvioMeta`;
- falha repetida da Meta;
- flood detectado;
- Redis indisponivel;
- banco indisponivel;
- falha no unlock;
- muitos retries;
- mensagens removidas por `max_retry`;
- divergencia banco x Meta.

### Tarefas para V2

- decidir canal de alerta;
- criar dashboard;
- criar arquivos/relatorios rotativos se necessario;
- definir severidade;
- definir quem deve agir.

## Desafio 11 - Observabilidade e metricas

Logs ajudam no debug, mas metricas ajudam a operar.

### Tarefas para V2

Medir:

- mensagens recebidas por minuto;
- mensagens enfileiradas;
- mensagens ignoradas por motivo;
- tempo medio no webhook;
- tempo medio no worker;
- fila pending;
- fila processing;
- mensagens com retry;
- falhas Meta;
- falhas banco;
- bloqueios por flood;
- quantidade por unidade;
- tempo por etapa.

## Desafio 12 - Infraestrutura AWS e Meta

As protecoes em Django ajudam, mas nao substituem infraestrutura.

### Tarefas para V2 / producao mais madura

Na Meta:

- app em modo live;
- webhook no dominio final;
- verify token correto;
- App Secret configurado;
- assinatura validada;
- WABA/numeros conectados;
- eventos corretos assinados.

Na AWS:

- dominio HTTPS;
- Gunicorn/Uvicorn;
- Nginx ou Load Balancer;
- Security Groups;
- CloudFront + WAF ou AWS WAF;
- rate limit por IP/origem;
- logs centralizados;
- metricas;
- alarmes;
- segredos fora do codigo.

## Desafio 13 - Segredos e criptografia

Na V1, alguns segredos ainda podem estar em arquivo de configuracao.

### Tarefas para V2

- mover token da Meta para variavel de ambiente ou secret manager;
- mover App Secret para variavel de ambiente ou secret manager;
- mover credenciais de banco para ambiente seguro;
- avaliar AWS Secrets Manager;
- revisar logs para garantir que token nunca aparece;
- documentar rotacao de token.

## Desafio 14 - Interface operacional

Hoje o Django admin cobre parte importante da operacao.

Na V2, pode existir uma interface propria.

### Tarefas futuras

- tela de unidades;
- tela de conversas;
- tela de bloqueios Meta;
- tela de relatorios de flood;
- tela de fila;
- tela de erros criticos;
- botao para rodar reconciliacao;
- filtros por unidade;
- leitura de historico;
- status de worker.

## Desafio 15 - IA ou regras deterministicas

A V1 deve seguir fluxo seco por etapas.

Na V2, pode ser avaliado:

- continuar com regras;
- usar IA apenas para classificacao;
- usar IA para extrair nome, idade e intencao;
- usar IA para interpretar ate 3 mensagens recentes do cliente e 3 do bot;
- usar IA apenas em fallback quando regra nao entender.

Decisao ainda aberta:

```text
a V2 tera IA ou continuara deterministica?
```

Mesmo com IA, o estado oficial da conversa deve continuar no banco.

## Desafio 16 - Tratamento de respostas invalidas

Na V1, o plano atual deixa uma base simples:

- `flow_treat_unsupported_type` para tipos nao suportados, como midia, audio, documento e figurinha;
- `flow_treat_context` como esqueleto para respostas fora do contexto esperado;
- tratamentos registrando historico e usando o mesmo contrato transacional do `flow_sender`;
- tratamento sem avancar etapa oficial.

Na V2, ainda sera preciso implementar tratamentos por etapa com mais detalhe.

Exemplo:

```text
bot: Qual seu nome?
cliente: resposta invalida
bot: Nao consegui usar esse nome. Digite novamente.
cliente: Alice
```

### Decisao futura

Definir se mensagens invalidas continuam entrando no historico principal ou se entram em uma estrutura separada.

Registrar tudo aumenta auditoria.

Registrar apenas respostas validas simplifica o fluxo.

Essa decisao deve ser feita com cuidado, porque pode afetar:

- suporte;
- auditoria;
- IA futura;
- entendimento de contexto;
- simplicidade do historico.

Tambem sera necessario decidir se `flow_treat_context` deve:

- repetir a pergunta exata da etapa atual;
- enviar botoes/listas da etapa atual novamente;
- usar IA ou regras deterministicas para identificar resposta fora de contexto;
- registrar categorias de erro, como `midia`, `texto_fora_contexto`, `botao_invalido`, `tentativa_maliciosa`.

## Desafio 17 - Tipos de mensagem e componentes Meta

A V1 comeca com mensagens simples.

Na V2, o bot deve suportar melhor:

- botoes;
- listas;
- templates;
- links;
- respostas interativas;
- midias;
- documentos;
- mensagens unsupported;
- payloads de componentes da Meta.

Cada sender de etapa deve manter contrato padrao:

```text
enviou
resposta_ja_existia
tipo_mensagem
mensagem_bot ou payload resumido
id_hash_msg_bot
id_etapa_resultante
```

Assim, `atualizar_banco_com_contexto_final` continua servindo para todas as etapas.

## Desafio 18 - Otimizacoes SQL para perguntas objetivas

A V1 ja usa bem SQL para perguntas objetivas.

Regra para V2:

```text
SQL responde existencia, vinculo, ultimo registro e estado.
Python decide comportamento conversacional.
```

Possiveis evolucoes:

- buscar ultima mensagem do bot diretamente em SQL;
- buscar ultima mensagem do cliente diretamente em SQL;
- consolidar query de flood se houver multiplas regras;
- criar `try_enqueue_message(...)` como funcao SQL unica;
- reduzir loops em Python quando o banco puder responder com indice;
- manter legibilidade acima de micro-otimizacao.

## Desafio 19 - Funcao SQL unica para enqueue

Hoje o webhook faz etapas separadas:

```text
advisory lock
avaliar turno
inserir fila
```

Na V2, pode ser criada uma funcao SQL:

```text
try_enqueue_message(...)
```

Ela poderia retornar:

```text
inserted
fila_aberta_sem_resposta_bot
fila_aberta_respondida_bot
duplicada
dados_invalidos
```

Vantagem:

- decisao mais atomica;
- menos round trips;
- webhook ainda mais enxuto.

Risco:

- mais logica no banco;
- debug menos intuitivo;
- maior complexidade.

## Desafio 20 - Escala por unidades

A V1 deve funcionar bem para poucas unidades.

Na V2, quando o numero de unidades crescer, revisar:

- volume por unidade;
- filas por unidade;
- prioridade por unidade;
- limites por unidade;
- metricas por unidade;
- isolamento operacional;
- capacidade do banco;
- capacidade do Redis;
- capacidade da Meta/API.

## O Que a V2 Deve Preservar da V1

Mesmo evoluindo, a V2 deve preservar:

- webhook enxuto;
- worker como cerebro;
- `sent` como ultima operacao ou equivalente operacional;
- logs com motivo e acao;
- SQL em repositories;
- DDL/funcoes SQL em database;
- commits e rollbacks visiveis no fluxo principal;
- idempotencia antes de envio externo;
- protecoes contra race condition;
- controle manual pelo admin quando fizer sentido.

## Resumo de Tarefas Futuras

Principais tarefas da V2:

- transformar worker em classe;
- criar controlador de workers;
- suportar multiplas instancias;
- avaliar pool de conexoes;
- implementar outbox ou checkpoint para envio Meta;
- reduzir risco Meta ok + banco falhou;
- criar job de reconciliacao banco x Meta;
- criar alertas criticos;
- criar metricas operacionais;
- revisar fallback local em arquitetura multi-processo;
- amadurecer infraestrutura AWS/Meta;
- mover segredos para ambiente seguro;
- estudar interface operacional;
- decidir uso de IA;
- implementar tratamento de respostas invalidas;
- suportar botoes/listas/templates;
- avaliar tabela de eventos ignorados;
- continuar otimizando SQL apenas onde houver ganho real.

## Decisao Final para a V1

Nao transformar a V1 em uma arquitetura de outbox, multi-worker e estado intermediario completo antes da primeira producao.

A V1 deve fechar o fluxo principal, operar com seguranca suficiente, atender os primeiros clientes e gerar dados reais.

A V2 deve nascer dos problemas reais observados em producao, principalmente:

```text
duplicidade apos Meta ok + banco/worker falhou
volume exigindo multiplos workers
necessidade de auditoria de eventos ignorados
necessidade de observabilidade e alertas
necessidade de IA ou tratamento mais sofisticado por etapa
```
