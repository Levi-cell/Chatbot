# Plano de implementacao - turno de recuperacao no webhook V1.0.0

## Objetivo

Permitir que o webhook aceite uma nova mensagem valida do cliente quando existe uma mensagem anterior ainda `pending` ou `processing`, mas essa mensagem anterior ja foi respondida pelo bot e so falta o worker fechar o ciclo marcando a fila como `sent`.

Este plano continua dentro do escopo da V1.0.0.

## Problema que sera resolvido

Cenario atual:

```text
1. Cliente envia mensagem A.
2. Worker processa A.
3. Bot envia resposta.
4. Worker registra historico do bot e atualiza conversa para last_message_from='bot'.
5. Worker cai antes de marcar A como sent.
6. Handler ou timeout deixa A pendente/reprocessavel por ate 2 minutos.
7. Cliente envia mensagem B respondendo ao bot.
8. Webhook ve A como pending/processing e ignora B.
```

O objetivo e permitir B entrar na fila quando A ja tem resposta do bot registrada.

## Regra nova

Regra atual:

```text
Se existe pending/processing para o mesmo cliente + unidade, o webhook ignora.
```

Regra nova:

```text
Se existe pending/processing para o mesmo cliente + unidade:
    verificar se todas as mensagens abertas desse cliente/unidade ja foram respondidas pelo bot.

Uma mensagem aberta conta como respondida pelo bot apenas se:
    fila_mensagens.id_conversa esta preenchido
    conversa.last_message_from = 'bot'
    existe historico_mensagens do bot com:
        quem_enviou = 'bot'
        status_envio = 'sent'
        id_mensagem_fila = fila_mensagens.id_mensagem
        id_hash_cliente_origem = fila_mensagens.id_hash_msg

Se todas as abertas ja foram respondidas:
    webhook aceita nova mensagem.

Se pelo menos uma aberta ainda nao tem resposta do bot:
    webhook ignora nova mensagem.
```

## Por que verificar todas as mensagens abertas

Nao basta olhar apenas a mensagem aberta mais antiga.

Exemplo:

```text
A esta pending, mas ja foi respondida pelo bot.
B entrou na fila depois disso, mas ainda nao foi respondida.
C chega no webhook.
```

Se o webhook olhasse so A, ele liberaria C.

Por isso a regra correta e:

```text
permitir nova mensagem apenas se nao existir nenhuma mensagem aberta sem resposta do bot.
```

Assim:

```text
A respondida -> nao bloqueia.
B ainda sem resposta -> bloqueia C.
```

## Dependencias ja existentes

O worker ja possui segunda camada de ordenacao:

```text
reagendar_se_houver_mensagem_anterior()
```

Entao, se a mensagem B entrar enquanto A ainda esta aberta:

```text
1. Worker pode pegar B.
2. Worker ve que existe A anterior ainda aberta.
3. Worker reagenda B sem contar como erro.
4. Depois A volta, o worker fecha A como sent.
5. Depois B e processada normalmente.
```

Tambem ja existe a estrategia de idempotencia do bot em:

```text
estrategia_evitar_duplicidade_worker.md
```

Ela cobre o caso em que a mensagem A ja tem resposta do bot registrada, mas ainda nao foi marcada como `sent`.

## Arquivos modificados

```text
core/database/turno_cliente_script.py
core/repositories/turno_cliente.py
```

## Passo 1 - Alterar core/database/turno_cliente_script.py

O indice unico atual precisa ser removido.

Motivo:

```text
O banco hoje impede qualquer segunda mensagem pending/processing do mesmo cliente/unidade.
```

Com a nova regra, em um caso controlado de recuperacao, pode existir:

```text
A pending/processing ja respondida pelo bot
B pending aguardando A fechar como sent
```

Codigo completo do arquivo:

```python
import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.turno_cliente_setup")


def criar_indices_turno_cliente():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute("""
            DROP INDEX IF EXISTS chatbot.uq_fila_cliente_unidade_aberta;

            CREATE INDEX IF NOT EXISTS idx_fila_cliente_unidade_aberta
            ON chatbot.fila_mensagens (
                cliente_telefone,
                id_phone_unidade,
                status,
                received_data_hora,
                id_mensagem
            )
            WHERE status IN ('pending', 'processing');

            CREATE INDEX IF NOT EXISTS idx_fila_cliente_unidade_conversa_aberta
            ON chatbot.fila_mensagens (
                cliente_telefone,
                id_phone_unidade,
                id_conversa,
                id_hash_msg,
                id_mensagem
            )
            WHERE status IN ('pending', 'processing');
        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_indices_turno_cliente")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "banco_setup_erro | acao=criar_indices_turno_cliente erro=%s",
            erro,
        )

    finally:
        if conn:
            conn.close()
```

## Passo 2 - Alterar core/repositories/turno_cliente.py

Este arquivo passa a avaliar se existe fila aberta sem resposta do bot.

Pontos importantes:

