# Plano de Implementacao - Flow Sender Etapa 1 com Meta/PyWa

## Objetivo

Implementar o primeiro envio real do bot pelo PyWa dentro do fluxo do worker, com controle claro de erro da Meta, persistencia da resposta do bot no banco e preservacao da regra principal do worker:

- `sent` continua sendo a ultima operacao do ciclo.
- `commit`, `rollback` e `close` continuam no `worker_flow.py`.
- SQL cru continua somente nos arquivos de `core/repositories`.
- Se a Meta falhar, nao grava resposta do bot no historico, nao atualiza conversa como bot e nao marca fila como `sent`.
- Se a Meta enviar com sucesso, grava historico do bot, atualiza conversa para `last_message_from='bot'`, comita, marca fila como `sent` e comita novamente.
- Se o banco falhar depois da Meta enviar, registra log critico especifico porque existe risco raro de duplicidade no retry.

## Fluxo final esperado

1. `worker_flow.py` chama `valida_historico()`.
2. `valida_historico()` registra a mensagem do cliente no historico e monta `contexto_historico`.
3. `worker_flow.py` chama `flow_sender(contexto_historico)`.
4. `flow_sender()` verifica idempotencia:
   - se ja existe resposta do bot vinculada a esta mensagem da fila, nao envia novamente;
   - retorna contexto informando `resposta_ja_existia=True`.
5. Se nao existe resposta e `id_etapa_resposta == 1`, `flow_sender()` chama `sender_etapa1()`.
6. `sender_etapa1()` monta `wa` com `conta_wa(phone_id_unidade)` e envia `"Ola!"`.
7. Se a Meta/PyWa falhar, `sender_etapa1()` levanta `ErroEnvioMeta`.
8. `worker_flow.py` captura `ErroEnvioMeta`, faz rollback e usa o handler atual para reagendar sem marcar `sent`.
9. Se a Meta enviar, `flow_sender()` retorna contexto com:
   - texto enviado;
   - tipo da mensagem;
   - etapa resultante;
   - `id_hash_msg_bot` retornado pela Meta.
10. `worker_flow.py` chama `atualizar_banco_com_contexto_final()`.
11. `atualizar_banco_com_contexto_final()` chama repositories para:
   - inserir historico do bot;
   - atualizar conversa para `last_message_from='bot'` e etapa resultante.
12. `worker_flow.py` da commit.
13. `worker_flow.py` marca a fila como `sent`.
14. `worker_flow.py` da commit final.

## Decisoes importantes

- `ErroEnvioMeta` deve ser exception, nao retorno `False`. Assim fica mais dificil esquecer de tratar erro da Meta.
- `sender_etapa1()` nao executa SQL. Ele apenas envia pela Meta e retorna contexto de sucesso.
- `flow_sender()` decide etapa e envia pela integracao, mas nao comita nada.
- `atualizar_banco_com_contexto_final()` nao contem SQL cru. Ela chama `inserts.py` e `updates.py`.
- Por enquanto apenas etapa 1 envia mensagem real. Etapas 2 a 7 devem ficar pendentes explicitamente para evitar gravar historico falso sem `id_hash_msg_bot`.
- A mensagem do cliente ja fica salva pelo `valida_historico()` antes do envio da Meta. Quando falamos "Meta falhou, nao registra nada no banco", significa: nao registra a resposta do bot, nao atualiza conversa como bot e nao marca a fila como `sent`.

---

# Passo 1 - Criar exceptions da integracao WhatsApp

Arquivo criado: `core/integrations/whatsapp/exceptions.py`

```python
class ErroEnvioMeta(Exception):
    def __init__(
        self,
        message,
        *,
        cliente_telefone=None,
        phone_id_unidade=None,
        id_etapa=None,
    ):
        super().__init__(message)
        self.cliente_telefone = cliente_telefone
        self.phone_id_unidade = phone_id_unidade
        self.id_etapa = id_etapa
```

---

# Passo 2 - Criar exception especifica do worker para falha de banco apos envio

Arquivo criado: `workers/tratamento_erro/exceptions.py`

