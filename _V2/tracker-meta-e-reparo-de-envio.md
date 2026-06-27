# Tracker Meta e reparo de envio

Este documento registra uma estrategia futura para reduzir a chance de resposta
duplicada quando a Meta confirma um envio, mas o banco falha antes de salvar o
historico do bot.

## Problema

Cenario raro:

```text
1. Worker envia mensagem para a Meta.
2. Meta aceita o envio e retorna um wamid.
3. Cliente pode receber a mensagem.
4. Banco falha antes de salvar historico do bot.
5. Fila nao vira sent.
6. No retry, o banco nao encontra resposta do bot vinculada.
7. Worker pode enviar a mesma resposta novamente.
```

Esse cenario nao perde a mensagem valida do cliente, mas pode gerar duplicidade
rara de resposta.

## Por que nao e urgente na V1

Na V1, esse cenario depende de uma janela muito especifica:

```text
Meta aceitar o envio
e
banco cair antes de salvar historico do bot
```

Na pratica, isso tende a ser raro. O sistema pode passar dias ou semanas sem
ver esse caso, especialmente se banco, rede e deploy estiverem estaveis.

Por isso, tracker nao precisa entrar de forma apressada na V1. Ele deve ser
tratado como obrigatorio na V2, quando a arquitetura ja tiver suporte para
status da Meta, tabela/cache de rastreio e reparo idempotente.

## Campo que precisa estar ativo na Meta

Para receber status de mensagens enviadas pelo bot, a aplicacao precisa estar
assinada no campo de webhook:

```text
messages
```

Na tela da Meta, esse campo aparece na lista de `Campos do webhook`. O nome pode
confundir, mas o campo `messages` nao entrega apenas mensagens do cliente.

Ele tambem entrega status de mensagens que a empresa enviou para o cliente.

Dentro do mesmo campo assinado:

```text
value.messages -> mensagens recebidas do cliente
value.statuses -> status das mensagens enviadas pelo bot
```

Portanto, para a V2:

```text
Assinar o campo messages na Meta sera obrigatorio.
```

Sem esse campo assinado, o sistema nao recebe os posts de status e o tracker
nao consegue cumprir sua funcao de reparo.

Referencia: a documentacao oficial da Meta descreve o webhook `messages` como o
evento que carrega mensagens enviadas pelo usuario ao negocio e tambem status de
mensagens enviadas pelo negocio ao usuario. A referencia de status tambem mostra
o campo `statuses` e o retorno de `biz_opaque_callback_data` quando ele foi
enviado na mensagem original.

## O que o tracker resolve

A Cloud API permite enviar um campo de rastreio junto da mensagem:

```text
biz_opaque_callback_data
```

Na PyWa, esse campo aparece como o parametro:

```text
tracker
```

Exemplo conceitual:

```python
cliente_wa.send_message(
    to=cliente_telefone,
    text=mensagem_bot,
    buttons=botoes,
    tracker="conversa=10;fila=20;hash_cliente=wamid.x;etapa=2",
)
```

Com `requests`, o mesmo conceito seria:

```python
payload = {
    "messaging_product": "whatsapp",
    "to": cliente_telefone,
    "type": "text",
    "text": {
        "body": mensagem_bot,
    },
    "biz_opaque_callback_data": (
        f"conversa={id_conversa};"
        f"fila={id_mensagem_fila};"
        f"hash_cliente={id_hash_cliente};"
        f"etapa={id_etapa}"
    ),
}
```

Quando a Meta enviar eventos de status, esse tracker pode voltar no webhook de
status. Assim o sistema consegue associar um status da Meta a uma tentativa de
envio especifica.

## Explicacao leiga do fluxo

Pense no tracker como uma etiqueta colada na resposta do bot.

Exemplo:

```text
Cliente manda: Maria
Bot vai responder: Prazer, Maria!
```

Antes de enviar para a Meta, o sistema cola uma etiqueta invisivel:

```text
conversa=10
fila=20
hash_cliente=wamid.cliente
etapa=2
```

Essa etiqueta nao aparece para o cliente. Ela serve para o sistema reconhecer
aquela mensagem depois.

Fluxo desejado:

```text
1. Cliente envia mensagem.
2. Webhook recebe e coloca a mensagem na fila.
3. Worker le a mensagem.
4. Worker monta a resposta do bot.
5. Worker envia a resposta para a Meta com tracker.
6. Meta aceita a mensagem.
7. Meta envia um POST para o webhook com o status dessa mensagem.
8. Esse POST vem em value.statuses.
9. O status inclui o tracker.
10. Webhook detecta o tracker e salva em banco/cache.
```

Depois, se acontecer o problema raro:

```text
11. Worker caiu antes de salvar a resposta do bot no historico.
12. A mensagem do cliente volta para retry.
13. Worker percebe:
    - retry_count > 1;
    - nao existe resposta do bot vinculada no historico.
14. Antes de reenviar, worker consulta a tabela/cache de status Meta.
15. Se encontrar o tracker daquela fila/mensagem:
    - entende que a Meta ja recebeu uma resposta anterior;
    - nao envia duplicado;
    - repara historico/conversa/fila;
    - segue para a proxima etapa.
16. Se nao encontrar tracker/status:
    - segue o fluxo normal;
    - envia novamente.
```

Resumo:

```text
Tracker e a etiqueta.
Webhook de status e o aviso da Meta.
Tabela/cache local e o lugar onde guardamos esse aviso.
Retry consulta essa tabela/cache antes de reenviar.
```

## Limite importante

Tracker nao e uma consulta posterior direta.

Nao assumir que existe um endpoint confiavel como:

```text
GET /message_by_tracker/{tracker}
```

O tracker so e util se o sistema receber e persistir os eventos de status da
Meta.

Portanto, no retry, a pergunta nao deve ser:

```text
Meta, eu ja enviei essa mensagem?
```

Deve ser:

```text
Meu banco/cache local recebeu algum status da Meta com o tracker dessa tentativa?
```

Isso e importante: o worker nao pergunta para a Meta no retry. O worker pergunta
para o proprio sistema, que deve ter salvo anteriormente o POST de status enviado
pela Meta.

## Estrategia recomendada para V2

Criar uma estrutura local para rastrear envios do bot.

Opcoes:

```text
tabela meta_envio_status
tabela tentativa_envio_bot
cache Redis de status Meta
```

Uma abordagem robusta:

```text
1. Sender envia mensagem com tracker.
2. Meta retorna wamid.
3. Worker tenta salvar historico do bot normalmente.
4. Webhook de status da Meta recebe sent/delivered/read/failed.
5. Webhook salva status em tabela ou cache usando o tracker.
6. Em retry > 1, se nao houver historico do bot, worker consulta a tabela/cache
   de status antes de reenviar.
```

Tabela conceitual:

```text
meta_envio_status
```

Colunas possiveis:

```text
id_status
tracker
id_mensagem_fila
id_conversa
id_hash_cliente_origem
id_hash_msg_bot
id_etapa_resultante
phone_number_id
cliente_telefone
status_meta
timestamp_meta
payload_bruto
criado_em
```

Status uteis:

```text
sent
delivered
read
failed
```

Para reparo antes de reenviar, os status mais importantes sao:

```text
sent
delivered
read
```

Se o status for `failed`, o worker nao deve tratar como resposta entregue. Nesse
caso, pode seguir para retry normal ou para uma regra especifica de falha.

## Ponto exato de uso no worker

O tracker faria mais sentido neste ponto:

```text
retry_count > 1
resposta_bot_para_mensagem_atual nao existe
mensagem do cliente ja existe no historico
```

Fluxo desejado:

```text
1. Worker esta reprocessando mensagem.
2. Banco nao encontrou resposta do bot no historico.
3. Worker monta o tracker esperado para aquela mensagem/fila.
4. Antes de reenviar, worker procura status Meta pelo tracker esperado.
5. Se encontrar status que indica envio aceito/entregue/lido:
   - nao reenvia;
   - repara historico do bot ou marca estado de reparo;
   - atualiza conversa conforme a etapa;
   - marca fila como sent.
6. Se nao encontrar status:
   - segue fluxo atual e reenvia.
```

Condicao minima para acionar essa verificacao:

```text
retry_count > 1
resposta_bot_para_mensagem_atual nao existe
mensagem_cliente_atual existe
```

Isso evita consultar status Meta em todo fluxo normal. A verificacao so roda
quando existe sinal de reprocessamento e ausencia de historico do bot.

## Cuidado com cache

Um cache Redis pode ajudar, mas nao deve ser a unica fonte de verdade para a V2.

Motivo:

```text
Redis pode reiniciar
status pode expirar
evento pode chegar quando Redis esta fora
```

Melhor:

```text
Banco como fonte principal
Redis como acelerador/cache
```

## Por que nao implementar isso apressado na V1

Na V1 atual, o webhook nao persiste status de mensagens enviadas pelo bot.

Adicionar apenas `tracker` nos senders teria baixo risco, mas tambem baixo valor
imediato se os status nao forem tratados e salvos.

Para virar protecao real, seria necessario tambem:

```text
1. ajustar senders para receber tracker;
2. definir formato padrao do tracker;
3. tratar payloads de status no webhook;
4. criar tabela/cache de status Meta;
5. consultar essa tabela/cache no retry antes de reenviar;
6. reparar historico/conversa/fila quando o status confirmar envio anterior.
```

Isso ja e uma mudanca de arquitetura, portanto combina mais com V2 ou com uma
V1.1 planejada.

## Estrategia intermediaria possivel

Se a V1 precisar de uma melhoria pequena, pode ser feita em duas fases:

```text
Fase 1:
- adicionar tracker opcional nos senders;
- manter comportamento atual;
- apenas preparar rastreabilidade futura.

Fase 2:
- persistir status webhook;
- usar status no retry.
```

Mesmo assim, a fase 1 so vale a pena se for feita com plano especifico e testes,
porque exige passar dados do ciclo para os senders.

## Recomendacao

Para a V1 atual:

```text
Nao implementar agora.
Manter o fluxo atual.
Documentar para V2.
```

Para a V2:

```text
Implementar tracker como parte do desenho de envio/resposta/status.
Usar tracker em conjunto com tabela de status Meta e reparo idempotente.
Tratar tracker como obrigatorio em todo envio do bot.
Assinar o campo messages na Meta para receber value.statuses.
```

O tracker e uma excelente peca da estrategia, mas nao resolve sozinho a janela
entre:

```text
Meta aceitou envio
e
banco salvou historico do bot
```

Ele reduz o escuro operacional quando combinado com status webhook persistido.