```text
advisory lock continua existindo
webhook continua barato quando nao existe fila aberta
consulta mais detalhada so pesa quando existe pending/processing
last_message_from sozinho nao libera nada
historico do bot vinculado a fila tambem precisa existir
```

Codigo completo do arquivo:

```python
import logging

from core.logging_config import short_value


logger = logging.getLogger("db.turno_cliente")


def avaliar_turno_cliente_para_fila(
    cursor,
    cliente_telefone,
    id_phone_unidade,
    usar_lock=False,
):
    if not cliente_telefone or not id_phone_unidade:
        logger.warning(
            "turno_cliente_invalido | motivo=dados_invalidos acao=bloquear_turno cliente=%s phone_number_id=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
        )
        return {
            "pode_enfileirar": False,
            "motivo": "dados_invalidos",
        }

    if usar_lock:
        adquirir_lock_turno_cliente(cursor, cliente_telefone, id_phone_unidade)

    turno = avaliar_filas_abertas_turno(
        cursor,
        cliente_telefone,
        id_phone_unidade,
    )

    if not turno["existe_fila_aberta"]:
        logger.debug(
            "turno_cliente_liberado | motivo=sem_fila_aberta acao=enfileirar cliente=%s phone_number_id=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
        )
        return {
            "pode_enfileirar": True,
            "motivo": "sem_fila_aberta",
        }

    if turno["todas_abertas_respondidas"]:
        logger.info(
            "turno_cliente_liberado | motivo=fila_aberta_respondida_bot acao=enfileirar_recuperacao cliente=%s phone_number_id=%s total_abertas=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            turno["total_abertas"],
        )
        return {
            "pode_enfileirar": True,
            "motivo": "fila_aberta_respondida_bot",
        }

    logger.info(
        "turno_cliente_bloqueado | motivo=fila_aberta_sem_resposta_bot acao=nao_enfileirar cliente=%s phone_number_id=%s total_abertas=%s id_mensagem_bloqueadora=%s",
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
        turno["total_abertas"],
        turno["id_mensagem_bloqueadora"],
    )
    return {
        "pode_enfileirar": False,
        "motivo": "fila_aberta_sem_resposta_bot",
    }


def adquirir_lock_turno_cliente(cursor, cliente_telefone, id_phone_unidade):
    cursor.execute("""
        SELECT pg_advisory_xact_lock(hashtext(%s), hashtext(%s));
    """, (str(id_phone_unidade), str(cliente_telefone)))

    logger.debug(
        "turno_cliente_lock | acao=advisory_xact_lock cliente=%s phone_number_id=%s",
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
    )


def avaliar_filas_abertas_turno(cursor, cliente_telefone, id_phone_unidade):
    cursor.execute("""
        WITH filas_abertas AS (
            SELECT
                f.id_mensagem,
                f.id_conversa,
                f.id_hash_msg,
                f.status,
                f.received_data_hora
            FROM chatbot.fila_mensagens f
            WHERE f.cliente_telefone = %s
              AND f.id_phone_unidade = %s
              AND f.status IN ('pending', 'processing')
        ),
        filas_sem_resposta_bot AS (
            SELECT
                f.id_mensagem
            FROM filas_abertas f
            LEFT JOIN chatbot.conversa c
              ON c.id_conversa = f.id_conversa
            LEFT JOIN chatbot.historico_mensagens h
              ON h.id_conversa = f.id_conversa
             AND h.quem_enviou = 'bot'
             AND h.status_envio = 'sent'
             AND h.id_mensagem_fila = f.id_mensagem
             AND h.id_hash_cliente_origem = f.id_hash_msg
            WHERE NOT (
                c.last_message_from = 'bot'
                AND h.id_mensagem IS NOT NULL
            )
            ORDER BY f.received_data_hora, f.id_mensagem
            LIMIT 1
        )
        SELECT
            EXISTS (SELECT 1 FROM filas_abertas) AS existe_fila_aberta,
            NOT EXISTS (SELECT 1 FROM filas_sem_resposta_bot) AS todas_abertas_respondidas,
            (SELECT COUNT(*) FROM filas_abertas) AS total_abertas,
            (SELECT id_mensagem FROM filas_sem_resposta_bot LIMIT 1) AS id_mensagem_bloqueadora;
    """, (cliente_telefone, id_phone_unidade))

    resultado = cursor.fetchone()

    existe_fila_aberta = bool(resultado[0]) if resultado else False
    todas_abertas_respondidas = bool(resultado[1]) if resultado else False
    total_abertas = int(resultado[2] or 0) if resultado else 0
    id_mensagem_bloqueadora = resultado[3] if resultado else None

    logger.debug(
        "turno_cliente_fila_consultada | acao=avaliar_abertas cliente=%s phone_number_id=%s existe=%s todas_respondidas=%s total=%s bloqueadora=%s",
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
        existe_fila_aberta,
        todas_abertas_respondidas,
        total_abertas,
        id_mensagem_bloqueadora,
    )

    return {
        "existe_fila_aberta": existe_fila_aberta,
        "todas_abertas_respondidas": todas_abertas_respondidas,
        "total_abertas": total_abertas,
        "id_mensagem_bloqueadora": id_mensagem_bloqueadora,
    }


def fila_tem_mensagem_aberta_turno(cursor, cliente_telefone, id_phone_unidade):
    turno = avaliar_filas_abertas_turno(
        cursor,
        cliente_telefone,
        id_phone_unidade,
    )
    return turno["existe_fila_aberta"]
```

