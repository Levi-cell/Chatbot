# Contexto do fluxo de historico e envio de mensagens

Este arquivo resume as decisoes tecnicas tomadas no chat para continuar o fluxo do worker a partir do `valida_historico_mensagem`, envio de resposta pelo bot e persistencia do historico.

## Estado geral do fluxo

O desenho atual continua sendo:

```text
Webhook Meta
=> valida unidade ativa via Redis/cache_unidade
=> valida conversa bloqueada via Redis/cache_conversas_bloqueadas
=> insere mensagem do cliente na fila
=> worker consome fila
=> valida unidade
=> valida cliente
=> valida conversa
=> bloqueia conversa se necessario
=> tenta lock da conversa
=> valida historico
=> decide resposta
=> envia mensagem pelo WhatsApp
=> atualiza conversa
=> marca fila como sent
```

O worker deve continuar usando o banco como fonte da verdade para conversa bloqueada. O Redis e usado como atalho no webhook, mas o worker valida conversa no banco via `valida_conversa`.

## Banco: historico_mensagens

O `bank_script.py` foi ajustado para que novos bancos ja criem `chatbot.historico_mensagens` com suporte a mensagens do cliente e do bot.

Mudancas aplicadas no desenho da tabela:

```sql
conteudo_texto TEXT
```

Agora `conteudo_texto` aceita `NULL`, porque mensagens de imagem, video, audio, documento, figurinha etc. podem nao ter corpo textual.

Foram adicionadas as colunas:

```sql
origem VARCHAR(10) NOT NULL
status_envio VARCHAR(20)
```

Regras:

```sql
CONSTRAINT chk_historico_origem
    CHECK (origem IN ('cliente', 'bot')),

CONSTRAINT chk_historico_status_envio
    CHECK (
        (origem = 'cliente' AND status_envio IS NULL)
        OR
        (
            origem = 'bot'
            AND status_envio IS NOT NULL
            AND status_envio IN ('pending', 'sent', 'failed')
        )
    )
```

Semantica definida:

```text
origem='cliente'
=> mensagem recebida do cliente
=> status_envio obrigatoriamente NULL

origem='bot'
=> mensagem enviada/tentada pelo bot
=> status_envio obrigatoriamente pending, sent ou failed
```

Tambem foi criado o indice:

```sql
CREATE INDEX IF NOT EXISTS idx_historico_conversa_data
ON chatbot.historico_mensagens (id_conversa, received_data_hora DESC);
```

Esse indice existe para consultas como:

```text
buscar ultimas mensagens da conversa
auditar duplicidade de respostas
ver se o bot ja respondeu depois de uma mensagem do cliente
montar contexto futuro para IA
```

## SQL de alteracao para banco ja existente

Caso o banco ja exista e nao seja recriado pelo `setup_database_aws.py`, estes comandos podem ser rodados manualmente no DBeaver:

```sql
BEGIN;

ALTER TABLE chatbot.historico_mensagens
ADD COLUMN IF NOT EXISTS origem VARCHAR(10);

ALTER TABLE chatbot.historico_mensagens
ADD COLUMN IF NOT EXISTS status_envio VARCHAR(20);

ALTER TABLE chatbot.historico_mensagens
ALTER COLUMN conteudo_texto DROP NOT NULL;

UPDATE chatbot.historico_mensagens
SET origem = 'cliente'
WHERE origem IS NULL;

ALTER TABLE chatbot.historico_mensagens
ALTER COLUMN origem SET NOT NULL;

ALTER TABLE chatbot.historico_mensagens
DROP CONSTRAINT IF EXISTS chk_historico_origem;

ALTER TABLE chatbot.historico_mensagens
DROP CONSTRAINT IF EXISTS chk_historico_status_envio;

ALTER TABLE chatbot.historico_mensagens
ADD CONSTRAINT chk_historico_origem
CHECK (origem IN ('cliente', 'bot'));

ALTER TABLE chatbot.historico_mensagens
ADD CONSTRAINT chk_historico_status_envio
CHECK (
    (origem = 'cliente' AND status_envio IS NULL)
    OR
    (
        origem = 'bot'
        AND status_envio IS NOT NULL
        AND status_envio IN ('pending', 'sent', 'failed')
    )
);

CREATE INDEX IF NOT EXISTS idx_historico_conversa_data
ON chatbot.historico_mensagens (id_conversa, received_data_hora DESC);

COMMIT;
```