```python
class BancoFalhouAposEnvioMeta(Exception):
    def __init__(
        self,
        message,
        *,
        id_mensagem=None,
        id_conversa=None,
        id_hash_msg_bot=None,
        id_etapa=None,
    ):
        super().__init__(message)
        self.id_mensagem = id_mensagem
        self.id_conversa = id_conversa
        self.id_hash_msg_bot = id_hash_msg_bot
        self.id_etapa = id_etapa
```

---

# Passo 3 - Criar sender de etapa na integracao WhatsApp

Arquivo criado: `core/integrations/whatsapp/sender.py`

```python
import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.senders import enviar_mensagem_texto
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender")

MENSAGEM_ETAPA_1 = "Ola!"


def sender_etapa1(cliente_telefone, phone_id_unidade):
    try:
        id_hash_msg_bot = enviar_mensagem_texto(
            to=cliente_telefone,
            text=MENSAGEM_ETAPA_1,
            phone_id_unidade=phone_id_unidade,
        )

    except Exception as erro:
        logger.exception(
            "meta_envio_falhou | acao=levantar_erro_meta etapa=1 cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Falha ao enviar mensagem da etapa 1 pela Meta",
            cliente_telefone=cliente_telefone,
            phone_id_unidade=phone_id_unidade,
            id_etapa=1,
        ) from erro

    logger.info(
        "meta_envio_ok | acao=enviar etapa=1 cliente=%s phone_number_id=%s id_hash_msg_bot=%s",
        short_value(cliente_telefone),
        short_value(phone_id_unidade),
        id_hash_msg_bot,
    )

    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "canal": "meta_whatsapp",
        "tipo_mensagem": "text",
        "mensagem_bot": MENSAGEM_ETAPA_1,
        "id_hash_msg_bot": id_hash_msg_bot,
        "id_etapa_resultante": 1,
    }
```

---

# Passo 4 - Atualizar repositories de insert

Arquivo modificado: `core/repositories/inserts.py`

