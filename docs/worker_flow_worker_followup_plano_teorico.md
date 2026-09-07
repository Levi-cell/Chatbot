# Plano teórico — `worker_followup` e retorno após inatividade

## Objetivo do documento

Este documento registra o contrato funcional e os cuidados técnicos da integração entre:

- o novo `worker_followup`, responsável por enviar um único lembrete quando o cliente não responde; e
- o `worker_flow`, responsável por processar a reação do cliente, repetir a etapa atual e encerrar o ciclo de follow-up.

O ponto de partida é a V1.1.0, registrada no commit `3f75447`. A implementação descrita neste plano formará a V1.1.1.

O documento é intencionalmente teórico. Ele define responsabilidades, estados, transações, concorrência, retries e critérios de aceite. A futura implementação deve continuar obedecendo a:

- `REGRAS_DE_NEGOCIO.md`;
- `PADROES_DE_ARQUITETURA.md`;
- `ROTINA_IMPLEMENTACAO_ETAPAS.md`;
- os contratos documentados nos READMEs de `workers`, `core`, `deploy` e `tests`.

A coluna canônica do ciclo é `chatbot.conversa.followup_stage`. Expressões como “stage de follow-up” representam essa mesma coluna.

## Escopo fechado da V1.1.1

Nesta primeira entrega existe somente um follow-up por período contínuo sem resposta:

```text
Cliente fica 7 horas sem responder
    -> worker_followup envia "Você viu a minha mensagem?"
    -> followup_stage muda de 0 para 1

Se o cliente não responder
    -> followup_stage permanece 1
    -> nenhuma outra mensagem é enviada

Se o cliente responder
    -> worker_flow registra a mensagem recebida
    -> repete a etapa atual sem interpretar a resposta
    -> persiste a resposta do bot e o contexto final
    -> followup_stage muda de 1 para 0
```

Não fazem parte desta versão:

- segundo follow-up após 14 horas;
- terceiro follow-up após 21 horas;
- transições produzidas pelo `worker_followup` de `1 -> 2` ou `2 -> 3`;
- recuperação em rajada de lembretes atrasados;
- textos adicionais ainda não aprovados;
- alterações futuras no modelo de identidade recebido da Meta.

Quando novos lembretes forem estudados e aprovados, este plano deverá ser revisado antes da implementação.

## Ordem da implementação

Embora os dois componentes sejam entregues juntos na V1.1.1, a ordem de construção deve ser:

1. implementar e testar o `worker_followup` sem ativá-lo em produção;
2. adaptar e testar o `worker_flow` para tratar `followup_stage > 0`;
3. validar a integração e a concorrência entre os dois workers;
4. implantar as duas partes;
5. reiniciar o `worker_flow` atualizado;
6. somente então habilitar e iniciar o novo serviço de follow-up.

O `worker_followup` não pode ser ativado enquanto o `worker_flow` em produção ainda não souber repetir a etapa e zerar o ciclo. Escrever o novo worker primeiro é uma ordem de desenvolvimento, não uma autorização para iniciá-lo isoladamente.

---

# Estado atual da V1.1.0

## 1. Serviços e responsabilidades existentes

A implantação atual possui três serviços systemd independentes:

- `chatbot-webhook.service`;
- `chatbot-worker-flow.service`;
- `chatbot-worker-funil.service`.

O aplicativo Django `callback/monitoramento` é servido pelo mesmo processo web do webhook. Ele não é um worker nem um quarto orquestrador.

O `worker_followup` será o quarto serviço da implantação. Seu laço de execução ficará em `workers/worker_followup/`, enquanto SQL permanecerá em `core/repositories/` e chamadas à Meta permanecerão em `core/integrations/whatsapp/`.

## 2. Estrutura de banco já disponível

A tabela `chatbot.conversa` já possui:

- `last_interaction_at`;
- `last_message_from`;
- `followup_stage`, com valor padrão `0`;
- `followup_last_sent_at`;
- `processing`;
- `processing_started_at`;
- `lock_version`;
- `turnos_sem_avanco`.

Também já existe `idx_conversa_followup` sobre:

```text
(last_message_from, followup_stage, last_interaction_at)
```

O model Django não gerenciado e o contexto carregado pelo `worker_flow` já expõem os campos de follow-up. A V1.1.0 ainda não usa esses campos para enviar lembretes nem para escolher o comportamento da resposta.

`followup_stage` continua aceitando `NULL` e não possui `CHECK` de faixa no DDL atual. A aplicação deve interpretar `NULL` legado como `0`. O novo worker escreverá somente `0` e `1`.

## 3. Saudação de retorno já implementada

A V1.1.0 já possui a saudação reativa após três horas:

```text
Olá novamente, <nome>!
```

Ela é calculada quando:

- chega uma nova mensagem do cliente;
- a etapa atual é posterior à etapa 1;
- existe nome canônico disponível;
- transcorreram pelo menos três horas desde o último envio confirmado do bot na mesma conversa.

Essa saudação:

- não é uma mensagem proativa;
- não cria um ciclo de follow-up;
- não altera validação, tratamento ou transição;
- é prefixada uma única vez à resposta normal do fluxo;
- é persistida exatamente como foi enviada;
- não é aplicada na etapa 1 nem quando o nome ou os timestamps necessários estão ausentes.

