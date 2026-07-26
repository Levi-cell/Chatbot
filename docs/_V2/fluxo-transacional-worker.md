# Fluxo transacional do worker

Este documento registra uma garantia importante da V1 que deve ser preservada
na V2: o worker nao deve perder mensagens validas do cliente, mesmo quando a
Meta, o banco ou o processo falharem em pontos intermediarios.

O exemplo usado aqui e a ponte da etapa 1 para a etapa 2:

```text
Cliente: Maria
Bot: Prazer, Maria! ...
```

Essa ponte tambem e o momento em que o sistema deve salvar o primeiro nome do
cliente no banco.

## Estado de aplicacao na V1

O `plano_implementacao_ponte_etapa2.md` foi aplicado na V1. No estado atual:

```text
etapa1.py ja valida nome e envia a etapa 2
etapa1.py ja coloca primeiro_nome_cliente no contexto_envio
persistencia_resposta.py salva cliente.nome na transicao 1 -> 2
```

As garantias abaixo descrevem o comportamento ativo da V1 e devem ser
preservadas na V2.

## Conceito central

`id_etapa_atual` e a etapa da conversa antes da resposta do bot.

`id_etapa_resultante` e a etapa para onde a resposta do bot esta levando a
conversa.

Por isso, a persistencia do nome nao deve ser feita simplesmente porque a
conversa esta na etapa 1 ou na etapa 2. Ela deve acontecer quando o sistema
identifica a transicao:

```text
etapa_origem  = 1
etapa_destino = 2
```

Ou seja:

```text
1 -> 2
```

Essa diferenca e essencial.

## O vínculo da fila não é uma nova barreira de turno

Depois de resolver cliente, unidade e conversa, o worker tenta preencher
`fila_mensagens.id_conversa`. O `UPDATE` aceita apenas vínculo vazio ou a mesma
conversa já persistida; portanto ele nunca sobrescreve silenciosamente uma
conversa diferente.

Essa proteção pertence à integridade do vínculo. Ela não:

- altera `pending`, `processing` ou `sent`;
- adquire ou libera o lock da conversa;
- decide se o webhook pode aceitar o próximo turno;
- substitui `reagendar_se_houver_mensagem_anterior()`;
- substitui a idempotência de `resposta_bot_para_mensagem_atual`.

Um retorno de zero linhas não deve virar erro genérico. Existe um cenário
recuperável em que:

1. A já recebeu resposta do bot, mas ainda não chegou a `sent`;
2. B foi aceita como primeiro evento do próximo turno e vinculada à conversa;
3. A encerra essa conversa sem bloqueio ativo antes do retry de B;
4. B passa intencionalmente a uma conversa nova do mesmo cliente e unidade.

Isso não acontece em uma transição normal de etapa: se A não encerra o
atendimento, B continua na mesma conversa e na etapa já atualizada. Se A
encerra em uma etapa com bloqueio vigente, B é removida como mensagem de
conversa bloqueada. No fluxo atual, a criação imediata de uma conversa nova
após encerramento ocorre nos tratamentos de idade inválida, que usam
`bloqueio_dias = 0`; também pode ocorrer depois da expiração de um bloqueio.

Nesse cenário o vínculo antigo é preservado para diagnóstico, o worker registra
`mensagem_conversa_vinculo_preservado` e continua com o contexto recalculado.
Transformar isso em retry genérico poderia consumir as três tentativas e perder
uma mensagem válida antes de alcançar a barreira idempotente.

Se o sistema salvasse nome apenas porque `id_etapa_atual == 1`, poderia salvar
texto invalido em tratamentos da etapa 1, como midia, pergunta financeira ou
nome fora de contexto.

Se o sistema salvasse nome apenas porque `id_etapa_atual == 2`, poderia salvar
como nome uma resposta da etapa 2, como `Para mim` ou `Para outra pessoa`.

Por isso, o ponto correto e a transicao:

```text
mensagem do cliente pertence a etapa 1
resposta do bot avanca a conversa para etapa 2
```

## Fluxo normal

Antes do envio da etapa 2, o worker ja fez:

```text
1. Pegou a mensagem da fila.
2. Validou cliente e conversa.
3. Registrou a mensagem do cliente no historico.
4. Atualizou last_message_from = cliente.
5. Fez commit desse estado.
```

Depois disso, o worker chama o `flow_sender`.