```python
import logging

from core.logging_config import short_value


logger = logging.getLogger("db.inserts")


def inserindo_em_cliente_caso_seja_novo(waid_telefone, cursor):
    try:
        cursor.execute("""
            INSERT INTO chatbot.cliente (waid_telefone)
            VALUES (%s)
            ON CONFLICT (waid_telefone) DO NOTHING;
        """, (waid_telefone,))

        inserido = cursor.rowcount == 1

        cursor.execute("""
            SELECT id_cliente
            FROM chatbot.cliente
            WHERE waid_telefone = %s;
        """, (waid_telefone,))
        result = cursor.fetchone()

        if result:
            logger.debug(
                "cliente_insert_resultado | acao=obter_cliente telefone=%s id_cliente=%s inserido=%s",
                short_value(waid_telefone),
                result[0],
                inserido,
            )
            return result[0], inserido

        raise ValueError(
            f"Anomalia Critica: Cliente do telefone {waid_telefone} "
            "desapareceu da base durante a verificacao!"
        )

    except Exception:
        logger.exception(
            "cliente_insert_erro | acao=rollback telefone=%s",
            short_value(waid_telefone),
        )
        raise


def inserindo_em_conversa_caso_seja_nova(id_cliente, id_unidade, cursor):
    try:
        cursor.execute("""
            INSERT INTO chatbot.conversa (
                id_cliente,
                id_unidade,
                last_interaction_at,
                last_message_from
            )
            VALUES (%s, %s, NOW(), 'cliente')
            RETURNING id_conversa;
        """, (id_cliente, id_unidade))

        result = cursor.fetchone()

        if result:
            logger.debug(
                "conversa_insert_resultado | acao=criar_conversa id_cliente=%s id_unidade=%s id_conversa=%s",
                id_cliente,
                id_unidade,
                result[0],
            )
            return result[0]

        raise ValueError(
            f"Anomalia Critica: conversa do cliente {id_cliente} "
            f"e unidade {id_unidade} nao foi criada!"
        )

    except Exception:
        logger.exception(
            "conversa_insert_erro | acao=rollback id_cliente=%s id_unidade=%s",
            id_cliente,
            id_unidade,
        )
        raise


def inserir_historico_mensagem_cliente(
    mensagem,
    id_conversa,
    id_etapa,
    cursor,
):
    cursor.execute("""
        WITH existente AS (
            SELECT id_mensagem, received_data_hora
            FROM chatbot.historico_mensagens
            WHERE id_conversa = %s
              AND quem_enviou = 'cliente'
              AND id_mensagem_fila = %s
              AND id_hash_msg = %s
            ORDER BY received_data_hora DESC, id_mensagem DESC
            LIMIT 1
        ),
        inserido AS (
            INSERT INTO chatbot.historico_mensagens (
                id_conversa,
                id_etapa,
                received_data_hora,
                cliente_telefone,
                conteudo_texto,
                tipo_mensagem,
                id_hash_msg,
                id_mensagem_fila,
                id_hash_cliente_origem,
                id_phone_unidade,
                unidade_telefone,
                quem_enviou,
                status_envio
            )
            SELECT
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                NULL,
                %s,
                %s,
                'cliente',
                NULL
            WHERE NOT EXISTS (SELECT 1 FROM existente)
            RETURNING id_mensagem, received_data_hora
        )
        SELECT id_mensagem, received_data_hora, TRUE AS inserido
        FROM inserido

        UNION ALL

        SELECT id_mensagem, received_data_hora, FALSE AS inserido
        FROM existente

        LIMIT 1;
    """, (
        id_conversa,
        mensagem["id_mensagem"],
        mensagem["id_hash"],
        id_conversa,
        id_etapa,
        mensagem["data_recebimento"],
        mensagem["cliente_telefone"],
        mensagem["conteudo_texto"],
        mensagem["tipo_mensagem"],
        mensagem["id_hash"],
        mensagem["id_mensagem"],
        mensagem["id_phone_unidade"],
        mensagem["unidade_telefone"],
    ))

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Historico do cliente nao foi inserido nem encontrado "
            f"(id_conversa={id_conversa}, id_mensagem={mensagem['id_mensagem']})"
        )

    logger.debug(
        "historico_cliente_insert_resultado | acao=registrar_cliente id_conversa=%s id_mensagem_fila=%s id_historico=%s inserido=%s",
        id_conversa,
        mensagem["id_mensagem"],
        resultado[0],
        bool(resultado[2]),
    )
    return resultado[0], resultado[1], bool(resultado[2])


def inserir_historico_mensagem_bot(contexto_historico, contexto_envio, cursor):
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    id_hash_msg_bot = contexto_envio.get("id_hash_msg_bot")

    if not id_hash_msg_bot:
        raise ValueError("id_hash_msg_bot nao informado para historico do bot")

    cursor.execute("""
        WITH existente AS (
            SELECT id_mensagem, received_data_hora
            FROM chatbot.historico_mensagens
            WHERE id_conversa = %s
              AND quem_enviou = 'bot'
              AND id_mensagem_fila = %s
              AND id_hash_cliente_origem = %s
            ORDER BY received_data_hora DESC, id_mensagem DESC
            LIMIT 1
        ),
        inserido AS (
            INSERT INTO chatbot.historico_mensagens (
                id_conversa,
                id_etapa,
                received_data_hora,
                cliente_telefone,
                conteudo_texto,
                tipo_mensagem,
                id_hash_msg,
                id_mensagem_fila,
                id_hash_cliente_origem,
                id_phone_unidade,
                unidade_telefone,
                quem_enviou,
                status_envio
            )
            SELECT
                %s,
                %s,
                NOW(),
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                %s,
                'bot',
                'sent'
            WHERE NOT EXISTS (SELECT 1 FROM existente)
            RETURNING id_mensagem, received_data_hora
        )
        SELECT id_mensagem, received_data_hora, TRUE AS inserido
        FROM inserido

        UNION ALL

        SELECT id_mensagem, received_data_hora, FALSE AS inserido
        FROM existente

        LIMIT 1;
    """, (
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        mensagem_cliente["id_hash_msg"],
        contexto_historico["id_conversa"],
        contexto_envio["id_etapa_resultante"],
        mensagem_cliente["cliente_telefone"],
        contexto_envio["mensagem_bot"],
        contexto_envio.get("tipo_mensagem", "text"),
        id_hash_msg_bot,
        mensagem_cliente["id_mensagem_fila"],
        mensagem_cliente["id_hash_msg"],
        mensagem_cliente["id_phone_unidade"],
        mensagem_cliente["unidade_telefone"],
    ))

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Historico do bot nao foi inserido nem encontrado "
            f"(id_conversa={contexto_historico['id_conversa']}, "
            f"id_mensagem_fila={mensagem_cliente['id_mensagem_fila']})"
        )

    logger.debug(
        "historico_bot_insert_resultado | acao=registrar_bot id_conversa=%s id_mensagem_fila=%s id_historico=%s inserido=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        resultado[0],
        bool(resultado[2]),
    )
    return resultado[0], resultado[1], bool(resultado[2])
```