A V1.1.1 deve preservar esse comportamento quando `followup_stage = 0`.

## 4. Proteções existentes que permanecem obrigatórias

A nova funcionalidade é aditiva. Ela não pode enfraquecer:

- a ordenação das mensagens da fila;
- o bloqueio comercial de 30 dias;
- a denylist e os bloqueios da Meta;
- as proteções de flood aplicáveis;
- o isolamento por unidade;
- o lock da conversa com `lock_version`;
- a tolerância atual de 110 segundos para lock stale;
- a idempotência baseada no histórico;
- os checkpoints, commits, rollbacks e retries existentes;
- a autocura do contexto;
- a persistência do conteúdo realmente enviado ao cliente.

---

# Parte 1 — novo `worker_followup`

## 1. Responsabilidade exclusiva

O `worker_followup` deve executar apenas este fluxo de negócio:

1. localizar conversas ativas cujo último remetente confirmado é o bot;
2. identificar aquelas com sete horas ou mais sem resposta do cliente;
3. aplicar novamente todos os guards depois de adquirir o lock;
4. enviar a mensagem aprovada;
5. persistir o histórico do envio;
6. alterar `followup_stage` de `0` para `1`;
7. permanecer em silêncio enquanto o stage continuar positivo.

O worker não deve:

- interpretar mensagens do cliente;
- validar respostas de etapa;
- avançar ou retroceder etapa;
- executar tratamentos;
- atualizar respostas da triagem;
- incrementar `turnos_sem_avanco`;
- criar efeitos de transição;
- enviar dados ao funil;
- encerrar ou reabrir conversa;
- zerar `followup_stage`;
- enviar um segundo lembrete no mesmo período contínuo sem resposta.

O reset pertence exclusivamente ao `worker_flow` depois da reação do cliente e da repetição persistida da etapa.

## 2. Máquina de estados da V1.1.1

| `followup_stage` | Significado | Ação do `worker_followup` |
|---:|---|---|
| `NULL` | Estado legado equivalente a zero | Normalizar como `0` durante a leitura |
| `0` | Nenhum follow-up ativo | Pode enviar o único lembrete após sete horas |
| `1` | Lembrete já enviado; aguardando reação | Não enviar mais nada |
| maior que `1` | Estado não produzido pela V1.1.1 | Não enviar; registrar anomalia |
| negativo ou inválido | Corrupção de estado | Falhar fechado e alertar |

A única transição produzida pelo `worker_followup` é:

```text
0 -> 1
```

A transição de retorno pertence ao `worker_flow`:

```text
1 -> 0
```

Para recuperação segura, o `worker_flow` tratará qualquer valor positivo como ciclo ativo. Entretanto, o novo worker jamais usará essa tolerância para criar `2` ou `3`.

Quando o valor observado for `NULL`, a transição precisa normalizá-lo para `1` de forma condicionada na mesma persistência do envio. Não basta tratá-lo como zero apenas em memória e depois executar um `UPDATE` que aceite exclusivamente o valor literal `0`.

## 3. Relógio de sete horas

### 3.1 Referência do primeiro follow-up

O vencimento é calculado a partir da última mensagem confirmada do bot que deixou a conversa aguardando uma resposta do cliente:

```text
agora_do_banco >= horario_ultima_mensagem_bot + 7 horas
```

Regras obrigatórias:

1. a conversa deve continuar com `followup_stage = 0`;
2. `last_message_from` deve continuar igual a `bot`;
3. a mensagem de referência deve pertencer à mesma conversa;
4. o histórico deve indicar `quem_enviou = 'bot'` e `status_envio = 'sent'`;
5. exatamente sete horas já torna a conversa elegível;
6. timestamps devem ser comparados como `TIMESTAMPTZ`;
7. o relógio do PostgreSQL deve ser a referência comum;
8. horário futuro, intervalo negativo ou contexto incompleto deve cancelar o envio e gerar diagnóstico.

`last_interaction_at` pode apoiar a seleção inicial. A releitura protegida deve confirmar a mensagem de referência e o estado real antes do envio.

### 3.2 Atraso operacional

Se o worker ficar desligado e retornar depois do vencimento, poderá enviar o único follow-up na próxima rodada elegível.

Ele não deve compensar o atraso com mensagens adicionais. Depois que o primeiro envio for confirmado e o stage chegar a `1`, não existe novo prazo enquanto o cliente permanecer em silêncio.

### 3.3 Novo ciclo

Depois que o cliente responder e o `worker_flow` repetir a etapa com sucesso, `followup_stage` volta para `0`. A mensagem repetida pelo bot passa a ser a nova referência ordinária.

Se o cliente ficar novamente sete horas sem responder essa etapa repetida, começa um novo ciclo e um novo único follow-up poderá ser enviado.

Assim, o limite é de um follow-up por período contínuo sem reação, e não de um follow-up durante toda a vida da conversa.

## 4. Mensagem aprovada

O único texto proativo da V1.1.1 é exatamente:

```text
Você viu a minha mensagem?
```

Regras de apresentação e persistência:

- enviar como mensagem de texto;
- preservar acentuação, maiúsculas e ponto de interrogação;
- não acrescentar nome, saudação, rodapé ou explicação;
- não anexar botões;
- não alterar a mensagem original da etapa que permanece aguardando resposta;
- persistir em `historico_mensagens.conteudo_texto` exatamente o conteúdo enviado;
- registrar o tipo compatível com texto, remetente `bot` e envio confirmado como `sent`;
- associar o histórico à conversa, unidade e etapa atuais.

O texto deve ficar no catálogo de mensagens da integração WhatsApp, conforme o padrão arquitetural. Não deve ser declarado diretamente no laço do worker nem dentro de um repositório SQL.

## 5. Elegibilidade de uma conversa

Uma conversa somente pode ser candidata se, na seleção inicial e novamente depois do lock:

1. estiver ativa;
2. possuir cliente e unidade válidos;
3. possuir etapa atual válida;
4. possuir configuração de envio válida para a unidade;
5. não estiver encerrada nem em finalização;
6. não estiver sob bloqueio comercial vigente;
7. não estiver sob bloqueio da Meta, denylist ou outra proibição aplicável;
8. possuir `last_message_from = 'bot'`;
9. possuir `followup_stage` igual a `0` ou `NULL` normalizável;
10. possuir último envio confirmado do bot com pelo menos sete horas;
11. não possuir mensagem posterior do cliente no histórico;
12. não possuir mensagem inbound pendente ou em processamento;
13. possuir destinatário atual resolvido com segurança na unidade correta;
14. não estar sob lock atual de outro worker.

A consulta inicial serve apenas para encontrar candidatas. Nenhum resultado autoriza o envio sem releitura depois da aquisição do lock.

### 5.1 Mensagem inbound ainda sem `id_conversa`

Na V1.1.0, uma mensagem pode estar na fila antes de ter sido vinculada à conversa pelo `worker_flow`. Portanto, procurar apenas por `fila_mensagens.id_conversa` não é suficiente.

O guard deve considerar:

- o vínculo por `id_conversa`, quando já existir; e
- a identidade atual do cliente dentro da unidade, quando a fila ainda não estiver vinculada.

Se houver qualquer inbound compatível já comprometido no banco, o follow-up deve ser cancelado para que o `worker_flow` tenha prioridade.

## 6. Seleção e fronteira dos repositórios

Todo SQL da funcionalidade deve ficar em `core/repositories/`, organizado pelo domínio de atendimento/follow-up. O worker recebe cursores e coordena o ciclo, mas não contém SQL embutido.

A seleção deve:

- usar consulta parametrizada;
- limitar o lote;
- ordenar pela conversa vencida há mais tempo;
- evitar lock de tabela;
- não manter uma transação ampla enquanto examina candidatas que não serão processadas;
- permitir que cada conversa seja revalidada e processada isoladamente.

O índice `idx_conversa_followup` já existente pode apoiar a busca por stage zero. A consulta real deve ser validada com `EXPLAIN` durante a implementação. Um novo índice só deve ser criado se essa medição demonstrar necessidade.

O PostgreSQL é a fonte da verdade. Redis não deve decidir vencimento, stage, envio realizado ou reset. O estado precisa ser reconstruível depois de reinício ou perda completa do cache.

## 7. Fluxo seguro de processamento

Para cada candidata:

1. identificar `id_conversa` e a referência do ciclo;
2. adquirir o mesmo lock versionado usado pelo `worker_flow`;
3. respeitar lock com menos de 110 segundos;
4. realizar takeover somente quando o lock estiver stale conforme o contrato atual;
5. guardar o `lock_version` obtido;
6. reler conversa, cliente, unidade, etapa e bloqueios;
7. confirmar novamente `followup_stage = 0`;
8. confirmar novamente `last_message_from = 'bot'`;
9. confirmar o vencimento de sete horas;
10. procurar inbound pendente, em processamento ou já persistido depois da referência;
11. construir a chave idempotente do único follow-up do ciclo;
12. procurar comprovação local de envio anterior para a mesma chave;
13. confirmar a posse do lock imediatamente antes da chamada externa;
14. enviar `Você viu a minha mensagem?` pela integração central;
15. persistir o histórico e a transição condicionada `0 -> 1`;
16. atualizar os campos normais da última mensagem do bot;
17. efetuar commit;
18. liberar o lock somente se ainda possuir o mesmo `lock_version`.

Se qualquer requisito mudar durante a releitura, a candidata deve ser abandonada sem envio e sem alteração de stage.

## 8. Persistência atômica do envio

Depois que a Meta confirmar o envio, a persistência local deve tratar como uma única unidade lógica:

- histórico da mensagem do bot;
- `followup_stage = 1`;
- `followup_last_sent_at` com o horário confirmado no banco;
- `last_message_from = 'bot'`;
- `last_interaction_at` conforme o contrato vigente para toda saída do bot;
- identidade idempotente do follow-up;
- manutenção de `id_etapa_atual`;
- manutenção de `turnos_sem_avanco`;
- ausência de transição e de efeitos de negócio.

A alteração deve ser condicionada ao estado observado:

```text
atualizar conversa
   de COALESCE(followup_stage, 0) = 0
   para followup_stage = 1
 somente se:
   a conversa continua ativa,
   o último remetente continua sendo o bot,
   não existe inbound posterior,
   e o lock_version ainda pertence ao worker
```