Quando o cliente respondeu `Maria`:

```text
flow_sender
-> etapa1.py
-> valida nome
-> chama enviar_etapa2(...)
-> Meta responde OK
-> contexto_envio volta com:
   id_etapa_resultante = 2
   primeiro_nome_cliente = Maria
```

Em seguida entra a transacao final:

```text
atualizar_banco_com_contexto_final
-> insere historico do bot
-> atualiza conversa para etapa 2
-> atualizar_banco_conforme_transicao_de_etapa
-> detecta ponte 1 -> 2
-> salva cliente.nome = Maria
-> commit
-> marca fila como sent
-> commit
```

Resultado:

```text
historico do cliente: sim
last_message_from = bot
historico do bot: sim
id_etapa_atual = 2
cliente.nome = Maria
fila.status = sent
```

## Cenario 1: Meta falha ao enviar a etapa 2

Exemplo:

```text
Bot tentou enviar: Prazer, Maria! ...
Meta/PyWa falhou.
```

Fluxo:

```text
1. Nome Maria e validado.
2. Sender tenta enviar etapa 2 pela PyWa.
3. Meta/PyWa falha.
4. Sender levanta ErroEnvioMeta.
5. flow_worker cai no except ErroEnvioMeta.
6. Worker faz rollback da transacao atual.
7. handle_erro_generico tenta reagendar a mensagem.
8. A fila fica preparada para retry.
```

O que fica salvo:

```text
historico do cliente: sim
last_message_from = cliente: sim
historico do bot: nao
id_etapa_atual = 1
cliente.nome: nao
fila.status = pending ou processing ate ficar elegivel novamente
```

No retry:

```text
1. Worker pega a mesma mensagem.
2. valida_historico encontra a mensagem do cliente ja existente.
3. valida_historico nao encontra resposta do bot para essa mensagem.
4. flow_sender valida Maria de novo.
5. Sender tenta enviar etapa 2 de novo.
6. Se a Meta responder OK:
   - salva historico do bot;
   - atualiza conversa para etapa 2;
   - detecta transicao 1 -> 2;
   - salva cliente.nome = Maria;
   - faz commit;
   - marca fila como sent.
```

Garantia:

```text
A mensagem valida do cliente nao e perdida.
Se Meta e banco funcionarem no retry, o nome e salvo normalmente.
```

## Cenario 2: Meta envia, mas banco falha depois

Este e o cenario mais delicado.

Exemplo:

```text
Meta confirmou envio de: Prazer, Maria! ...
Mas o banco falhou antes do commit final.
```

Fluxo:

```text
1. Nome Maria e validado.
2. Meta envia a mensagem com sucesso.
3. Cliente pode receber a mensagem no WhatsApp.
4. contexto_envio.enviou = True.
5. Banco falha ao:
   - inserir historico do bot; ou
   - atualizar conversa para etapa 2; ou
   - salvar cliente.nome = Maria.
6. A transacao final sofre rollback.
7. flow_worker levanta BancoFalhouAposEnvioMeta.
8. Mensagem fica para retry.
```

O que fica salvo se o banco falhou antes do commit final:

```text
historico do cliente: sim
last_message_from = cliente: sim
historico do bot: nao
id_etapa_atual = 1
cliente.nome: nao
fila.status: nao vira sent
```

Risco conhecido:

```text
O cliente pode ter recebido a resposta da Meta, mas o banco nao registrou essa
resposta.
```

No retry:

```text
1. Worker pega a mesma mensagem.
2. Banco nao encontra historico do bot para essa mensagem.
3. flow_sender pode tentar enviar a etapa 2 novamente.
4. Pode ocorrer uma resposta duplicada rara.
```

Garantia:

```text
A mensagem valida do cliente nao e perdida.
O risco desse cenario e duplicidade rara, nao perda de atendimento.
```

Esse risco existe porque o envio para a Meta e uma operacao externa e nao
participa da mesma transacao do banco.

## Cenario 3: Meta envia, banco commita, mas worker cai antes do sent

Este e o melhor cenario de recuperacao.

Fluxo:

```text
1. Meta envia: Prazer, Maria! ...
2. Banco salva historico do bot.
3. Banco atualiza conversa para etapa 2.
4. Banco salva cliente.nome = Maria.
5. Worker faz commit da transacao final.
6. Worker cai antes de marcar a fila como sent.
```