---

# Passo 5 - Atualizar repositories de update

Arquivo modificado: `core/repositories/updates.py`

```python
import logging


logger = logging.getLogger("db.updates")


def marcar_mensagem_como_enviada(id_mensagem, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET status = 'sent',
            processing_started_at = NULL,
            last_error = NULL
        WHERE id_mensagem = %s
    """, (id_mensagem,))
    logger.debug(
        "fila_update | acao=marcar_sent id_mensagem=%s linhas=%s",
        id_mensagem,
        cursor.rowcount,
    )


def vincular_mensagem_fila_a_conversa(id_mensagem, id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET id_conversa = %s
        WHERE id_mensagem = %s
          AND (
              id_conversa IS NULL
              OR id_conversa = %s
          );
    """, (id_conversa, id_mensagem, id_conversa))
    logger.debug(
        "fila_update | acao=vincular_conversa id_mensagem=%s id_conversa=%s linhas=%s",
        id_mensagem,
        id_conversa,
        cursor.rowcount,
    )
    return cursor.rowcount


def atualizar_conversa_resposta_bot(id_conversa, id_etapa_resultante, cursor):
    if id_etapa_resultante is None:
        raise ValueError("id_etapa_resultante nao informado para atualizar conversa")

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = %s,
            last_message_from = 'bot',
            last_interaction_at = NOW()
        WHERE id_conversa = %s;
    """, (id_etapa_resultante, id_conversa))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot id_conversa=%s etapa=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def reagendar_mensagem_sem_erro(id_mensagem, cursor, delay_seconds=30):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET
            status = 'pending',
            next_attempt_at = NOW() + (%s * INTERVAL '1 second'),
            processing_started_at = NULL,
            retry_count = GREATEST(COALESCE(retry_count, 0) - 1, 0),
            last_error = NULL
        WHERE id_mensagem = %s;
    """, (delay_seconds, id_mensagem))
    logger.debug(
        "fila_update | acao=reagendar_sem_erro id_mensagem=%s delay=%s linhas=%s",
        id_mensagem,
        delay_seconds,
        cursor.rowcount,
    )
    return cursor.rowcount


def reagendar_mensagem(id_mensagem, erro, max_retry, cursor):
    cursor.execute("""
        UPDATE chatbot.fila_mensagens
        SET
            status = 'pending',
            next_attempt_at = NOW() + INTERVAL '2 minutes',
            processing_started_at = NULL,
            last_error = %s
        WHERE id_mensagem = %s AND retry_count < %s;
    """, (str(erro), id_mensagem, max_retry))
    logger.debug(
        "fila_update | acao=reagendar_com_erro id_mensagem=%s max_retry=%s linhas=%s",
        id_mensagem,
        max_retry,
        cursor.rowcount,
    )
    return cursor.rowcount
```

---

# Passo 6 - Atualizar support functions do worker

Arquivo modificado: `workers/worker_flow/suport_functions.py`

