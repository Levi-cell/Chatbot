# Estrategia - evitar duplicidade quando o worker cai antes de marcar sent

## Objetivo

Evitar que o bot envie a mesma resposta duas vezes quando acontecer este cenario:

```text
1. worker pega mensagem da fila
2. worker envia resposta do bot
3. worker registra historico do bot
4. worker atualiza conversa
5. worker faz commit desse bloco
6. worker cai antes de marcar a mensagem da fila como sent
7. a mesma mensagem volta a ser processada depois do timeout
```

A protecao desejada:

```text
se ja existe historico do bot com status_envio='sent'
ligado a mensagem atual da fila,
o worker nao chama o flow_sender de novo
e apenas deixa o fluxo marcar a fila como sent
```

## Base ja aplicada

Estes pontos ja foram aplicados no projeto:

```text
core/database/bank_script.py
callback/webhook/models.py
callback/webhook/admin.py
```

O historico agora tem as colunas:

```text
id_mensagem_fila
id_hash_cliente_origem
```

Significado:

```text
id_mensagem_fila = fila_mensagens.id_mensagem que originou a resposta
id_hash_cliente_origem = fila_mensagens.id_hash_msg que originou a resposta
```

Para mensagem do bot:

```text
id_hash_msg = hash/id da propria mensagem enviada pelo bot
id_hash_cliente_origem = hash/id da mensagem do cliente que causou a resposta
```

## Regra de responsabilidade

O `flow_sender` deve ser especifico para enviar mensagem.

Ele nao deve:

```text
consultar idempotencia
inserir historico
atualizar conversa
fazer commit
fazer rollback
fechar conexao
```

O fluxo externo do worker deve fazer:

```text
registrar historico do cliente
chamar flow_sender
registrar historico do bot
atualizar conversa
marcar fila como sent
```

Todos os `commit`, `rollback` e `close` do fluxo do worker continuam em:

```text
workers/worker_flow/worker_flow.py
```

## Fluxo desejado

```text
1. Cliente envia mensagem
2. Worker valida banco e cria/obtém conversa
3. Worker vincula mensagem da fila a conversa
4. Worker pega lock da conversa
5. Worker chama validar_historico
6. Worker descobre qual etapa/resposta deve enviar
7. Worker consulta se ja existe resposta do bot para essa mensagem da fila
8. Se existir, nao envia novamente
9. Se nao existir, registra historico do cliente
10. Worker chama flow_sender
11. Worker registra historico do bot com id_mensagem_fila/id_hash_cliente_origem
12. Worker atualiza conversa e last_message_from='bot'
13. worker_flow.py faz commit do bloco logico
14. worker_flow.py marca fila como sent
15. worker_flow.py faz commit final
```

## Consulta futura em `core/repositories/querys.py`

Adicionar uma funcao de consulta parecida com esta:

```python
def buscar_resposta_bot_por_mensagem_origem(
    id_conversa,
    id_mensagem_fila,
    id_hash_cliente_origem,
    id_etapa_resposta,
    cursor,
):
    if not all([
        id_conversa,
        id_mensagem_fila,
        id_hash_cliente_origem,
        id_etapa_resposta,
    ]):
        logger.debug(
            "historico_bot_idempotencia_ignorada | motivo=dados_insuficientes id_conversa=%s id_mensagem_fila=%s id_hash_origem=%s id_etapa=%s",
            id_conversa,
            id_mensagem_fila,
            id_hash_cliente_origem,
            id_etapa_resposta,
        )
        return None

    cursor.execute("""
        SELECT
            id_mensagem,
            id_hash_msg,
            received_data_hora,
            status_envio
        FROM chatbot.historico_mensagens
        WHERE id_conversa = %s
          AND quem_enviou = 'bot'
          AND status_envio = 'sent'
          AND id_mensagem_fila = %s
          AND id_hash_cliente_origem = %s
          AND id_etapa = %s
        ORDER BY received_data_hora DESC, id_mensagem DESC
        LIMIT 1;
    """, (
        id_conversa,
        id_mensagem_fila,
        id_hash_cliente_origem,
        id_etapa_resposta,
    ))

    resultado = cursor.fetchone()
    logger.debug(
        "historico_bot_idempotencia_consultada | acao=verificar_resposta id_conversa=%s id_mensagem_fila=%s id_etapa=%s encontrada=%s",
        id_conversa,
        id_mensagem_fila,
        id_etapa_resposta,
        bool(resultado),
    )
    return resultado
```

## Helper futuro `workers/worker_flow/idempotencia_bot.py`

Esse helper deve receber a mensagem atual da fila, o contexto da conversa e a etapa da resposta.

Ele deve retornar algo como:

```python
{
    "ja_registrada": True,
    "historico_bot": {
        "id_historico_bot": 10,
        "id_hash_msg_bot": "wamid.BOT_123",
        "received_data_hora": "...",
        "status_envio": "sent",
    },
    "motivo": "resposta_ja_registrada",
}
```

ou:

```python
{
    "ja_registrada": False,
    "historico_bot": None,
    "motivo": "sem_resposta_registrada",
}
```

## Encaixe futuro no `worker_flow.py`

O encaixe deve ficar depois de:

```text
validar_banco
vincular mensagem a conversa
lock da conversa
reagendar_se_houver_mensagem_anterior
validar_historico
```

E antes de:

```text
flow_sender
registrar historico do bot
atualizar conversa
marcar sent
```

Pseudofluxo:

```python
idempotencia_bot = resposta_bot_ja_registrada_para_mensagem(
    mensagem,
    contexto_banco,
    id_etapa_resposta,
    cursor_ciclo,
)

if idempotencia_bot["ja_registrada"]:
    logger.warning(
        "flow_sender_ignorado | motivo=resposta_bot_ja_registrada acao=marcar_sent_sem_reenviar id_mensagem=%s id_conversa=%s id_etapa=%s",
        mensagem["id_mensagem"],
        id_conversa,
        id_etapa_resposta,
    )

else:
    # registrar_historico_cliente
    # resultado_sender = flow_sender(...)
    # registrar_historico_bot
    # atualizar_conversa
    conn_ciclo.commit()

finalizar_mensagem_processada(...)
conn_ciclo.commit()
```

## Limite importante

Essa estrategia resolve o caso em que:

```text
Meta/PyWa enviou
historico do bot foi inserido
conversa foi atualizada
commit aconteceu
worker caiu antes de marcar fila como sent
```

Ela nao resolve completamente o caso em que:

```text
Meta/PyWa enviou
worker caiu antes de inserir/commitar historico do bot
```

Nesse segundo caso, o banco nao tem prova do envio. Para resolver isso de forma perfeita no futuro, seria necessario suporte de idempotency key do provedor, reconciliacao com a Meta, ou outro mecanismo externo de confirmacao.

## Validacoes quando implementar o restante

Rodar:

```powershell
C:\Chatbot\venv\.venv\Scripts\python.exe -m compileall -q core callback workers main.py
C:\Chatbot\venv\.venv\Scripts\python.exe callback\manage.py check
```

Conferir:

```powershell
rg -n "id_mensagem_fila|id_hash_cliente_origem|resposta_bot_ja_registrada|buscar_resposta_bot_por_mensagem_origem" core callback workers
rg -n "\.commit\(|\.rollback\(|\.close\(" workers\worker_flow -g "*.py"
```

Resultado esperado:

```text
commit, rollback e close do fluxo do worker continuam em worker_flow.py
```