O que fica salvo:

```text
historico do cliente: sim
last_message_from = bot
historico do bot: sim
id_etapa_atual = 2
cliente.nome = Maria
fila.status ainda pode estar processing
```

No retry:

```text
1. Worker pega a mesma mensagem.
2. valida_historico encontra resposta do bot ja existente para essa mensagem.
3. flow_sender entra em idempotencia.
4. flow_sender nao envia mensagem duplicada.
5. atualizar_banco_com_contexto_final entra em modo idempotente.
6. atualizar_banco_conforme_transicao_de_etapa pode reparar o nome se precisar.
7. Worker marca a fila como sent.
```

Garantia:

```text
Nao deve duplicar resposta.
A fila e reparada para sent.
O nome pode ser reparado caso algo tenha ficado incompleto.
```

## Cenario 4: Meta falha e banco tambem falha ao reagendar

Exemplo:

```text
Meta falhou no envio.
Depois, o banco tambem falhou quando o sistema tentou reagendar a mensagem.
```

Fluxo:

```text
1. Sender levanta ErroEnvioMeta.
2. flow_worker entra no except ErroEnvioMeta.
3. Worker tenta rollback.
4. handle_erro_generico tenta reagendar a fila.
5. Banco falha durante o reagendamento.
6. handle_erro_generico registra handler_generico_falhou.
7. O erro do handler nao derruba o worker.
```

O que fica salvo:

```text
historico do cliente: sim, se ja havia sido commitado antes
historico do bot: nao
id_etapa_atual: continua na etapa anterior
cliente.nome: nao
fila.status: nao vira sent
```

Garantia:

```text
O sistema registra a falha e continua protegido.
A mensagem nao e marcada como sent indevidamente.
Quando a fila voltar a ficar elegivel, o worker pode tentar novamente.
```

Se o processo inteiro escapar, `iniciar_flow_worker.py` reinicia
`worker_flow()`.

## Cenario 5: resposta do bot ja existe, mas nome ainda precisa ser reparado

Esse cenario cobre recuperacao idempotente.

Exemplo:

```text
Historico do bot para a mensagem ja existe.
Mas cliente.nome ainda nao foi salvo ou precisa ser reparado.
```

Fluxo:

```text
1. Worker pega a mensagem em retry.
2. valida_historico encontra resposta do bot ja existente.
3. flow_sender nao envia nada para a Meta.
4. contexto_envio indica resposta_ja_existia = True.
5. atualizar_banco_com_contexto_final repara o estado da conversa se precisar.
6. atualizar_banco_conforme_transicao_de_etapa detecta 1 -> 2.
7. Se primeiro_nome_cliente nao veio no contexto_envio, reconstruiu pelo texto original.
8. Salva cliente.nome = Maria.
9. Marca fila como sent.
```

Garantia:

```text
Nao envia resposta duplicada.
Pode reparar o nome usando a mensagem original do cliente.
```

## Invariantes que a V2 deve preservar

1. O worker deve continuar commitando a mensagem do cliente antes do envio do bot.
2. O envio Meta deve continuar acontecendo antes da persistencia da resposta do bot.
3. A resposta do bot, a atualizacao da conversa e os dados especificos da etapa devem ficar na mesma transacao final.
4. A fila so deve virar `sent` depois da transacao final estar commitada.
5. Resposta do bot ja existente deve ativar idempotencia e nao reenviar mensagem.
6. Dados especificos de etapa devem ser salvos por transicao, nao por etapa isolada.
7. A ponte `1 -> 2` salva o nome; tratamentos `1 -> 1` nao salvam nome.
8. Falha da Meta deve reagendar sem marcar `sent`.
9. Falha do banco apos envio Meta pode gerar duplicidade rara, mas nao pode perder a mensagem valida.

## Resumo rapido

```text
None -> 1
Saudacao inicial.
Nao salva nome.

1 -> 1
Tratamento da etapa 1.
Nao salva nome.

1 -> 2
Nome valido.
Salva cliente.nome.

2 -> 3
Proxima etapa futura.
Nao salva nome neste bloco.
```

O ponto principal para a V2 e manter a mesma filosofia:

```text
salvar efeitos especificos quando a transicao correta for confirmada,
nao apenas porque a conversa esta em uma etapa numerica.
```