```python
import logging
import time

from core.cache.cache_cliente import salvar_cliente_cache
from core.logging_config import short_value
from core.repositories.inserts import inserir_historico_mensagem_bot
from core.repositories.querys import (
    existe_mensagem_anterior_aberta_conversa,
    unlock_conversa,
)
from core.repositories.updates import (
    atualizar_conversa_resposta_bot,
    marcar_mensagem_como_enviada,
    reagendar_mensagem_sem_erro,
)


logger = logging.getLogger("worker.support")


def criar_estado_ciclo():
    return {
        "id_mensagem": None,
        "id_cliente": None,
        "id_conversa": None,
        "id_unidade": None,
        "estado": None,
        "lock_ok": False,
        "lock_version": None,
        "cliente_telefone": None,
        "id_phone_unidade": None,
        "tipo_mensagem": None,
    }


def montar_mensagem_fila(registro):
    (
        id_mensagem,
        cliente_telefone,
        conteudo_texto,
        tipo_mensagem,
        id_phone_unidade,
        unidade_telefone,
        data_recebimento,
        id_hash,
        retry_count,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "data_recebimento": data_recebimento,
        "id_hash": id_hash,
        "retry_count": retry_count,
    }


def atualizar_estado_com_mensagem(estado_ciclo, mensagem):
    estado_ciclo["id_mensagem"] = mensagem["id_mensagem"]
    estado_ciclo["cliente_telefone"] = mensagem["cliente_telefone"]
    estado_ciclo["id_phone_unidade"] = mensagem["id_phone_unidade"]
    estado_ciclo["tipo_mensagem"] = mensagem["tipo_mensagem"]


def atualizar_estado_com_contexto(estado_ciclo, contexto_banco):
    contexto_conversa = contexto_banco["conversa"]

    estado_ciclo["id_cliente"] = contexto_banco["id_cliente"]
    estado_ciclo["id_unidade"] = contexto_banco["id_unidade"]
    estado_ciclo["id_conversa"] = contexto_conversa["id_conversa"]
    estado_ciclo["estado"] = contexto_conversa["estado"]


def atualizar_estado_lock(estado_ciclo, lock_ok, lock_version):
    estado_ciclo["lock_ok"] = lock_ok
    estado_ciclo["lock_version"] = lock_version


def aguardar_fila_vazia():
    logger.debug("fila_vazia | acao=aguardar segundos=30")
    time.sleep(30)


def confirmar_cache_cliente_se_pendente(contexto_banco):
    if not contexto_banco.get("cliente_cache_pendente"):
        return False

    salvar_cliente_cache(
        contexto_banco["cliente_telefone"],
        contexto_banco["id_cliente"],
    )
    contexto_banco["cliente_cache_pendente"] = False

    logger.debug(
        "cliente_cache_confirmado | acao=salvar cliente=%s id_cliente=%s",
        short_value(contexto_banco["cliente_telefone"]),
        contexto_banco["id_cliente"],
    )
    return True


def logar_lock_recusado(mensagem, contexto_banco):
    contexto_conversa = contexto_banco["conversa"]

    logger.info(
        "conversa_lock_recusado | motivo=conversa_em_processamento acao=continuar id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        contexto_conversa["id_conversa"],
    )


def reagendar_se_houver_mensagem_anterior(
    mensagem,
    contexto_banco,
    lock_version,
    cursor,
):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    existe_anterior = existe_mensagem_anterior_aberta_conversa(
        id_conversa,
        mensagem["id_mensagem"],
        mensagem["data_recebimento"],
        cursor,
    )

    if not existe_anterior:
        return False

    reagendar_mensagem_sem_erro(
        mensagem["id_mensagem"],
        cursor,
        delay_seconds=30,
    )

    logger.info(
        "mensagem_reagendada | motivo=mensagem_anterior_aberta acao=aguardar_ordem id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s lock_version=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        id_conversa,
        lock_version,
    )
    return True


def atualizar_banco_com_contexto_final(contexto_historico, contexto_envio, cursor):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")

    if contexto_envio.get("resposta_ja_existia"):
        atualizar_conversa_resposta_bot(
            id_conversa,
            id_etapa_resultante,
            cursor,
        )

        logger.info(
            "resposta_bot_idempotente | motivo=resposta_ja_existia acao=atualizar_conversa id_conversa=%s etapa=%s id_hash_msg_bot=%s",
            id_conversa,
            id_etapa_resultante,
            contexto_envio.get("id_hash_msg_bot"),
        )
        return {
            "historico_bot_inserido": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
            "id_etapa_resultante": id_etapa_resultante,
        }

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    id_historico_bot, data_historico_bot, historico_inserido = (
        inserir_historico_mensagem_bot(
            contexto_historico,
            contexto_envio,
            cursor,
        )
    )

    atualizar_conversa_resposta_bot(
        id_conversa,
        id_etapa_resultante,
        cursor,
    )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_conversa id_conversa=%s id_historico_bot=%s inserido=%s etapa=%s id_hash_msg_bot=%s",
        id_conversa,
        id_historico_bot,
        historico_inserido,
        id_etapa_resultante,
        contexto_envio.get("id_hash_msg_bot"),
    )

    return {
        "historico_bot_inserido": historico_inserido,
        "resposta_ja_existia": False,
        "id_historico_bot": id_historico_bot,
        "data_historico_bot": data_historico_bot,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
    }


def finalizar_mensagem_processada(
    mensagem,
    contexto_banco,
    lock_version,
    cursor,
):
    contexto_conversa = contexto_banco["conversa"]

    marcar_mensagem_como_enviada(mensagem["id_mensagem"], cursor)

    logger.info(
        "mensagem_processada | acao=marcar_sent id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s estado=%s lock_version=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        contexto_conversa["id_conversa"],
        contexto_conversa["estado"],
        lock_version,
    )


def liberar_lock_conversa_se_necessario(cursor, estado_ciclo):
    if not (
        estado_ciclo["lock_ok"]
        and estado_ciclo["id_conversa"]
        and estado_ciclo["lock_version"] is not None
    ):
        return None

    unlock_realizado = unlock_conversa(
        estado_ciclo["id_conversa"],
        estado_ciclo["lock_version"],
        cursor,
    )

    logger.debug(
        "conversa_unlock | acao=liberar id_conversa=%s lock_version=%s liberada=%s",
        estado_ciclo["id_conversa"],
        estado_ciclo["lock_version"],
        unlock_realizado,
    )
    return unlock_realizado
```