O número de linhas afetadas deve ser exatamente um. Zero indica mudança de contexto ou perda de posse e exige reconciliação; nunca autoriza um segundo envio automático.

O `worker_followup` não possui nenhuma operação que grave `followup_stage = 0`.

## 9. Idempotência na fronteira Meta/PostgreSQL

O envio HTTP e o commit no PostgreSQL não formam uma transação distribuída. O caso crítico continua sendo:

1. a Meta aceita a mensagem;
2. o processo cai antes da comprovação local;
3. uma nova rodada ainda encontra `followup_stage = 0`.

Cada ciclo precisa de uma identidade determinística anterior ao envio. A âncora recomendada é a mensagem ordinária do bot que iniciou a espera de sete horas:

```text
followup:{id_conversa}:{ancora_ultima_resposta_bot}:1
```

Requisitos da identidade:

- ser estável durante retries;
- distinguir conversas diferentes;
- distinguir ciclos diferentes da mesma conversa;
- sobreviver ao reinício do processo;
- permitir consulta antes de novo despacho;
- impedir mais de uma comprovação local para o mesmo follow-up lógico.

O plano prático deverá verificar se a estrutura atual de histórico comporta essa identidade sem ambiguidade. Uma coluna ou tabela nova somente deve ser proposta se os campos atuais não oferecerem uma restrição local segura. Não se deve sobrecarregar um campo com semântica incompatível apenas para evitar uma migração.

Quando a comprovação local existe, o retry não pode reenviar. Ainda permanece a pequena janela em que a Meta aceitou a chamada e o processo caiu antes de gravar qualquer evidência. Sem uma chave idempotente aceita pelo endpoint externo ou um protocolo adicional de reconciliação, não é correto prometer entrega exatamente uma vez.

## 10. Concorrência com o `worker_flow`

Os dois workers usam o mesmo lock de conversa. Não deve existir um lock paralelo exclusivo para follow-up.

### 10.1 `worker_flow` obtém o lock primeiro

1. O cliente já enviou uma mensagem.
2. O `worker_flow` adquire o lock e registra/processa o evento.
3. Ao obter o lock posteriormente, o `worker_followup` relê o estado.
4. Ele encontra mudança de remetente, histórico ou fila e cancela o envio.

### 10.2 `worker_followup` obtém o lock primeiro

1. O `worker_followup` confirma ausência de inbound.
2. Envia e persiste o lembrete.
3. Altera o stage de `0` para `1`.
4. Libera o lock.
5. Quando o cliente reage, o `worker_flow` relê stage positivo e executa a repetição obrigatória.

### 10.3 Inbound chega durante o despacho

O lock da conversa não impede o webhook de receber e enfileirar uma nova mensagem. Uma entrada comprometida antes da checagem final deve cancelar o follow-up.

Se a mensagem chegar depois que a chamada externa já começou, pode ocorrer o cruzamento inevitável entre o lembrete e a reação do cliente. A entrada nunca pode ser perdida: o `worker_flow` deverá processá-la depois e, encontrando `followup_stage = 1`, repetir a etapa e zerar o ciclo.

## 11. Fencing e lock stale

O contrato continua igual ao da V1.1.0:

- antes de 110 segundos, outro worker não toma a conversa;
- a partir de 110 segundos, o lock pode ser recuperado;
- o takeover produz uma nova versão;
- persistência e unlock conferem o `lock_version` possuído;
- um processo antigo não pode alterar o stage nem liberar o lock da nova versão.

O fencing do banco não cancela uma chamada Meta já iniciada. Confirmar a posse imediatamente antes do envio e condicionar a persistência reduz o risco, mas não elimina toda sobreposição externa quando um processo excede o tempo do lease.

## 12. Falhas e recuperação

### 12.1 Falha antes do envio

- não cria histórico do bot;
- não altera `followup_stage`;
- não altera `followup_last_sent_at`;
- libera o lock se ainda for o proprietário;
- permite nova tentativa em uma rodada futura.

### 12.2 Falha do sender

- mantém stage zero;
- registra o erro conforme a política operacional;
- não simula sucesso no histórico;
- não inicia um estado de espera por reação.

### 12.3 Meta confirmou e o banco falhou

- se houver comprovação local, a identidade impede reenvio;
- sem comprovação local, permanece a janela residual de possível duplicidade;
- o retry não inventa stage, timestamp ou sucesso;
- uma atualização condicionada nunca incrementa o stage duas vezes.

### 12.4 Falha no unlock

- o lock não fica permanente;
- depois de 110 segundos pode ocorrer takeover;
- `lock_version` impede o proprietário antigo de liberar a nova posse.

### 12.5 Estado inesperado

- `followup_stage = 1`: não enviar;
- `followup_stage > 1`: não enviar e alertar;
- stage negativo ou inválido: falhar fechado;
- conversa sem etapa, cliente, unidade ou destinatário seguro: não enviar;
- timestamps incompatíveis: não adivinhar o vencimento.

## 13. Unidades, bloqueios e destinatário

O ciclo pertence à conversa e, portanto, ao vínculo entre cliente e unidade. Ele não é global por cliente.

Antes do envio, o worker deve consultar as fontes canônicas atuais para:

- status da conversa;
- status e configuração da unidade;
- bloqueio comercial;
- bloqueios Meta/denylist;
- proteções de flood aplicáveis;
- destinatário do cliente;
- `phone_number_id` correto da unidade.

Uma conversa em uma unidade não deve interferir no ciclo de outra unidade. Nenhuma consulta pode selecionar uma conversa somente pelo telefone sem considerar o vínculo com a unidade.

## 14. Reflexo no monitoramento

O painel de monitoramento da V1.1.0 é somente leitura e continua isolado pela unidade vinculada ao usuário autenticado.

O follow-up deve aparecer no histórico como uma mensagem normal enviada pelo bot, com o texto exato e o horário real. Por consequência:

- entra na contagem geral de mensagens;
- aparece na conversa atualizada pelo painel;
- não altera funil, nota, perfil ou etapa;
- não exige controle de escrita no monitoramento;
- não precisa de indicador visual especial nesta primeira entrega.

Caso seja desejada uma métrica exclusiva de follow-up no futuro, ela deve ser planejada sem inferir mensagens apenas pelo conteúdo textual.

## 15. Estrutura operacional esperada

A implementação deve respeitar as fronteiras atuais:

```text
workers/worker_followup/                   -> laço, orquestração e estado do ciclo
core/repositories/atendimento/             -> seleção e persistência SQL
core/integrations/whatsapp/messages/       -> texto aprovado
core/integrations/whatsapp/pywa_functions/ -> envio externo compartilhado
deploy/systemd/                            -> chatbot-worker-followup.service
tests/                                     -> contratos unitários e de integração
```

O serviço systemd deve seguir o endurecimento dos workers atuais:

- usuário e grupo `chatbot`;
- `EnvironmentFile=/etc/chatbot/chatbot.env`;
- `PYTHONPATH=/opt/chatbot/app`;
- reinício automático;
- desligamento gracioso por `SIGTERM`;
- logs no journal;
- mesmas restrições de sistema aplicáveis aos outros workers.

O intervalo entre varreduras é configuração operacional. Ele não muda a regra de negócio: a conversa nunca fica elegível antes de completar sete horas no relógio do banco.

## 16. Observabilidade

Logs estruturados devem registrar somente os identificadores técnicos necessários:

- `id_conversa`;
- `id_cliente`;
- `id_unidade`;
- stage observado e stage pretendido;
- horário de referência e vencimento;
- motivo de seleção ou descarte;
- presença de inbound pendente;
- resultado do lock e `lock_version`;
- chave idempotente;
- resultado do sender;
- resultado da persistência;
- duração do processamento.

Métricas úteis:

- candidatas examinadas;
- conversas ainda não vencidas;
- follow-ups enviados;
- conversas ignoradas por stage positivo;
- descartes por inbound pendente;
- descartes por bloqueio, encerramento ou unidade inválida;
- conflitos e takeovers de lock;
- falhas de envio;
- falhas de persistência depois do envio;
- reações processadas pelo `worker_flow`.

Logs não devem expor telefone, nome ou conteúdo integral sem necessidade operacional.

## 17. Critérios de aceite do `worker_followup`

A implementação deve demonstrar, no mínimo:

1. Com 6h59min59s não envia follow-up.
2. Com exatamente sete horas a conversa pode ser selecionada.
3. O texto enviado é exatamente `Você viu a minha mensagem?`.
4. O envio confirmado e persistido altera `followup_stage` de `0` para `1`.
5. O envio registra `followup_last_sent_at` e histórico `sent`.
6. Stage `NULL` legado pode iniciar o envio e é persistido como `1` sem ambiguidade.
7. Com stage `1`, não envia depois de mais sete horas, 14 horas, 21 horas ou qualquer outro intervalo.
8. O worker jamais grava stage `2` ou `3`.
9. Sem reação do cliente, stage `1` permanece estável.
10. Uma nova mensagem do cliente anterior ao lock cancela o envio.
11. Uma inbound pendente ou em processamento cancela o envio.
12. Conversa encerrada, bloqueada ou sem etapa não recebe follow-up.
13. Unidade inativa ou sender inválido impede o envio.
14. Falha antes ou durante o sender mantém stage zero.
15. Follow-up não altera etapa, triagem, `turnos_sem_avanco`, funil ou encerramento.
16. Dois processos concorrentes produzem uma única transição local e um único envio comprovado fora da janela externa residual.
17. Lock atual é respeitado.
18. Lock stale pode ser recuperado com nova versão.
19. Worker antigo não altera stage nem libera lock depois de perder a versão.
20. Retry com comprovação local não reenvia.
21. A janela entre aceite externo e comprovação local permanece testada e documentada.
22. Stage maior que `1` não gera envio e produz diagnóstico.
23. Conversas do mesmo cliente em unidades diferentes permanecem isoladas.
24. O histórico permite que o painel mostre e contabilize o follow-up.
25. Reinício do processo não apaga nem reinicia o ciclo persistido.

---

# Parte 2 — adaptação do `worker_flow`

## 1. Responsabilidade do `worker_flow`

O `worker_flow` continua sendo o único responsável por interpretar novas mensagens do cliente. A adaptação adiciona uma bifurcação baseada no stage confirmado da conversa:

| Estado observado | Interpretação | Comportamento |
|---|---|---|
| `followup_stage = 0` e inatividade menor que 3 horas | Resposta normal | Preserva o fluxo atual sem saudação de retorno |
| `followup_stage = 0` e inatividade igual ou superior a 3 horas | Retorno espontâneo | Preserva validação e transição, com a saudação atual da V1.1.0 |
| `followup_stage > 0` | Reação depois de follow-up | Registra a entrada, ignora seu conteúdo para o negócio, repete a etapa atual e zera o ciclo no contexto final |

`NULL` legado é interpretado como `0`.

O `worker_flow` deve tratar qualquer valor positivo como follow-up ativo para recuperação segura, embora o novo worker produza somente `1`. Valor negativo ou estruturalmente inválido deve falhar fechado.

## 2. Caminho A — `followup_stage = 0`

Este caminho permanece igual ao da V1.1.0.

### 2.1 Menos de três horas

- valida a resposta normalmente;
- escolhe transição ou tratamento normalmente;
- atualiza `turnos_sem_avanco` conforme as regras atuais;
- não acrescenta saudação de retorno.

### 2.2 Três horas ou mais

- valida a resposta normalmente;
- preserva o tratamento ou a transição decidida;
- usa a saudação existente `Olá novamente, <nome>!` quando a etapa e os dados permitem;
- persiste exatamente o conteúdo enviado;
- não altera `followup_stage` por causa do tempo.

Mesmo que tenham passado mais de sete horas, stage zero não prova que um follow-up foi enviado. Se o serviço estava desligado, atrasado ou recusou a candidata por algum guard, o retorno continua sendo processado normalmente.

## 3. Caminho B — `followup_stage > 0`

Este caminho somente existe quando o cliente realmente enviou uma mensagem depois que o banco registrou um follow-up.

Quando o stage confirmado for positivo, o `worker_flow` deve:

1. preservar os guards operacionais e de segurança;
2. registrar normalmente a mensagem recebida no histórico;
3. manter a correlação da resposta com o item da fila;
4. ignorar o conteúdo recebido para validação de negócio nesse processamento;
5. não executar os validadores da etapa;
6. não escolher tratamento;
7. não produzir evento de transição;
8. não avançar nem retroceder etapa;
9. não modificar profissão, dependente, e-mail, triagem ou satisfação;
10. não incrementar nem zerar `turnos_sem_avanco`;
11. não executar efeitos de funil ou encerramento derivados da resposta;
12. renderizar e enviar novamente a etapa atual;
13. persistir a mensagem repetida e o contexto final;
14. somente nessa persistência final alterar `followup_stage` para `0`.

A resposta do cliente pode ser texto, botão, emoji, mídia, “sim”, “oi”, “voltei” ou qualquer conteúdo permitido pelo webhook. Para o fluxo de negócio, o conteúdo não responde à etapa neste primeiro processamento.

Depois da repetição e do reset, a próxima mensagem do cliente volta a ser interpretada normalmente.

## 4. Relação com a saudação de três horas

Os dois caminhos são mutuamente exclusivos:

- stage zero usa a regra atual de três horas;
- stage positivo usa a repetição obrigatória da etapa.

A reação a um follow-up não deve receber também a saudação `Olá novamente, <nome>!`. O próprio lembrete já estabeleceu o retorno e a resposta do bot deve concentrar-se em recolocar a pergunta atual no contexto.

Assim, a saída conceitual do caminho de follow-up é:

```text
{mensagem existente da etapa atual}
```

e não:

```text
Olá novamente, <nome>!

{mensagem existente da etapa atual}
```

## 5. Renderização pura da etapa atual

A repetição não deve chamar um resolver que interprete a resposta recém-recebida. Ela precisa de uma rota explícita para “renderizar a etapa atual”, separada de “validar resposta e resolver transição”.

Essa renderização deve:

- usar `conversa.id_etapa_atual` confirmado;
- reutilizar as mensagens oficiais existentes;
- preservar botões, listas, cabeçalhos, rodapés e tipos interativos da etapa;
- consultar dados dinâmicos necessários da conversa e da unidade;
- produzir o mesmo contexto visual que o cliente precisa responder;
- permanecer livre de efeitos colaterais de negócio.

Ela não pode:

- criar transição;
- atualizar respostas da etapa;
- inferir uma resposta válida;
- executar tratamentos;
- incrementar contador de suspeita;
- encerrar conversa;
- disparar funil.

Se não houver etapa atual, se a conversa estiver encerrada ou se a etapa não puder ser renderizada com segurança, o processamento deve falhar fechado. O sistema não deve adivinhar uma etapa nem zerar o follow-up.

## 6. Momento correto para ler o stage

O contexto carregado antes do lock pode ficar desatualizado enquanto o `worker_flow` espera. A decisão deve usar o estado relido depois da aquisição do lock.

Sequência segura:

1. resolver a conversa pelo mecanismo atual;
2. adquirir o lock;
3. guardar o `lock_version`;
4. vincular a fila à conversa;
5. reler status, etapa e `followup_stage` sob proteção;
6. registrar ou recuperar o histórico da entrada;
7. escolher o caminho normal ou de follow-up;
8. enviar e persistir com as condições do estado observado.

