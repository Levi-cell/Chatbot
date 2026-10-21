# V1.5 - LISTEN/NOTIFY no worker de atendimento

## Status

Estrategia aprovada para avaliacao na V1.5. Nao faz parte do deploy inicial da
V1 e nao deve alterar as regras atuais de fila, turno, retry, idempotencia,
locks, historico ou transicao de etapas.

## Objetivo

Substituir o polling vazio frequente do `worker_flow` por um mecanismo orientado
a eventos, mantendo o PostgreSQL como fonte duravel da verdade.

```text
mensagem inserida na fila
-> transacao confirma o INSERT
-> PostgreSQL emite NOTIFY
-> worker acorda
-> worker executa o dequeue existente
```

O `NOTIFY` sera apenas um sinal para acordar o worker. IDs, conteudo, status e
controle de concorrencia continuarao armazenados na tabela
`chatbot.fila_mensagens`.

## Limites que precisam ser preservados

O estado atual possui mais de um prazo de recuperacao:

```text
reagendamento por ordem de turno: 30 segundos
erro normal de processamento:      2 minutos
processing abandonado:             2 minutos
```

Por isso, um timeout fixo de dois minutos nao preservaria integralmente a
latencia atual do reagendamento de turno. A espera devera ser dinamica.

## Arquitetura recomendada

```text
webhook
-> grava a mensagem
-> emite NOTIFY na mesma transacao
-> responde HTTP sem executar o atendimento

worker_flow independente
-> mantem uma conexao dedicada ao LISTEN
-> processa imediatamente ao receber NOTIFY
-> aguarda o prazo exato do proximo item agendado
-> executa uma varredura rara de seguranca
```

Webhook e worker permanecem em processos separados. O listener nao deve ser
iniciado dentro do processo Gunicorn/Django, porque reinicios e multiplos
workers web poderiam criar consumidores duplicados ou interromper um
atendimento em andamento.

## Ciclo do listener

```text
1. Abrir conexao dedicada.
2. Executar LISTEN e confirmar a transacao.
3. Consultar a fila antes da primeira espera.
4. Drenar todas as mensagens que ja estejam elegiveis.
5. Descobrir o prazo elegivel mais proximo.
6. Aguardar ate ocorrer um dos eventos:
   - chegou um NOTIFY;
   - chegou o horario do proximo next_attempt_at;
   - venceu o lease de um processing;
   - chegou a varredura rara de seguranca.
7. Voltar ao passo 4.
```

O prazo de espera devera considerar, no minimo:

```text
MIN(next_attempt_at) para registros pending
MIN(processing_started_at + 2 minutos) para registros processing
```

Assim, uma mensagem reagendada para 30 segundos acorda o worker em 30 segundos;
uma falha reagendada para dois minutos acorda em dois minutos.

## Notificacoes de retry

Quando uma mensagem falhar, a transacao podera emitir um novo `NOTIFY` contendo
somente informacoes pequenas, como:

```text
tipo do evento
id_mensagem
next_attempt_at
```

Essa notificacao acontece no momento do reagendamento, nao dois minutos depois.
Ela serve para o worker recalcular seu timer local. O horario futuro continua
registrado no banco.

## Varredura de seguranca

`LISTEN/NOTIFY` nao e uma fila duravel. Uma notificacao pode ser perdida quando
o listener estiver desconectado. Alem disso, um processo que morreu enquanto
mantinha uma mensagem em `processing` nao consegue notificar a propria queda.

Deve existir uma varredura de seguranca rara, inicialmente a cada cinco
minutos. Ela deve usar o mesmo dequeue atual e nao criar um segundo fluxo de
processamento.

O prazo da varredura deve usar um relogio absoluto. Receber muitas notificacoes
nao pode reiniciar indefinidamente a contagem e impedir a recuperacao de itens
abandonados.

## Reconexao

Ao perder a conexao do listener:

```text
fechar conexao invalida
-> aplicar o backoff atual de conexao
-> abrir nova conexao
-> executar LISTEN e COMMIT
-> consultar a fila imediatamente
-> somente depois voltar a aguardar eventos
```

A consulta imediatamente apos a reconexao recupera mensagens inseridas durante
o periodo em que nenhuma sessao estava ouvindo o canal.

## Garantias mantidas

- PostgreSQL continua sendo a fila duravel.
- `dequeue_message()` continua selecionando apenas itens elegiveis.
- `FOR UPDATE SKIP LOCKED` continua protegendo concorrencia.
- `retry_count`, `next_attempt_at` e o lease de `processing` permanecem ativos.
- Regras de turno e idempotencia nao mudam.
- Redis nao passa a ser fila nem fonte de verdade.
- Uma notificacao duplicada apenas provoca uma nova consulta segura.
- Uma notificacao perdida e reparada pela consulta de inicializacao, reconexao
  ou varredura de seguranca.

## Relacao com o worker do Funil

Esta estrategia pertence somente ao `worker_flow` continuo.

O `worker_funil` nao precisa de `LISTEN/NOTIFY`: na V1 ele deve executar um unico
ciclo e encerrar, sendo chamado de hora em hora por um `systemd timer`. O timer
do Funil e uma decisao do deploy atual, nao uma dependencia desta melhoria da
V1.5.

## Cenarios obrigatorios antes de aplicar

1. Mensagem nova acorda o worker imediatamente.
2. Reagendamento de turno volta em aproximadamente 30 segundos.
3. Erro de processamento volta depois de dois minutos.
4. `processing` abandonado volta a ser elegivel depois de dois minutos.
5. NOTIFY duplicado nao duplica resposta.
6. Worker desconectado durante um INSERT recupera a mensagem ao reconectar.
7. Queda entre Meta e banco continua seguindo as regras transacionais atuais.
8. Fluxos A/B/C de queda continuam produzindo os mesmos resultados.
9. Trafego continuo nao impede a varredura de seguranca.
10. Reinicio do servidor recupera toda mensagem pendente sem depender de um
    evento novo.

## Resultado esperado

```text
fila vazia
-> worker aguarda sem consultar o banco a cada cinco segundos

mensagem nova
-> resposta com baixa latencia por NOTIFY

retry futuro
-> timer acorda exatamente no prazo salvo

notificacao perdida ou processo morto
-> varredura rara ou reconexao recupera o trabalho
```