---

# Passo 7 - Atualizar flow_sender

Arquivo modificado: `workers/worker_flow/flow_sender.py`

```python
import logging

from core.integrations.whatsapp.sender import sender_etapa1


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resposta = contexto_historico["id_etapa_resposta"]
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    id_phone_unidade = mensagem_cliente_atual["id_phone_unidade"]

    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_sender_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_resposta=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            resposta_bot_atual.get("id_mensagem"),
            resposta_bot_atual.get("id_etapa"),
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "mensagem_bot": resposta_bot_atual.get("conteudo_texto"),
            "tipo_mensagem": resposta_bot_atual.get("tipo_mensagem", "text"),
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
        }

    if retry_count > 1:
        logger.info(
            "flow_sender_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            retry_count,
        )

    if id_etapa_resposta == 1:
        return sender_etapa1(
            cliente_telefone=cliente_telefone,
            phone_id_unidade=id_phone_unidade,
        )

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa=%s",
        id_conversa,
        id_etapa_resposta,
    )
    raise NotImplementedError(
        f"Sender da etapa {id_etapa_resposta} ainda nao implementado"
    )
```

---

# Passo 8 - Atualizar worker_flow

Arquivo modificado: `workers/worker_flow/worker_flow.py`

```python
import logging

import psycopg2

from core.cache.cache_unidade import UnidadeNaoEncontrada
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.logging_config import short_value
from core.repositories.querys import pegar_mensagens_da_fila, tentar_lock_conversa
from core.repositories.updates import vincular_mensagem_fila_a_conversa
from workers.tratamento_erro.erro_conexao import handle_erro_conexao
from workers.tratamento_erro.erro_generico import handle_erro_generico
from workers.tratamento_erro.exceptions import BancoFalhouAposEnvioMeta
from workers.tratamento_erro.unidade_nao_encontrada import handle_unidade_nao_encontrada
from workers.worker_flow.flow_sender import flow_sender
from workers.worker_flow.suport_functions import (
    aguardar_fila_vazia,
    atualizar_banco_com_contexto_final,
    atualizar_estado_com_contexto,
    atualizar_estado_com_mensagem,
    atualizar_estado_lock,
    confirmar_cache_cliente_se_pendente,
    criar_estado_ciclo,
    finalizar_mensagem_processada,
    liberar_lock_conversa_se_necessario,
    logar_lock_recusado,
    montar_mensagem_fila,
    reagendar_se_houver_mensagem_anterior,
)
from workers.worker_flow.tratar_bloqueio import tratar_conversa_bloqueada
from workers.worker_flow.valida_banco import validar_banco_mensagem
from workers.worker_flow.valida_historico import valida_historico


logger = logging.getLogger("worker.flow")


def worker_flow():
    logger.info("worker_iniciado")

    max_retry = 3
    retry_delay = 5

    while True:
        print("---------------------NOVO CICLO---------------------")
        logger.info("---------- ciclo_worker_inicio ----------")

        conn_ciclo = None
        cursor_ciclo = None
        estado_ciclo = criar_estado_ciclo()

        try:
            conn_ciclo = get_conn(application_name="worker_chatbot")
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5
            logger.debug("ciclo_conexao_banco_ok | acao=dequeue")

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                aguardar_fila_vazia()
                continue

            mensagem = montar_mensagem_fila(registro)
            atualizar_estado_com_mensagem(estado_ciclo, mensagem)

            logger.info(
                "mensagem_processando | acao=iniciar id_mensagem=%s cliente=%s phone_number_id=%s tipo=%s retry=%s",
                mensagem["id_mensagem"],
                short_value(mensagem["cliente_telefone"]),
                short_value(mensagem["id_phone_unidade"]),
                mensagem["tipo_mensagem"],
                mensagem["retry_count"],
            )

            contexto_banco = validar_banco_mensagem(
                mensagem,
                cursor_ciclo,
            )
            atualizar_estado_com_contexto(estado_ciclo, contexto_banco)

            contexto_conversa = contexto_banco["conversa"]
            id_conversa = contexto_conversa["id_conversa"]

            vincular_mensagem_fila_a_conversa(
                mensagem["id_mensagem"],
                id_conversa,
                cursor_ciclo,
            )
            conn_ciclo.commit()
            logger.debug(
                "mensagem_conversa_vinculada | acao=commit id_mensagem=%s id_conversa=%s estado=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_conversa["estado"],
            )

            confirmar_cache_cliente_se_pendente(contexto_banco)

            if contexto_conversa["estado"] == "bloqueada":
                tratar_conversa_bloqueada(
                    mensagem["id_mensagem"],
                    mensagem["cliente_telefone"],
                    mensagem["id_phone_unidade"],
                    id_conversa,
                    cursor_ciclo,
                )
                conn_ciclo.commit()
                continue

            lock_ok, lock_version = tentar_lock_conversa(id_conversa, cursor_ciclo)
            conn_ciclo.commit()
            atualizar_estado_lock(estado_ciclo, lock_ok, lock_version)

            if not lock_ok:
                logar_lock_recusado(mensagem, contexto_banco)
                continue

            if reagendar_se_houver_mensagem_anterior(
                mensagem,
                contexto_banco,
                lock_version,
                cursor_ciclo,
            ):
                conn_ciclo.commit()
                continue

            contexto_historico = valida_historico(
                mensagem,
                contexto_banco,
                cursor_ciclo,
            )
            conn_ciclo.commit()
            logger.debug(
                "historico_contexto_ok | acao=commit id_mensagem=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s inserido=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_historico["id_etapa_cliente"],
                contexto_historico["id_etapa_resposta"],
                contexto_historico["mensagem_cliente_inserida"],
            )

            contexto_envio = flow_sender(contexto_historico)

            try:
                contexto_final = atualizar_banco_com_contexto_final(
                    contexto_historico,
                    contexto_envio,
                    cursor_ciclo,
                )
                conn_ciclo.commit()

            except Exception as erro:
                if contexto_envio.get("enviou"):
                    raise BancoFalhouAposEnvioMeta(
                        "Banco falhou depois da Meta confirmar envio",
                        id_mensagem=mensagem["id_mensagem"],
                        id_conversa=id_conversa,
                        id_hash_msg_bot=contexto_envio.get("id_hash_msg_bot"),
                        id_etapa=contexto_envio.get("id_etapa_resultante"),
                    ) from erro

                raise

            logger.debug(
                "resposta_bot_contexto_final_ok | acao=commit id_mensagem=%s id_conversa=%s etapa=%s resposta_ja_existia=%s id_hash_msg_bot=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_final["id_etapa_resultante"],
                contexto_final["resposta_ja_existia"],
                contexto_final["id_hash_msg_bot"],
            )

            finalizar_mensagem_processada(
                mensagem,
                contexto_banco,
                lock_version,
                cursor_ciclo,
            )
            conn_ciclo.commit()

        except ErroEnvioMeta as erro:
            logger.warning(
                "meta_envio_erro | acao=reagendar_sem_sent id_mensagem=%s cliente=%s phone_number_id=%s etapa=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro.id_etapa,
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except BancoFalhouAposEnvioMeta as erro:
            logger.critical(
                "banco_falhou_apos_envio_meta | risco=resposta_duplicada acao=reagendar_sem_sent id_mensagem=%s id_conversa=%s etapa=%s id_hash_msg_bot=%s erro=%s",
                erro.id_mensagem,
                erro.id_conversa,
                erro.id_etapa,
                erro.id_hash_msg_bot,
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except psycopg2.OperationalError as erro:
            logger.warning(
                "banco_operacional_erro | acao=retry_conexao id_mensagem=%s erro=%s",
                estado_ciclo["id_mensagem"],
                erro,
            )
            retry_delay = handle_erro_conexao(erro, retry_delay)
            continue

        except UnidadeNaoEncontrada as erro:
            logger.warning(
                "unidade_nao_encontrada | acao=tratar_unidade_invalida id_mensagem=%s cliente=%s phone_number_id=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_unidade_nao_encontrada(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        except Exception as erro:
            logger.exception(
                "mensagem_erro | acao=tratar_erro_generico id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s estado=%s erro=%s",
                estado_ciclo["id_mensagem"],
                short_value(estado_ciclo["cliente_telefone"]),
                short_value(estado_ciclo["id_phone_unidade"]),
                estado_ciclo["id_conversa"],
                estado_ciclo["estado"],
                erro,
            )
            if conn_ciclo:
                conn_ciclo.rollback()

            handle_erro_generico(
                cursor_ciclo,
                estado_ciclo["id_mensagem"],
                erro,
                max_retry,
            )

            if conn_ciclo:
                conn_ciclo.commit()

        finally:
            if conn_ciclo:
                try:
                    unlock_realizado = liberar_lock_conversa_se_necessario(
                        cursor_ciclo,
                        estado_ciclo,
                    )

                    if unlock_realizado is not None:
                        conn_ciclo.commit()

                    conn_ciclo.close()

                except Exception as erro:
                    logger.warning("finalizacao_ciclo_falhou | erro=%s", erro)
```