## Models e admin

`callback/webhook/models.py` foi alinhado ao banco:

```python
conteudo_texto = models.TextField(blank=True, null=True)
origem = models.CharField(
    max_length=10,
    choices=[
        ("cliente", "cliente"),
        ("bot", "bot"),
    ],
)
status_envio = models.CharField(
    max_length=20,
    blank=True,
    null=True,
    choices=[
        ("pending", "pending"),
        ("sent", "sent"),
        ("failed", "failed"),
    ],
)
```

`callback/webhook/admin.py` foi alinhado ao model:

```text
HistoricoMensagensAdmin.list_display inclui:
- origem
- status_envio

HistoricoMensagensAdmin.list_filter inclui:
- origem
- status_envio
```

## id_hash_msg

Para mensagens recebidas do cliente:

```text
id_hash_msg = messages[0].id vindo do webhook da Meta
```

Mesmo mensagens de foto, video, audio, documento, figurinha etc. devem ter `messages[0].id`.

Se uma mensagem vier sem `id_hash_msg`, ela deve continuar sendo tratada como payload anormal/incompleto e nao deve entrar na fila. O codigo atual de `populating_fila_mensagens.py` ja faz isso usando `not all([... message_id ...])`.

Para mensagens enviadas pelo bot:

```text
id_hash_msg = id retornado pela API da Meta no envio
```

O bot nao precisa entrar na fila. A fila e somente para mensagens recebidas do cliente.

## PyWa

`core/integrations/whatsapp/pywa_tools.py` foi transformado em utilitario e nao dispara mensagem automaticamente ao importar.

Funcoes atuais:

```python
id_hash_msg = enviar_mensagem_texto(
    to="5571994111866",
    text="oi",
)
```

```python
id_hash_msg = enviar_template(
    to="5571994111866",
    name="evento_supera",
    language="en_US",
)
```

Ambas retornam:

```python
sent_message.id
```

Se o PyWa nao retornar `.id`, a funcao levanta `ValueError`.

Decisao atual:

```text
historico_mensagens registra mensagem do bot quando a API retorna id da mensagem
falha antes de retornar id pode ficar em log/tratamento de erro por enquanto
```

Assim nao precisamos gerar ID interno para mensagem do bot neste momento.

## valida_conversa

`valida_conversa` agora deve retornar tres valores:

```python
id_conversa, estado, etapa = valida_conversa(...)
```

Semantica:

```text
cliente novo
=> cria conversa
=> estado='nova'
=> etapa=None

cliente antigo sem conversa com aquela unidade
=> cria conversa
=> estado='liberada'
=> etapa=None

conversa ativa
=> usa conversa existente
=> estado='ativa'
=> etapa=id_etapa_atual vindo do banco

conversa bloqueada
=> estado='bloqueada'
=> etapa=None
=> worker nao chama valida_historico; registra bloqueio/cache, remove mensagem da fila e continua

conversa liberada apos 30 dias
=> cria nova conversa
=> estado='liberada'
=> etapa=None
```

Para `estado='bloqueada'`, a etapa pode ser `None`, porque o worker da `continue` antes de qualquer historico.

## Ponto exato no worker

No `workers/worker_flow/worker_flow.py`, o fluxo atual esta conceitualmente assim:

```python
id_cliente, inserido = valida_cliente(cliente_telefone, cursor_ciclo)

id_conversa, estado, etapa = valida_conversa(
    id_cliente,
    id_unidade,
    inserido,
    cursor_ciclo,
)

if estado == "bloqueada":
    tratar_conversa_bloqueada(...)
    conn_ciclo.commit()
    continue

lock_ok = tentar_lock_conversa(id_conversa, cursor_ciclo)
conn_ciclo.commit()

# valida historico

if not lock_ok:
    ...
    continue
```

Atencao: a chamada real de `valida_historico_mensagem` deve ficar depois do `if not lock_ok`.

Ordem correta sugerida:

```text
1. valida cliente
2. valida conversa
3. se bloqueada, trata bloqueio e continua
4. tenta lock da conversa
5. se nao lockou, continua
6. valida/insere historico da mensagem do cliente
7. decide se deve responder
8. envia resposta
9. registra historico do bot, se envio retornar id_hash_msg
10. atualiza conversa
11. marca mensagem da fila como sent
12. commit
```

