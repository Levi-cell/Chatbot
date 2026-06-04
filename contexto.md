# Contexto - responsabilidades do webhook e do worker

## Decisao principal

O webhook deve ser um porteiro leve e barato.

O worker deve ser o cerebro do fluxo da conversa.

## Webhook

O webhook nao deve interpretar etapa, historico ou `last_message_from`.

Responsabilidades do webhook:

- validar Content-Type;
- validar tamanho do body;
- validar assinatura Meta;
- fazer parse do JSON;
- aplicar anti-flood;
- validar unidade ativa;
- validar conversa bloqueada por 30 dias;
- impedir mais de uma mensagem aberta por `wa_id + phone_id_unidade`;
- inserir somente mensagens validas na fila.

Regra importante do webhook:

```text
Se ja existe mensagem pending ou processing para o mesmo wa_id + phone_id_unidade, ignora.
```

Essa regra impede que varias mensagens do mesmo cliente entrem na fila enquanto o worker ainda nao terminou de processar o turno atual.

## Worker

O worker e responsavel pela regra de negocio da conversa.

Responsabilidades do worker:

- validar cliente;
- validar conversa;
- garantir ordem das mensagens;
- validar historico;
- entender a etapa atual;
- interpretar se a mensagem atual e uma resposta valida;
- decidir qual fluxo executar;
- enviar mensagem do bot;
- registrar historico do cliente;
- registrar historico do bot;
- atualizar conversa;
- atualizar etapa atual;
- atualizar `status_dependente`;
- atualizar `last_message_from`;
- marcar mensagem da fila como `sent`.

## Regra obrigatoria do worker

Marcar a mensagem como `sent` deve ser sempre a ultima coisa do ciclo.

Antes de marcar `sent`, o worker deve ter concluido tudo que faz parte do turno:

- validacao do historico;
- envio da mensagem do bot;
- registro do historico;
- atualizacao da conversa;
- atualizacao da etapa;
- atualizacao de `last_message_from`.

Enquanto a mensagem ainda nao esta `sent`, ela permanece `pending` ou `processing`.

Por isso o webhook nao precisa consultar `last_message_from`: se o worker ainda nao terminou, a fila aberta ja bloqueia novas mensagens do mesmo cliente/unidade.

## Validar Historico

O `validar_historico` deve consultar o passado da conversa e devolver contexto para o sender.

Ele deve responder perguntas como:

- a mensagem atual ja foi registrada no historico?
- qual foi a ultima mensagem do bot?
- qual foi a ultima mensagem valida do cliente?
- a mensagem atual chegou depois da ultima pergunta do bot?
- ja existe resposta do cliente para a etapa atual?
- existe envio do bot que precisa ser completado apos falha anterior?

O `validar_historico` nao deve enviar mensagem.

Ele deve apenas devolver contexto e decisao para o fluxo.

## Flow Sender

O `flow_sender` deve decidir e executar a resposta do bot com base em:

- etapa atual;
- `status_dependente`;
- contexto retornado pelo `validar_historico`;
- ultima mensagem do cliente;
- ultima mensagem do bot;
- regras especificas de cada etapa.

Na primeira versao, a implementacao deve comecar pelas etapas 1 e 2.

## Etapas 1 e 2

Fluxo desejado:

1. Cliente envia a primeira mensagem.
2. Webhook aceita somente essa primeira mensagem se nao houver fila aberta.
3. Worker cria ou reutiliza conversa conforme regra atual.
4. Worker registra a mensagem do cliente no historico como etapa 1.
5. Worker atualiza conversa para etapa 1 e `last_message_from='cliente'`.
6. Bot envia saudacao da etapa 1.
7. Worker registra historico do bot na etapa 1.
8. Bot envia pergunta da etapa 2.
9. Worker registra historico do bot na etapa 2.
10. Worker atualiza conversa para etapa 2 e `last_message_from='bot'`.
11. Worker marca a mensagem da fila como `sent` por ultimo.

Mensagens extras enviadas pelo cliente antes do worker concluir o ciclo nao entram na fila, porque o webhook encontra a primeira mensagem ainda `pending` ou `processing`.

## Observacao sobre fallback

Se o worker cair antes de marcar `sent`, a mensagem continua aberta na fila.

Quando ela voltar a ser processada, o `validar_historico` deve identificar o que ja foi feito e continuar do ponto correto sempre que possivel.

Exemplo:

- se o historico ja tem saudacao da etapa 1, nao repetir saudacao;
- se falta pergunta da etapa 2, enviar apenas a etapa 2;
- se falta atualizar conversa, atualizar antes de marcar `sent`.