---

# Passo 9 - Validacao

Rodar:

```powershell
C:\Chatbot\venv\.venv\Scripts\python.exe -m compileall -q core callback workers main.py
C:\Chatbot\venv\.venv\Scripts\python.exe callback\manage.py check
```

Validar manualmente com banco recriado:

1. Criar unidade ativa no admin.
2. Enviar uma mensagem real para o numero da unidade.
3. Confirmar que o webhook enfileira apenas a mensagem valida.
4. Ligar worker.
5. Confirmar que a etapa 1 envia `"Ola!"` pela Meta.
6. Confirmar no banco:
   - mensagem do cliente no `historico_mensagens`;
   - mensagem do bot no `historico_mensagens` com `quem_enviou='bot'`, `status_envio='sent'`, `id_mensagem_fila` e `id_hash_cliente_origem`;
   - conversa com `last_message_from='bot'` e `id_etapa_atual=1`;
   - fila com `status='sent'`.
7. Simular erro da Meta usando mock ou token invalido em ambiente de teste:
   - nao deve inserir historico do bot;
   - nao deve atualizar conversa para bot;
   - nao deve marcar fila como `sent`;
   - deve logar `meta_envio_erro`.
8. Simular falha de banco depois de envio Meta, se possivel em teste controlado:
   - deve logar `banco_falhou_apos_envio_meta`;
   - mensagem nao deve virar `sent`;
   - retry posterior pode duplicar resposta, risco aceito e monitorado na V1.

## Observacao sobre retry da Meta

O plano usa o handler atual de erro generico tambem para `ErroEnvioMeta`. Isso significa que a fila sera reagendada com `last_error` e `next_attempt_at` para retry, sem marcar `sent`.

Se a decisao for nao contar erro da Meta no `max_retry`, o ajuste deve ser discutido antes da implementacao, porque hoje o handler generico tambem e responsavel por remover mensagens que estouraram `max_retry`.