## valida_historico_mensagem

Escopo planejado:

```text
Receber os dados que o worker ja tem em memoria.
Nao consultar banco para "embelezar" logs.
Nao buscar dados que ja vieram da fila.
Inserir a mensagem do cliente em historico_mensagens com origem='cliente' e status_envio=NULL.
Aceitar etapa=None.
Ser idempotente ou protegida contra duplicidade por id_hash_msg, se decidirmos criar constraint/indice depois.
```

Parametros esperados:

```python
valida_historico_mensagem(
    id_conversa=id_conversa,
    id_etapa=etapa,
    received_data_hora=data_recebimento,
    cliente_telefone=cliente_telefone,
    conteudo_texto=conteudo_texto,
    tipo_mensagem=tipo_mensagem,
    id_hash_msg=id_hash,
    id_phone_unidade=id_phone_unidade,
    unidade_telefone=unidade_telefone,
    cursor=cursor_ciclo,
)
```

Insert esperado para mensagem do cliente:

```text
id_conversa = conversa atual
id_etapa = etapa atual ou NULL
received_data_hora = data da mensagem recebida
cliente_telefone = telefone do cliente
conteudo_texto = texto ou NULL
tipo_mensagem = text/image/audio/document/sticker/etc.
id_hash_msg = id da mensagem recebida da Meta
id_phone_unidade = phone_number_id da unidade
unidade_telefone = display_phone_number da unidade
origem = 'cliente'
status_envio = NULL
```

## Etapas e historico

Regra definida:

```text
conversa.id_etapa_atual = fonte da verdade da etapa atual
historico_mensagens.id_etapa = fotografia da etapa no momento daquela mensagem
```

Portanto, se uma conversa esta atualmente na etapa 4, e normal que o historico tenha mensagens antigas nas etapas 1, 2 e 3.

O que deve ser evitado:

```text
conversa.id_etapa_atual = 4
historico novo sendo gravado como etapa 5 sem o fluxo realmente ter avancado para etapa 5
```

Para evitar isso:

```text
1. Nunca usar historico como fonte da etapa atual.
2. Sempre decidir a etapa atual por conversa.id_etapa_atual.
3. Atualizar conversa.id_etapa_atual somente no ponto oficial da regra de negocio.
4. Gravar historico com a etapa que estava vigente naquele momento logico.
```

## Duplicidade de mensagens e resposta do bot

Cenario importante:

```text
cliente manda "ola"
cliente manda "ola" de novo antes do bot responder
worker processa a primeira e responde
worker pega a segunda depois
```

Protecao sugerida:

```text
Usar last_message_from + last_interaction_at + received_data_hora.
```

Regra conceitual:

```text
se last_message_from = 'bot'
e last_interaction_at >= received_data_hora da mensagem da fila
=> o bot ja respondeu depois daquela mensagem
=> registrar historico do cliente, marcar fila como sent e nao responder de novo
```

Essa decisao deve acontecer com a conversa lockada.

## Concorrencia

O `lock_conversa` continua sendo a barreira principal contra dois workers responderem a mesma conversa ao mesmo tempo.

Por isso:

```text
valida_historico_mensagem deve rodar depois do lock bem-sucedido.
```

Se `lock_ok` for falso:

```text
nao inserir historico
nao enviar resposta
nao incrementar retry
apenas continue
```

## Logs

Os logs foram padronizados para registrar:

```text
evento | motivo=... acao=... contexto operacional
```

O formato central em `core/logging_config.py` inclui:

```text
arquivo:linha
```

Erros reais usam `logger.exception`, preservando traceback completo.

## Proximos passos sugeridos

1. Criar funcao de insert em `core/repositories/inserts.py` para `historico_mensagens`.
2. Criar `valida_historico_mensagem` em `workers/worker_flow/suport_functions.py` ou arquivo proprio.
3. Chamar `valida_historico_mensagem` no worker depois do `if not lock_ok`.
4. Criar funcao de decisao `mensagem_ja_coberta_por_resposta_bot`.
5. Criar primeiro envio real de saudacao pelo bot usando `pywa_tools.enviar_mensagem_texto`.
6. Registrar historico do bot quando envio retornar `id_hash_msg`.
7. Atualizar conversa com `last_message_from='bot'`, `last_interaction_at=NOW()` e eventual `id_etapa_atual`.
