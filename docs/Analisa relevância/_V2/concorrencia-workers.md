# Concorrência e Workers - V2

## Objetivo

Registrar como a V2 deve evoluir de um worker ativo para múltiplos workers sem
quebrar a regra central de turno do cliente.

## Regra da V1

Na V1, a implantação deve manter apenas um worker ativo. Mesmo assim, o código já
possui proteções importantes contra concorrência:

- `dequeue_message()` com reserva de mensagem;
- status `pending` e `processing`;
- timeout para mensagem travada;
- lock de conversa;
- `unlock_conversa` com versão;
- `reagendar_se_houver_mensagem_anterior`;
- idempotência por histórico do bot vinculado à mensagem da fila;
- `sent` como última etapa do ciclo.

### Limite aceito na V1: retomada da mesma mensagem

O lock lógico da conversa pode ser retomado após 110 segundos, enquanto uma
mensagem em `processing` volta a ser elegível no dequeue após 2 minutos. Essa
diferença permite recuperação automática quando um worker morre sem executar o
unlock.

Existe, porém, uma janela residual já aceita na V1: se o worker antigo não
morreu e apenas ficou suspenso por mais de 2 minutos, outro worker pode retomar
a mesma mensagem e adquirir uma nova versão do lock. O `lock_version` impede o
worker antigo de liberar o lock novo, mas ainda não funciona como *fencing
token* para impedir todas as escritas ou um envio tardio do worker antigo.

A implantação V1 reduz esse risco mantendo apenas um worker ativo. Antes de
habilitar múltiplos workers, avaliar um token de posse da fila, heartbeat,
fencing nas escritas ou lock de sessão.

## Ideia Central para V2

A V2 pode ter múltiplos workers, mas a regra por conversa continua simples:

```text
Permitido:
cliente/unidade A processando em um worker
cliente/unidade B processando em outro worker

Não permitido:
duas mensagens da mesma conversa avançando etapa ao mesmo tempo
```

Ou seja, a V2 deve permitir paralelismo entre conversas diferentes, mas preservar
ordem e exclusividade dentro da mesma conversa.

## O Que Deve Continuar Valendo

Mesmo com vários workers:

- uma conversa não pode retroceder etapa;
- uma conversa não pode saltar mais de uma etapa;
- uma mensagem não pode gerar duas respostas por falha externa comum;
- uma mensagem respondida, mas ainda não marcada como `sent`, deve ser
  reconhecida em retry;
- uma mensagem mais nova não deve passar uma mais antiga aberta sem controle;
- o webhook não deve criar bola de neve de mensagens do mesmo cliente/unidade.

## Cenário A/B/C que Deve Continuar Protegido

Fluxo desejado:

```text
1. Cliente envia A.
2. Worker responde A.
3. O bot grava a resposta no histórico.
4. O worker cai antes de marcar A como sent.
5. Cliente envia B.
6. Webhook pode aceitar B porque A já tem resposta do bot vinculada.
7. B ainda sem resposta bloqueia C, D e próximas mensagens.
8. Retry de A reconhece a resposta existente e marca A como sent.
9. B processa depois, sem duplicar A.
```

Esse comportamento deve permanecer quando houver múltiplos workers.

## Tarefas Futuras

Antes de habilitar múltiplos workers:

- testar concorrência com PostgreSQL real;
- testar Redis real;
- simular worker morrendo antes e depois dos commits;
- simular Meta falhando no envio;
- simular banco falhando após envio Meta;
- medir tempo de lock e timeout;
- revisar logs para rastrear corrida;
- documentar número seguro de workers por volume.

## Critério de Aceite da V2

A V2 só deve habilitar múltiplos workers quando os testes provarem:

- nenhum turno válido é ignorado por corrida;
- nenhuma etapa retrocede;
- nenhuma etapa salta indevidamente;
- mensagens duplicadas continuam raras e rastreáveis;
- mensagens de clientes diferentes podem processar em paralelo;
- mensagens da mesma conversa continuam serializadas.