Um snapshot anterior ao lock não pode fazer o fluxo escolher o caminho normal quando o `worker_followup` acabou de persistir `followup_stage = 1`.

## 7. Ordem dos guards

A bifurcação por stage não deve contornar proteções existentes. A ordem conceitual permanece:

1. dequeue atômico;
2. espera por mensagem anterior aberta;
3. validação e autocura do contexto;
4. bloqueios e estado da conversa;
5. aquisição do lock;
6. vínculo da fila com a conversa;
7. releitura do estado protegido;
8. histórico e idempotência da entrada;
9. decisão por `followup_stage`;
10. geração e envio da resposta;
11. persistência do contexto final;
12. finalização da fila;
13. liberação do lock com a versão possuída.

Comandos obrigatórios de segurança ou conformidade, caso existam no contrato atual, continuam tendo precedência. O caminho de follow-up não reabre conversa encerrada, não responde a cliente bloqueado e não duplica evento já concluído.

## 8. Reset do ciclo

O esclarecimento funcional central é:

> O tempo não zera o follow-up. O `worker_followup` não zera o follow-up. Somente a reação do cliente, processada com repetição enviada e persistida pelo `worker_flow`, encerra o ciclo.

Na persistência final do caminho positivo, a mesma unidade transacional lógica deve:

- registrar ou recuperar a mensagem repetida do bot;
- manter `id_etapa_atual` inalterado;
- manter `turnos_sem_avanco` inalterado;
- manter dados de negócio inalterados;
- atualizar os campos normais da última saída do bot;
- alterar condicionalmente o stage observado para `0`;
- preservar a posse indicada por `lock_version`.

O reset nunca pode ocorrer:

- quando o follow-up é enviado;
- porque passaram mais sete horas;
- durante uma varredura do `worker_followup`;
- quando a mensagem do cliente apenas entra na fila;
- quando o histórico do cliente é registrado;
- antes da repetição ser enviada;
- se o sender falhar;
- se a persistência final falhar;
- por um worker que perdeu o lock.

`followup_last_sent_at` pode ser preservado como informação operacional. Com stage zero, ele não participa do vencimento do ciclo seguinte, cuja referência passa a ser a nova mensagem ordinária do bot.

## 9. Atualização condicionada

O reset deve verificar o estado exato observado sob lock:

```text
atualizar conversa
   de followup_stage = stage_positivo_observado
   para followup_stage = 0
 somente se:
   a conversa continua ativa,
   a etapa continua sendo a etapa repetida,
   e o lock_version ainda pertence ao worker_flow
```

Uma linha afetada confirma o reset. Zero linhas representa divergência, perda de posse ou mudança concorrente; nesse caso, o worker não deve marcar a fila como concluída até reconciliar o estado.

Essa condição impede que um processo antigo zere um ciclo novo iniciado depois de perder o lock.

## 10. Idempotência e retries do retorno

A V1.1.0 já correlaciona a resposta do bot à mensagem atual da fila por meio do histórico. A nova rota deve preservar esse contrato.

### 10.1 Retry antes do envio da repetição

- stage permanece positivo;
- a mensagem recebida já pode existir no histórico;
- o retry recupera a mesma entrada;
- a etapa continua sem ser validada semanticamente;
- o worker tenta novamente renderizar e enviar a repetição.

### 10.2 Repetição enviada e contexto persistido

- o histórico comprova a resposta do bot para aquele evento;
- stage já está zero na mesma persistência lógica;
- o retry não chama a Meta novamente;
- a mensagem ignorada não é reprocessada como resposta normal apenas porque o stage agora está zero;
- a fila é finalizada pelo mecanismo de recuperação existente.

### 10.3 Meta confirmou e a persistência falhou

Permanece a mesma fronteira conhecida da V1.1.0: se a Meta aceitou a repetição e o processo caiu antes da comprovação local, um retry pode não ter evidência suficiente para impedir outra chamada.

Se o histórico foi persistido, mas uma intervenção ou falha extraordinária deixou o stage positivo, qualquer reparo deve correlacionar a mensagem da fila, a resposta do bot, o stage observado e o `lock_version`. Não basta zerar genericamente toda conversa com stage positivo.

## 11. Concorrência e lock

O `worker_flow` conserva o lock atual de 110 segundos e seu `lock_version`.

Toda nova persistência crítica deve conferir a versão possuída. A tolerância a lock stale não cancela uma chamada externa antiga, portanto a janela rara de sobreposição continua explicitamente reconhecida.

O fluxo não deve criar um lock adicional para o retorno de follow-up. Uma conversa possui um único domínio de exclusão mútua compartilhado pelos workers.

## 12. Novo ciclo depois da reação

Depois que a repetição é confirmada:

```text
followup_stage = 0
last_message_from = 'bot'
last_interaction_at = horario_da_repeticao_confirmada
```

A conversa volta a aguardar uma resposta real para a mesma etapa.

Se o cliente responder, o fluxo interpreta normalmente. Se permanecer em silêncio por mais sete horas, o `worker_followup` poderá enviar novamente o único lembrete em um novo ciclo.

## 13. Observabilidade do `worker_flow`

Os logs da bifurcação devem registrar:

- `id_conversa`, `id_cliente` e `id_unidade`;
- stage confirmado depois do lock;
- caminho escolhido: `normal`, `retorno_3h` ou `resposta_followup`;
- etapa repetida;
- se a entrada foi inserida ou recuperada;
- se a resposta do bot foi enviada ou recuperada;
- stage anterior e resultado do reset;
- `lock_version` usado;
- ausência de transição e de alteração de `turnos_sem_avanco`.

O conteúdo ignorado não precisa ser exposto no log para comprovar a decisão.

## 14. Critérios de aceite do `worker_flow`

A implementação deve demonstrar, no mínimo:

1. Stage zero e menos de três horas preservam o fluxo atual sem saudação.
2. Stage zero e exatamente três horas preservam a saudação `Olá novamente, <nome>!` quando elegível.
3. Stage zero com mais de sete horas continua no caminho normal se nenhum follow-up foi persistido.
4. Stage positivo é confirmado depois do lock.
5. Uma mensagem recebida com stage `1` é registrada no histórico.
6. O conteúdo dessa mensagem não é passado aos validadores de negócio.
7. Uma resposta que seria válida não avança a etapa nesse primeiro processamento.
8. Uma resposta inválida não escolhe tratamento nem incrementa `turnos_sem_avanco`.
9. Texto, botão, emoji e mídia seguem a mesma regra de reação.
10. A etapa atual é repetida com seus botões e conteúdo dinâmico corretos.
11. A repetição não recebe adicionalmente a saudação de três horas.
12. A repetição não cria transição, efeitos, funil ou encerramento.
13. O stage permanece positivo se o sender falhar.
14. O stage permanece positivo se a persistência final falhar.
15. O stage somente vira zero junto da resposta do bot persistida e do contexto final.
16. Retry com resposta persistida não reenvia nem interpreta a entrada ignorada.
17. Stage `2` ou maior, embora anômalo nesta versão, também repete e só zera depois do sucesso.
18. Stage negativo falha fechado.
19. Conversa encerrada, bloqueada ou sem etapa não é repetida nem zerada.
20. Worker que perdeu `lock_version` não zera o ciclo.
21. Depois do reset, a próxima mensagem do cliente é interpretada normalmente.
22. Depois do reset, sete novas horas de silêncio podem iniciar outro ciclo.

---

# Implantação conjunta da V1.1.1

## 1. Sequência segura

O deploy deve respeitar esta dependência:

```text
1. instalar o código completo
2. instalar o arquivo chatbot-worker-followup.service sem iniciá-lo
3. executar verificações e testes de configuração
4. atualizar/reiniciar chatbot-worker-flow.service
5. comprovar que o worker_flow atualizado está ativo
6. habilitar e iniciar chatbot-worker-followup.service
7. validar logs, locks e uma seleção sem envio indevido
```

O serviço novo não deve ser iniciado entre as etapas 2 e 4.

## 2. Desligamento e rollback

Em rollback:

1. parar primeiro o `chatbot-worker-followup.service`;
2. preservar os dados já persistidos;
3. evitar retornar a um `worker_flow` que desconheça stage positivo enquanto existirem conversas em stage `1`;
4. reconciliar essas conversas ou manter temporariamente a versão compatível do fluxo;
5. somente então concluir a reversão.

Parar o serviço não zera ciclos existentes. Stage positivo é estado persistido e precisa continuar sendo entendido pelo `worker_flow` até ser encerrado pela reação do cliente.

---

# Invariantes finais

O desenho completo deve manter permanentemente estas garantias:

1. A V1.1.1 envia no máximo um follow-up por período contínuo sem reação.
2. O texto proativo é exatamente `Você viu a minha mensagem?`.
3. O `worker_followup` produz somente a transição `0 -> 1`.
4. Stage `1` permanece estável enquanto o cliente não responder.
5. Tempo adicional sem resposta nunca produz outro envio nesta versão.
6. O `worker_followup` nunca zera o stage.
7. O `worker_flow` somente zera o stage depois de receber uma mensagem do cliente, repetir a etapa e persistir o contexto final.
8. Uma resposta com stage positivo nunca avança de etapa no primeiro processamento.
9. A reação é armazenada, mas não é usada para validação de negócio.
10. A repetição causada pelo follow-up não altera `turnos_sem_avanco`.
11. A saudação atual de três horas continua exclusiva do caminho com stage zero.
12. `followup_stage` é a fonte de verdade; tempo sozinho não comprova envio.
13. Os dois workers usam o mesmo lock e condicionam suas transições ao `lock_version` possuído.
14. Inbound já comprometido no banco tem prioridade sobre um follow-up ainda não despachado.
15. Histórico, stage e campos da conversa refletem somente envios confirmados localmente.
16. Retry não reenvia quando existe comprovação local suficiente.
17. A janela entre aceite da Meta e commit PostgreSQL permanece reconhecida, sem promessa de entrega exatamente uma vez.
18. Follow-up é isolado por conversa e unidade.
19. Bloqueios, encerramentos e configuração da unidade continuam tendo precedência.
20. O estado confirmado é reconstruível pelo PostgreSQL e não depende de memória ou Redis.
21. A mensagem aparece no monitoramento como histórico normal do bot, sem conceder qualquer ação ao usuário do painel.
22. O novo serviço só é ativado depois que o `worker_flow` compatível estiver implantado.