## Passo 3 - Nao alterar callback/webhook/services/populating_fila_mensagens.py

Este arquivo ja consome:

```python
turno = avaliar_turno_cliente_para_fila(...)
```

e depois usa:

```python
if not turno["pode_enfileirar"]:
```

Logo, nao precisa mudar.

A unica diferenca sera que `avaliar_turno_cliente_para_fila()` agora pode retornar:

```python
{
    "pode_enfileirar": True,
    "motivo": "fila_aberta_respondida_bot",
}
```

Nesse caso o insert segue normalmente.

## Passo 4 - Nao alterar worker_flow.py neste plano

O worker ja tem a segunda camada de protecao:

```python
reagendar_se_houver_mensagem_anterior(...)
```

Quando uma mensagem mais nova entrar na fila enquanto uma anterior ainda esta aberta, o worker deve:

```text
ver mensagem anterior aberta
reagendar a mensagem mais nova
aguardar a antiga ser fechada como sent
```

O comportamento de marcar como `sent` uma mensagem antiga ja respondida pelo bot esta descrito em:

```text
estrategia_evitar_duplicidade_worker.md
```

E sera conectado ao fluxo completo do `flow_sender` quando o sender real registrar historico do bot e atualizar conversa.

## Passo 5 - Validacoes

Rodar:

```powershell
C:\Chatbot\venv\.venv\Scripts\python.exe -m compileall -q core callback workers main.py
C:\Chatbot\venv\.venv\Scripts\python.exe callback\manage.py check
```

Depois de recriar ou alterar o banco, garantir que o indice unico antigo saiu:

```sql
SELECT indexname
FROM pg_indexes
WHERE schemaname = 'chatbot'
  AND tablename = 'fila_mensagens'
  AND indexname IN (
      'uq_fila_cliente_unidade_aberta',
      'idx_fila_cliente_unidade_aberta',
      'idx_fila_cliente_unidade_conversa_aberta'
  );
```

Resultado esperado:

```text
uq_fila_cliente_unidade_aberta nao existe
idx_fila_cliente_unidade_aberta existe
idx_fila_cliente_unidade_conversa_aberta existe
```

## Teste manual recomendado

### Caso 1 - Sem fila aberta

```text
webhook recebe mensagem
avaliar_turno_cliente_para_fila retorna sem_fila_aberta
mensagem entra na fila
```

### Caso 2 - Fila aberta sem resposta do bot

```text
existe A pending/processing sem historico bot vinculado
webhook recebe B
B e ignorada com motivo fila_aberta_sem_resposta_bot
```

### Caso 3 - Fila aberta ja respondida pelo bot

Preparar estado:

```text
A pending/processing
A.id_conversa preenchido
conversa.last_message_from = 'bot'
historico_mensagens tem bot:
    quem_enviou = 'bot'
    status_envio = 'sent'
    id_mensagem_fila = A.id_mensagem
    id_hash_cliente_origem = A.id_hash_msg
```

Resultado esperado:

```text
webhook recebe B
B entra na fila
motivo = fila_aberta_respondida_bot
```

### Caso 4 - A respondida, B aberta sem resposta, C chega

Preparar estado:

```text
A pending/processing ja respondida pelo bot
B pending/processing ainda sem resposta do bot
C chega no webhook
```

Resultado esperado:

```text
C e ignorada
motivo = fila_aberta_sem_resposta_bot
```

Esse caso e essencial para garantir que a nova regra nao cria fila infinita.

## Riscos controlados

Esta mudanca permite mais de uma mensagem aberta por cliente/unidade apenas em caso de recuperacao.

O risco e controlado porque:

```text
advisory lock do webhook continua serializando cliente/unidade
mensagem nova so entra se todas as abertas ja foram respondidas pelo bot
worker ainda reage a mensagem anterior aberta
flow_sender tem idempotencia por id_mensagem_fila + id_hash_cliente_origem
```

## Decisao V1.0.0

Aplicar esta mudanca ainda na V1.0.0 e coerente porque ela fecha um buraco real:

```text
cliente respondeu durante janela de recuperacao antes da mensagem anterior virar sent
```

Sem transformar o webhook em cerebro do fluxo.

O webhook continua fazendo uma pergunta objetiva ao banco:

```text
existe alguma fila aberta sem resposta do bot?
```

Se existe, bloqueia.

Se nao existe, aceita.
