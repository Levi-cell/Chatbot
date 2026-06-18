# Experimento: last_message_from semantico

## Objetivo

Este documento descreve um experimento controlado para transformar
`conversa.last_message_from` em um campo semanticamente literal durante toda a
conversa, sem remover as protecoes atuais de fila, lock, retry e idempotencia:

```text
cliente envia mensagem
worker registra mensagem do cliente no historico
conversa.last_message_from = cliente
bot responde
worker registra mensagem do bot no historico
conversa.last_message_from = bot
cliente responde
ciclo se repete
```

Hoje, na V1, `last_message_from` tende a ficar `bot` depois da primeira resposta
do bot. Isso funciona, mas o nome da coluna deixa de representar a ultima
mensagem fisica registrada no historico.

O experimento continua aceitando o risco raro ja conhecido:

```text
Meta confirma envio
banco ou worker falha antes de registrar a resposta do bot
retry pode enviar a resposta novamente
```

O objetivo deste documento nao e eliminar essa pequena janela de duplicidade.
O objetivo e melhorar a semantica de `last_message_from` sem permitir que uma
etapa seja pulada ou retrocedida.

## Ponto critico

Nao basta atualizar `last_message_from = cliente` quando a mensagem do cliente entra no historico.

Se fizer apenas isso, o `valida_historico` pode parar de avancar etapa, porque hoje ele usa `last_message_from == "bot"` para decidir se deve responder a proxima etapa.

Portanto, este experimento tambem muda a regra de calculo de etapa:

```python
if id_etapa_atual is None:
    id_etapa_resposta = 1
else:
    id_etapa_resposta = min(id_etapa_atual + 1, 7)
```

Ou seja: a etapa de resposta passa a depender da etapa atual da conversa, nao
de `last_message_from`.

Em retry, a etapa nao pode ser reconstruida apenas com a etapa atual da
conversa. A mensagem do cliente pode ter sido registrada em uma etapa anterior
e a resposta do bot pode ja ter avancado a conversa. Por isso:

```text
id_etapa_cliente = etapa persistida no historico do cliente

se resposta do bot ja existe:
    id_etapa_resposta = etapa persistida na resposta do bot
se resposta do bot ainda nao existe:
    id_etapa_resposta = proxima etapa calculada pela conversa
```

## Regra transacional desejada

1. Worker pega mensagem da fila.
2. Worker valida cliente, unidade e conversa.
3. Worker insere mensagem do cliente no historico.
4. Se ainda nao existe resposta do bot para essa mensagem, worker atualiza `last_message_from = cliente`.
5. Commit.
6. Worker decide resposta/tratamento.
7. Worker envia mensagem na Meta.
8. Worker insere historico do bot.
9. Se for fluxo normal, atualiza etapa e `last_message_from = bot`.
10. Se for tratamento sem avancar etapa, atualiza apenas `last_message_from = bot` e `last_interaction_at`.
11. Commit.
12. Worker marca fila como `sent`.
13. Commit final.

## Por que o item 4 depende de resposta do bot nao existir

Em retry, pode acontecer de a resposta do bot ja estar registrada para a mensagem atual.

Se `valida_historico` sempre atualizasse `last_message_from = cliente`, poderia desfazer um estado ja recuperado como `bot`.

Por isso:

```text
se ja existe historico do bot vinculado a esta mensagem da fila:
    usa as etapas persistidas no historico
    garante last_message_from = bot
se ainda nao existe resposta do bot:
    muda last_message_from para cliente
```

## Garantias obrigatorias

- `last_message_from` nao decide mais se a etapa deve avancar;
- a etapa persistida no historico do cliente vence qualquer valor reconstruido;
- resposta do bot ja existente vence qualquer novo calculo de etapa;
- resposta normal pode manter ou avancar apenas uma etapa;
- resposta normal nunca retrocede a conversa;
- tratamento registra `bot` sem avancar etapa;
- webhook libera novo turno somente por resposta do bot vinculada a mensagem
  aberta, sem depender de `last_message_from`;
- commits, rollbacks, locks, handlers e marcacao `sent` permanecem no
  `flow_worker.py` exatamente na ordem atual;
- o novo roteador `rotear_resposta_cliente.py` permanece inalterado.

## Passo 1 - Alterar `core/repositories/inserts.py`

Arquivo modificado.

Motivo: quando a mensagem do cliente ja existe, a funcao precisa devolver a
etapa realmente persistida. Isso impede que um retry reconstrua a mensagem
antiga usando a etapa mais nova da conversa.

Codigo completo:

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
            SELECT id_mensagem, received_data_hora, id_etapa
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
            RETURNING id_mensagem, received_data_hora, id_etapa
        )
        SELECT id_mensagem, received_data_hora, id_etapa, TRUE AS inserido
        FROM inserido

        UNION ALL

        SELECT id_mensagem, received_data_hora, id_etapa, FALSE AS inserido
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
        "historico_cliente_insert_resultado | acao=registrar_cliente id_conversa=%s id_mensagem_fila=%s id_historico=%s etapa=%s inserido=%s",
        id_conversa,
        mensagem["id_mensagem"],
        resultado[0],
        resultado[2],
        bool(resultado[3]),
    )
    return resultado[0], resultado[1], resultado[2], bool(resultado[3])


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

## Passo 2 - Alterar `core/repositories/updates.py`

Arquivo modificado.

Codigo completo:

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


def atualizar_conversa_mensagem_cliente(id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'cliente',
            last_interaction_at = NOW()
        WHERE id_conversa = %s;
    """, (id_conversa,))

    logger.debug(
        "conversa_update | acao=registrar_mensagem_cliente id_conversa=%s linhas=%s",
        id_conversa,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com mensagem do cliente "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_resposta_bot(id_conversa, id_etapa_resultante, cursor):
    if id_etapa_resultante is None:
        raise ValueError("id_etapa_resultante nao informado para atualizar conversa")

    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            id_etapa_atual = CASE
                WHEN id_etapa_atual IS NULL THEN %s
                ELSE GREATEST(id_etapa_atual, %s)
            END,
            last_message_from = 'bot',
            last_interaction_at = NOW()
        WHERE id_conversa = %s
          AND (
              (id_etapa_atual IS NULL AND %s = 1)
              OR
              (
                  id_etapa_atual IS NOT NULL
                  AND %s <= id_etapa_atual + 1
              )
          );
    """, (
        id_etapa_resultante,
        id_etapa_resultante,
        id_conversa,
        id_etapa_resultante,
        id_etapa_resultante,
    ))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot id_conversa=%s etapa=%s linhas=%s",
        id_conversa,
        id_etapa_resultante,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot; conversa "
            "inexistente ou transicao de etapa invalida "
            f"(id_conversa={id_conversa}, etapa={id_etapa_resultante}, "
            f"linhas={cursor.rowcount})"
        )

    return cursor.rowcount


def atualizar_conversa_resposta_bot_sem_avancar(id_conversa, cursor):
    cursor.execute("""
        UPDATE chatbot.conversa
        SET
            last_message_from = 'bot',
            last_interaction_at = NOW()
        WHERE id_conversa = %s;
    """, (id_conversa,))

    logger.debug(
        "conversa_update | acao=registrar_resposta_bot_sem_avancar id_conversa=%s linhas=%s",
        id_conversa,
        cursor.rowcount,
    )

    if cursor.rowcount != 1:
        raise ValueError(
            "Conversa nao foi atualizada com resposta do bot sem avancar etapa "
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

## Passo 3 - Alterar `workers/worker_flow/valida_historico.py`

Arquivo modificado.

Codigo completo:

```python
import logging

from core.logging_config import short_value
from core.repositories.inserts import inserir_historico_mensagem_cliente
from core.repositories.querys import buscar_resposta_bot_por_mensagem_cliente
from core.repositories.updates import (
    atualizar_conversa_mensagem_cliente,
    atualizar_conversa_resposta_bot_sem_avancar,
)


logger = logging.getLogger("worker.valida_historico")

ETAPA_INICIAL = 1
ETAPA_FINAL = 7


def valida_historico(mensagem, contexto_banco, cursor):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    last_message_from_entrada = contexto_conversa.get("last_message_from")

    id_etapa_para_insert = _resolver_etapa_cliente(contexto_conversa)

    (
        id_historico_cliente,
        data_historico_cliente,
        id_etapa_cliente,
        cliente_inserido_no_historico,
    ) = inserir_historico_mensagem_cliente(
        mensagem=mensagem,
        id_conversa=id_conversa,
        id_etapa=id_etapa_para_insert,
        cursor=cursor,
    )

    mensagem_cliente_atual = {
        "id_mensagem": id_historico_cliente,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa_cliente,
        "received_data_hora": data_historico_cliente,
        "cliente_telefone": mensagem["cliente_telefone"],
        "conteudo_texto": mensagem["conteudo_texto"],
        "tipo_mensagem": mensagem["tipo_mensagem"],
        "id_hash_msg": mensagem["id_hash"],
        "id_mensagem_fila": mensagem["id_mensagem"],
        "id_hash_cliente_origem": None,
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "unidade_telefone": mensagem["unidade_telefone"],
        "quem_enviou": "cliente",
        "status_envio": None,
    }

    resposta_bot_para_mensagem_atual = _normalizar_resposta_bot(
        buscar_resposta_bot_por_mensagem_cliente(
            id_conversa=id_conversa,
            id_mensagem_fila=mensagem["id_mensagem"],
            id_hash_cliente_origem=mensagem["id_hash"],
            cursor=cursor,
        )
    )

    if resposta_bot_para_mensagem_atual:
        id_etapa_resposta = resposta_bot_para_mensagem_atual["id_etapa"]

        if last_message_from_entrada != "bot":
            atualizar_conversa_resposta_bot_sem_avancar(id_conversa, cursor)

        last_message_from_saida = "bot"
    else:
        id_etapa_resposta = _resolver_etapa_resposta(contexto_conversa)
        atualizar_conversa_mensagem_cliente(id_conversa, cursor)
        last_message_from_saida = "cliente"

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s etapa_resposta=%s last_from_entrada=%s last_from_saida=%s retry=%s resposta_bot_existente=%s cliente=%s phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        last_message_from_entrada,
        last_message_from_saida,
        mensagem["retry_count"],
        bool(resposta_bot_para_mensagem_atual),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    return {
        "id_conversa": id_conversa,
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        "id_etapa_resposta": id_etapa_resposta,
        "status_dependente": contexto_conversa.get("status_dependente"),
        "last_message_from": last_message_from_saida,
        "last_message_from_entrada": last_message_from_entrada,
        "mensagem_cliente_atual": mensagem_cliente_atual,
        "mensagem_cliente_inserida": cliente_inserido_no_historico,
        "resposta_bot_para_mensagem_atual": resposta_bot_para_mensagem_atual,
        "texto_cliente_atual": mensagem["conteudo_texto"],
        "tipo_mensagem_atual": mensagem["tipo_mensagem"],
        "retry_count": mensagem["retry_count"],
        "precisa_tratamento_erro": False,
        "motivo_tratamento_erro": None,
    }


def _resolver_etapa_cliente(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return id_etapa_atual


def _resolver_etapa_resposta(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return min(id_etapa_atual + 1, ETAPA_FINAL)


def _normalizar_linha_historico(registro):
    (
        id_mensagem,
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
        status_envio,
    ) = registro

    return {
        "id_mensagem": id_mensagem,
        "id_conversa": id_conversa,
        "id_etapa": id_etapa,
        "received_data_hora": received_data_hora,
        "cliente_telefone": cliente_telefone,
        "conteudo_texto": conteudo_texto,
        "tipo_mensagem": tipo_mensagem,
        "id_hash_msg": id_hash_msg,
        "id_mensagem_fila": id_mensagem_fila,
        "id_hash_cliente_origem": id_hash_cliente_origem,
        "id_phone_unidade": id_phone_unidade,
        "unidade_telefone": unidade_telefone,
        "quem_enviou": quem_enviou,
        "status_envio": status_envio,
    }


def _normalizar_resposta_bot(registro):
    if not registro:
        return None

    return _normalizar_linha_historico(registro)
```

## Passo 4 - Alterar `workers/worker_flow/suport_functions.py`

Arquivo modificado.

Codigo completo:

```python
import logging
import time

from core.cache.runtime.cache_cliente import remover_cliente_cache, salvar_cliente_cache
from core.cache.cache_unidade import recarregar_cache_unidades
from core.logging_config import short_value
from core.repositories.inserts import inserir_historico_mensagem_bot
from core.repositories.querys import (
    existe_mensagem_anterior_aberta_conversa,
    unlock_conversa,
)
from core.repositories.updates import (
    atualizar_conversa_resposta_bot,
    atualizar_conversa_resposta_bot_sem_avancar,
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


def reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo):
    erro_texto = str(erro)

    if "conversa_id_cliente_fkey" not in erro_texto:
        return False

    cliente_telefone = estado_ciclo.get("cliente_telefone")

    if not cliente_telefone:
        return False

    removido = remover_cliente_cache(cliente_telefone)

    logger.warning(
        "cliente_cache_stale_reparado | motivo=fk_cliente_inexistente acao=remover_cache cliente=%s id_mensagem=%s removido=%s",
        short_value(cliente_telefone),
        estado_ciclo.get("id_mensagem"),
        removido,
    )
    return removido


def reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo):
    erro_texto = str(erro)

    if "conversa_id_unidade_fkey" not in erro_texto:
        return False

    total_unidades = recarregar_cache_unidades()

    logger.warning(
        "unidade_cache_stale_reparado | motivo=fk_unidade_inexistente acao=recarregar_cache_unidades phone_number_id=%s id_mensagem=%s unidades=%s",
        short_value(estado_ciclo.get("id_phone_unidade")),
        estado_ciclo.get("id_mensagem"),
        total_unidades,
    )
    return total_unidades is not None


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
    atualizar_conversa = contexto_envio.get("atualizar_conversa", True)
    atualizar_last_from_bot = contexto_envio.get("atualizar_last_from_bot", True)

    if contexto_envio.get("resposta_ja_existia"):
        if atualizar_conversa:
            atualizar_conversa_resposta_bot(
                id_conversa,
                id_etapa_resultante,
                cursor,
            )
        elif atualizar_last_from_bot:
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                cursor,
            )

        logger.info(
            "resposta_bot_idempotente | motivo=resposta_ja_existia acao=atualizar_contexto id_conversa=%s etapa=%s id_hash_msg_bot=%s atualizar_conversa=%s atualizar_last_from_bot=%s",
            id_conversa,
            id_etapa_resultante,
            contexto_envio.get("id_hash_msg_bot"),
            atualizar_conversa,
            atualizar_last_from_bot,
        )
        return {
            "historico_bot_inserido": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
            "id_etapa_resultante": id_etapa_resultante,
            "atualizar_conversa": atualizar_conversa,
            "atualizar_last_from_bot": atualizar_last_from_bot,
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

    if atualizar_conversa:
        atualizar_conversa_resposta_bot(
            id_conversa,
            id_etapa_resultante,
            cursor,
        )
    elif atualizar_last_from_bot:
        atualizar_conversa_resposta_bot_sem_avancar(
            id_conversa,
            cursor,
        )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto id_conversa=%s id_historico_bot=%s inserido=%s etapa=%s id_hash_msg_bot=%s atualizar_conversa=%s atualizar_last_from_bot=%s",
        id_conversa,
        id_historico_bot,
        historico_inserido,
        id_etapa_resultante,
        contexto_envio.get("id_hash_msg_bot"),
        atualizar_conversa,
        atualizar_last_from_bot,
    )

    return {
        "historico_bot_inserido": historico_inserido,
        "resposta_ja_existia": False,
        "id_historico_bot": id_historico_bot,
        "data_historico_bot": data_historico_bot,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "atualizar_conversa": atualizar_conversa,
        "atualizar_last_from_bot": atualizar_last_from_bot,
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

## Passo 5 - Alterar `core/integrations/whatsapp/sender_tratamento.py`

Arquivo modificado.

Codigo completo:

```python
import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.senders import (
    enviar_mensagem_texto_com_botao,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.sender_tratamento")


def sender_tratamento_tipo_nao_suportado(
    cliente_telefone,
    phone_id_unidade,
    id_etapa,
    tipo_mensagem,
    mensagem_bot,
):
    titulo_botao = "Retornar ao atendimento"

    try:
        id_hash_msg_bot = enviar_mensagem_texto_com_botao(
            to=cliente_telefone,
            text=mensagem_bot,
            titulo_botao=titulo_botao,
            phone_id_unidade=phone_id_unidade,
            callback_data="retornar_atendimento",
        )

        logger.info(
            "sender_tratamento_tipo_nao_suportado_ok | acao=enviar_meta cliente=%s phone_number_id=%s etapa=%s tipo_cliente=%s id_hash_msg_bot=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_etapa,
            tipo_mensagem,
            id_hash_msg_bot,
        )

        return {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": id_etapa,
            "tipo_mensagem": "interactive_button",
            "canal": "meta_whatsapp",
            "tratamento": True,
            "tipo_tratamento": "tipo_mensagem_nao_suportado",
            "atualizar_conversa": False,
            "atualizar_last_from_bot": True,
        }

    except Exception as erro:
        logger.exception(
            "sender_tratamento_tipo_nao_suportado_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s etapa=%s tipo_cliente=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_etapa,
            tipo_mensagem,
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar tratamento de tipo de mensagem nao suportado",
            id_etapa=id_etapa,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
```

## Passo 6 - Alterar `workers/worker_flow/response_flow/flow_treat_unsupported_type.py`

Arquivo modificado.

Codigo completo:

```python
import logging

from core.integrations.whatsapp.sender_tratamento import (
    sender_tratamento_tipo_nao_suportado,
)


logger = logging.getLogger("worker.treat_unsupported_type")


def flow_treat_unsupported_type(contexto_historico, contexto_validacao):
    # Regra de negocio V1: esta versao nao trabalha com midias/anexos.
    # Midia recebida entra no historico, recebe tratamento e nao avanca etapa.
    id_conversa = contexto_historico["id_conversa"]
    retry_count = contexto_historico["retry_count"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_unsupported_type_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s tratamento=%s retry=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            contexto_validacao["tipo_tratamento"],
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
            "tratamento": True,
            "tipo_tratamento": contexto_validacao["tipo_tratamento"],
            "atualizar_conversa": False,
            "atualizar_last_from_bot": True,
        }

    if retry_count > 1:
        logger.info(
            "flow_treat_unsupported_type_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s tratamento=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            retry_count,
            contexto_validacao["tipo_tratamento"],
        )

    if contexto_validacao["tipo_tratamento"] == "tipo_mensagem_nao_suportado":
        mensagem_bot = _montar_mensagem_tipo_nao_suportado(contexto_historico)

        return sender_tratamento_tipo_nao_suportado(
            cliente_telefone=mensagem_cliente_atual["cliente_telefone"],
            phone_id_unidade=mensagem_cliente_atual["id_phone_unidade"],
            id_etapa=contexto_historico["id_etapa_cliente"],
            tipo_mensagem=contexto_validacao.get("tipo_mensagem"),
            mensagem_bot=mensagem_bot,
        )

    logger.warning(
        "flow_treat_unsupported_type_nao_implementado | acao=erro id_conversa=%s tratamento=%s",
        id_conversa,
        contexto_validacao["tipo_tratamento"],
    )
    raise NotImplementedError(
        f"Tratamento {contexto_validacao['tipo_tratamento']} ainda nao implementado"
    )


def _montar_mensagem_tipo_nao_suportado(contexto_historico):
    if contexto_historico.get("id_etapa_atual") is None:
        return (
            "Ola! Vi que voce iniciou o atendimento com uma midia.\n\n"
            "Por enquanto eu so consigo continuar por mensagem de texto ou botoes. "
            "Envie uma mensagem de texto para comecarmos."
        )

    return (
        "Recebi uma midia, mas nesta etapa eu preciso que voce responda por texto "
        "ou use os botoes disponiveis.\n\n"
        "Envie uma mensagem de texto para continuarmos."
    )
```

## Passo 7 - Alterar `workers/worker_flow/response_flow/flow_treat_context.py`

Arquivo modificado.

Codigo completo:

```python
import logging


logger = logging.getLogger("worker.treat_context")


def flow_treat_context(contexto_historico, contexto_validacao):
    # Esqueleto reservado para a V1 quando as regras de contexto por etapa
    # forem definidas. Tratamento de contexto deve usar id_etapa_cliente,
    # repetir a pergunta/opcoes da etapa atual e nao avancar a conversa.
    id_conversa = contexto_historico["id_conversa"]
    retry_count = contexto_historico["retry_count"]
    id_etapa_cliente = contexto_historico["id_etapa_cliente"]
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    if resposta_bot_atual:
        logger.info(
            "flow_treat_context_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_cliente=%s tratamento=%s retry=%s",
            id_conversa,
            mensagem_cliente_atual["id_mensagem_fila"],
            mensagem_cliente_atual["id_hash_msg"],
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_cliente,
            contexto_validacao["tipo_tratamento"],
            retry_count,
        )
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": resposta_bot_atual.get("id_etapa"),
            "tratamento": True,
            "tipo_tratamento": contexto_validacao["tipo_tratamento"],
            "atualizar_conversa": False,
            "atualizar_last_from_bot": True,
        }

    logger.warning(
        "flow_treat_context_nao_implementado | acao=erro id_conversa=%s etapa_cliente=%s id_mensagem_fila=%s resultado=%s retry=%s",
        id_conversa,
        id_etapa_cliente,
        mensagem_cliente_atual["id_mensagem_fila"],
        contexto_validacao["resultado"],
        retry_count,
    )
    raise NotImplementedError(
        "Tratamento de mensagem fora de contexto ainda nao implementado"
    )
```

## Passo 8 - Alterar `core/repositories/turno_cliente.py`

Arquivo modificado.

Codigo completo:

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
            LEFT JOIN chatbot.historico_mensagens h
              ON h.id_conversa = f.id_conversa
             AND h.quem_enviou = 'bot'
             AND h.status_envio = 'sent'
             AND h.id_mensagem_fila = f.id_mensagem
             AND h.id_hash_cliente_origem = f.id_hash_msg
            WHERE h.id_mensagem IS NULL
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

## Passo 9 - Alterar `tests/unit/test_repositories.py`

Arquivo modificado.

Codigo completo:

```python
import unittest

from core.repositories import inserts, updates
from tests.helpers import FakeCursor


class RepositoryTests(unittest.TestCase):
    def test_atualizar_conversa_resposta_bot_exige_etapa(self):
        with self.assertRaises(ValueError):
            updates.atualizar_conversa_resposta_bot(10, None, FakeCursor())

    def test_atualizar_conversa_resposta_bot_falha_se_nenhuma_linha(self):
        with self.assertRaises(ValueError):
            updates.atualizar_conversa_resposta_bot(10, 1, FakeCursor(rowcount=0))

    def test_atualizar_conversa_resposta_bot_impede_salto_e_retrocesso(self):
        cursor = FakeCursor(rowcount=1)

        self.assertEqual(updates.atualizar_conversa_resposta_bot(10, 2, cursor), 1)
        sql, params = cursor.calls[0]

        self.assertIn("UPDATE chatbot.conversa", sql)
        self.assertIn("GREATEST(id_etapa_atual", sql)
        self.assertIn("id_etapa_atual + 1", sql)
        self.assertEqual(params, (2, 2, 10, 2, 2))

    def test_inserir_historico_cliente_retorna_etapa_persistida(self):
        cursor = FakeCursor(
            fetchone_result=(100, "2026-01-01T00:00:00", 1, False)
        )
        mensagem = {
            "id_mensagem": 20,
            "cliente_telefone": "5571999999999",
            "conteudo_texto": "ola",
            "tipo_mensagem": "text",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
            "data_recebimento": "2026-01-01T00:00:00",
            "id_hash": "wamid.cliente",
        }

        resultado = inserts.inserir_historico_mensagem_cliente(
            mensagem,
            id_conversa=10,
            id_etapa=2,
            cursor=cursor,
        )

        self.assertEqual(
            resultado,
            (100, "2026-01-01T00:00:00", 1, False),
        )
        sql, _params = cursor.calls[0]
        self.assertIn("SELECT id_mensagem, received_data_hora, id_etapa", sql)

    def test_inserir_historico_mensagem_bot_exige_id_hash_bot(self):
        with self.assertRaises(ValueError):
            inserts.inserir_historico_mensagem_bot(
                {
                    "id_conversa": 10,
                    "mensagem_cliente_atual": {
                        "id_mensagem_fila": 20,
                        "id_hash_msg": "wamid.cliente",
                    },
                },
                {
                    "id_etapa_resultante": 1,
                    "mensagem_bot": "Ola!",
                },
                FakeCursor(),
            )

    def test_inserir_historico_mensagem_bot_sucesso(self):
        cursor = FakeCursor(
            fetchone_result=(300, "2026-01-01T00:00:00", True)
        )

        resultado = inserts.inserir_historico_mensagem_bot(
            {
                "id_conversa": 10,
                "mensagem_cliente_atual": {
                    "id_mensagem_fila": 20,
                    "id_hash_msg": "wamid.cliente",
                    "cliente_telefone": "5571999999999",
                    "id_phone_unidade": "123456",
                    "unidade_telefone": "5571000000000",
                },
            },
            {
                "id_etapa_resultante": 1,
                "mensagem_bot": "Ola!",
                "id_hash_msg_bot": "wamid.bot",
                "tipo_mensagem": "interactive_button",
            },
            cursor,
        )

        self.assertEqual(resultado, (300, "2026-01-01T00:00:00", True))
        sql, params = cursor.calls[0]

        self.assertIn("INSERT INTO chatbot.historico_mensagens", sql)
        self.assertEqual(params[0:3], (10, 20, "wamid.cliente"))


if __name__ == "__main__":
    unittest.main()
```

## Passo 10 - Alterar `tests/unit/test_worker_support_finalizacao.py`

Arquivo modificado.

Codigo completo:

```python
import unittest
from unittest.mock import patch

from workers.worker_flow import suport_functions as support


def contexto_historico_base():
    return {
        "id_conversa": 10,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
        },
    }


class WorkerSupportFinalizacaoTests(unittest.TestCase):
    def test_atualizar_banco_com_contexto_final_persiste_bot_e_conversa(self):
        chamadas = []

        def fake_inserir_historico(contexto_historico, contexto_envio, cursor):
            chamadas.append(("insert_bot", contexto_historico, contexto_envio, cursor))
            return 300, "2026-01-01T00:00:00", True

        def fake_atualizar_conversa(id_conversa, id_etapa_resultante, cursor):
            chamadas.append(("update_conversa", id_conversa, id_etapa_resultante, cursor))
            return 1

        def fake_atualizar_sem_avancar(*_args, **_kwargs):
            raise AssertionError("fluxo normal deve atualizar conversa com etapa")

        cursor = object()
        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": "Ola!",
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
            "tipo_mensagem": "interactive_button",
        }

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                contexto_envio,
                cursor,
            )

        self.assertEqual([chamada[0] for chamada in chamadas], ["insert_bot", "update_conversa"])
        self.assertTrue(resultado["historico_bot_inserido"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot")
        self.assertTrue(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_tratamento_persiste_bot_sem_avancar_mas_volta_last_from_para_bot(self):
        chamadas = []

        def fake_inserir_historico(contexto_historico, contexto_envio, cursor):
            chamadas.append(("insert_bot", contexto_historico, contexto_envio, cursor))
            return 301, "2026-01-01T00:00:00", True

        def fake_atualizar_conversa(*_args, **_kwargs):
            raise AssertionError("tratamento nao deve atualizar etapa da conversa")

        def fake_atualizar_sem_avancar(id_conversa, cursor):
            chamadas.append(("update_bot_sem_avancar", id_conversa, cursor))
            return 1

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": "Tratamento",
            "id_hash_msg_bot": "wamid.bot.tratamento",
            "id_etapa_resultante": 1,
            "tipo_mensagem": "interactive_button",
            "tratamento": True,
            "atualizar_conversa": False,
            "atualizar_last_from_bot": True,
        }

        cursor = object()

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                contexto_envio,
                cursor,
            )

        self.assertEqual(
            [chamada[0] for chamada in chamadas],
            ["insert_bot", "update_bot_sem_avancar"],
        )
        self.assertTrue(resultado["historico_bot_inserido"])
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_resposta_ja_existia_nao_insere_historico_do_bot(self):
        chamadas = []

        def fake_inserir_historico(*_args, **_kwargs):
            raise AssertionError("nao deve inserir historico quando resposta ja existe")

        def fake_atualizar_conversa(id_conversa, id_etapa_resultante, cursor):
            chamadas.append(("update_conversa", id_conversa, id_etapa_resultante, cursor))
            return 1

        def fake_atualizar_sem_avancar(*_args, **_kwargs):
            raise AssertionError("resposta normal idempotente deve atualizar conversa com etapa")

        cursor = object()

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                },
                cursor,
            )

        self.assertEqual(chamadas, [("update_conversa", 10, 1, cursor)])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])
        self.assertTrue(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_resposta_ja_existia_de_tratamento_nao_atualiza_etapa_mas_volta_last_from_para_bot(self):
        chamadas = []

        def fake_inserir_historico(*_args, **_kwargs):
            raise AssertionError("nao deve inserir historico quando resposta ja existe")

        def fake_atualizar_conversa(*_args, **_kwargs):
            raise AssertionError("tratamento idempotente nao deve atualizar etapa")

        def fake_atualizar_sem_avancar(id_conversa, cursor):
            chamadas.append(("update_bot_sem_avancar", id_conversa, cursor))
            return 1

        cursor = object()

        with patch.object(
            support,
            "inserir_historico_mensagem_bot",
            fake_inserir_historico,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot",
            fake_atualizar_conversa,
        ), patch.object(
            support,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_atualizar_sem_avancar,
        ):
            resultado = support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": False,
                    "resposta_ja_existia": True,
                    "id_hash_msg_bot": "wamid.bot.existente",
                    "id_etapa_resultante": 1,
                    "atualizar_conversa": False,
                    "atualizar_last_from_bot": True,
                },
                cursor,
            )

        self.assertEqual(chamadas, [("update_bot_sem_avancar", 10, cursor)])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertFalse(resultado["historico_bot_inserido"])
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertTrue(resultado["atualizar_last_from_bot"])

    def test_contexto_sem_envio_e_sem_resposta_existente_falha(self):
        with self.assertRaises(ValueError):
            support.atualizar_banco_com_contexto_final(
                contexto_historico_base(),
                {
                    "enviou": False,
                    "resposta_ja_existia": False,
                    "id_etapa_resultante": 1,
                },
                object(),
            )

    def test_reagendar_se_houver_mensagem_anterior_reagenda(self):
        chamadas = []

        def fake_reagendar(id_mensagem, cursor, delay_seconds=30):
            chamadas.append((id_mensagem, delay_seconds, cursor))
            return 1

        mensagem = {
            "id_mensagem": 44,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
            "data_recebimento": "2026-01-01T00:00:00",
        }
        contexto_banco = {"conversa": {"id_conversa": 10}}
        cursor = object()

        with patch.object(
            support,
            "existe_mensagem_anterior_aberta_conversa",
            return_value=True,
        ), patch.object(
            support,
            "reagendar_mensagem_sem_erro",
            fake_reagendar,
        ):
            resultado = support.reagendar_se_houver_mensagem_anterior(
                mensagem,
                contexto_banco,
                lock_version=7,
                cursor=cursor,
            )

        self.assertTrue(resultado)
        self.assertEqual(chamadas, [(44, 30, cursor)])

    def test_reparar_cache_cliente_stale_so_age_com_fk_cliente(self):
        estado = {"cliente_telefone": "5571999999999", "id_mensagem": 1}

        with patch.object(support, "remover_cliente_cache", return_value=True) as remover:
            self.assertTrue(
                support.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError("violates foreign key constraint conversa_id_cliente_fkey"),
                    estado,
                )
            )
            remover.assert_called_once_with("5571999999999")

        with patch.object(support, "remover_cliente_cache", return_value=True) as remover:
            self.assertFalse(
                support.reparar_cache_cliente_stale_se_fk_invalida(
                    RuntimeError("erro qualquer"),
                    estado,
                )
            )
            remover.assert_not_called()


if __name__ == "__main__":
    unittest.main()
```

## Passo 11 - Alterar `tests/unit/test_turno_cliente.py`

Arquivo modificado.

Codigo completo:

```python
import unittest
from unittest.mock import patch

from core.repositories import turno_cliente
from tests.helpers import FakeCursor


class TurnoClienteTests(unittest.TestCase):
    def test_dados_invalidos_bloqueiam_turno(self):
        resultado = turno_cliente.avaliar_turno_cliente_para_fila(
            cursor=object(),
            cliente_telefone="",
            id_phone_unidade="123456",
        )

        self.assertFalse(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "dados_invalidos")

    def test_sem_fila_aberta_libera(self):
        with patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            return_value={
                "existe_fila_aberta": False,
                "todas_abertas_respondidas": False,
                "total_abertas": 0,
                "id_mensagem_bloqueadora": None,
            },
        ):
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone="5571999999999",
                id_phone_unidade="123456",
            )

        self.assertTrue(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "sem_fila_aberta")

    def test_fila_aberta_sem_resposta_bloqueia(self):
        with patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            return_value={
                "existe_fila_aberta": True,
                "todas_abertas_respondidas": False,
                "total_abertas": 1,
                "id_mensagem_bloqueadora": 20,
            },
        ):
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone="5571999999999",
                id_phone_unidade="123456",
            )

        self.assertFalse(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "fila_aberta_sem_resposta_bot")

    def test_fila_aberta_respondida_pelo_bot_libera_recuperacao(self):
        with patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            return_value={
                "existe_fila_aberta": True,
                "todas_abertas_respondidas": True,
                "total_abertas": 1,
                "id_mensagem_bloqueadora": None,
            },
        ):
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone="5571999999999",
                id_phone_unidade="123456",
            )

        self.assertTrue(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "fila_aberta_respondida_bot")

    def test_advisory_lock_usa_phone_id_e_cliente_como_chaves(self):
        cursor = FakeCursor()

        turno_cliente.adquirir_lock_turno_cliente(
            cursor,
            cliente_telefone="5571999999999",
            id_phone_unidade="123456",
        )

        sql, params = cursor.calls[0]
        self.assertIn("pg_advisory_xact_lock", sql)
        self.assertEqual(params, ("123456", "5571999999999"))

    def test_consulta_turno_usa_historico_vinculado_sem_last_from(self):
        cursor = FakeCursor(fetchone_result=(True, True, 1, None))

        resultado = turno_cliente.avaliar_filas_abertas_turno(
            cursor,
            cliente_telefone="5571999999999",
            id_phone_unidade="123456",
        )

        sql, params = cursor.calls[0]
        self.assertNotIn("last_message_from", sql)
        self.assertIn("h.id_mensagem_fila = f.id_mensagem", sql)
        self.assertIn("h.id_hash_cliente_origem = f.id_hash_msg", sql)
        self.assertEqual(params, ("5571999999999", "123456"))
        self.assertTrue(resultado["todas_abertas_respondidas"])


if __name__ == "__main__":
    unittest.main()
```

## Passo 12 - Criar `tests/unit/test_lastfrom_semantico.py`

Arquivo novo.

Codigo completo:

```python
import unittest
from unittest.mock import patch

from workers.worker_flow import valida_historico


def mensagem_base(retry=1):
    return {
        "id_mensagem": 20,
        "cliente_telefone": "5571999999999",
        "conteudo_texto": "ola",
        "tipo_mensagem": "text",
        "id_phone_unidade": "123456",
        "unidade_telefone": "5571000000000",
        "data_recebimento": "2026-01-01T00:00:00",
        "id_hash": "wamid.cliente",
        "retry_count": retry,
    }


def contexto_banco_base(last_from="bot", etapa=1):
    return {
        "conversa": {
            "id_conversa": 10,
            "id_etapa_atual": etapa,
            "status_dependente": False,
            "last_message_from": last_from,
        }
    }


class LastFromSemanticoTests(unittest.TestCase):
    def test_conversa_nova_registra_cliente_e_responde_etapa_um(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            chamadas.append(("insert_cliente", id_conversa, id_etapa, cursor))
            return 100, "2026-01-01T00:00:00", 1, True

        def fake_buscar_resposta(**_kwargs):
            return None

        def fake_update_cliente(id_conversa, cursor):
            chamadas.append(("update_cliente", id_conversa, cursor))
            return 1

        def fake_update_bot(*_args, **_kwargs):
            raise AssertionError("conversa nova ainda nao tem resposta do bot")

        cursor = object()

        with patch.object(
            valida_historico,
            "inserir_historico_mensagem_cliente",
            fake_inserir,
        ), patch.object(
            valida_historico,
            "buscar_resposta_bot_por_mensagem_cliente",
            fake_buscar_resposta,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_mensagem_cliente",
            fake_update_cliente,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_update_bot,
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(),
                contexto_banco_base(last_from="cliente", etapa=None),
                cursor,
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 1)
        self.assertEqual(contexto["last_message_from"], "cliente")
        self.assertEqual(
            [chamada[0] for chamada in chamadas],
            ["insert_cliente", "update_cliente"],
        )

    def test_retry_antes_da_resposta_mantem_etapa_e_last_from_cliente(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            chamadas.append(("insert_cliente", id_conversa, id_etapa, cursor))
            return 100, "2026-01-01T00:00:00", 1, False

        def fake_buscar_resposta(**_kwargs):
            return None

        def fake_update_cliente(id_conversa, cursor):
            chamadas.append(("update_cliente", id_conversa, cursor))
            return 1

        cursor = object()

        with patch.object(
            valida_historico,
            "inserir_historico_mensagem_cliente",
            fake_inserir,
        ), patch.object(
            valida_historico,
            "buscar_resposta_bot_por_mensagem_cliente",
            fake_buscar_resposta,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_mensagem_cliente",
            fake_update_cliente,
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(last_from="cliente", etapa=1),
                cursor,
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 2)
        self.assertEqual(contexto["last_message_from"], "cliente")
        self.assertFalse(contexto["mensagem_cliente_inserida"])

    def test_retry_apos_resposta_usa_etapas_persistidas_sem_regredir(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            chamadas.append(("insert_cliente", id_conversa, id_etapa, cursor))
            return 100, "2026-01-01T00:00:00", 1, False

        def fake_buscar_resposta(**_kwargs):
            return (
                200,
                10,
                2,
                "2026-01-01T00:01:00",
                "5571999999999",
                "Ola",
                "text",
                "wamid.bot",
                20,
                "wamid.cliente",
                "123456",
                "5571000000000",
                "bot",
                "sent",
            )

        def fake_update_cliente(*_args, **_kwargs):
            raise AssertionError("nao deve atualizar cliente quando resposta bot ja existe")

        def fake_update_bot(*_args, **_kwargs):
            raise AssertionError("last_from ja esta semanticamente como bot")

        cursor = object()

        with patch.object(
            valida_historico,
            "inserir_historico_mensagem_cliente",
            fake_inserir,
        ), patch.object(
            valida_historico,
            "buscar_resposta_bot_por_mensagem_cliente",
            fake_buscar_resposta,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_mensagem_cliente",
            fake_update_cliente,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_update_bot,
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(last_from="bot", etapa=2),
                cursor,
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 2)
        self.assertEqual(contexto["last_message_from"], "bot")
        self.assertTrue(contexto["resposta_bot_para_mensagem_atual"])
        self.assertEqual([chamada[0] for chamada in chamadas], ["insert_cliente"])

    def test_retry_repara_last_from_cliente_quando_resposta_bot_ja_existe(self):
        chamadas = []

        def fake_inserir(mensagem, id_conversa, id_etapa, cursor):
            return 100, "2026-01-01T00:00:00", 1, False

        def fake_buscar_resposta(**_kwargs):
            return (
                200,
                10,
                2,
                "2026-01-01T00:01:00",
                "5571999999999",
                "Ola",
                "text",
                "wamid.bot",
                20,
                "wamid.cliente",
                "123456",
                "5571000000000",
                "bot",
                "sent",
            )

        def fake_update_bot(id_conversa, cursor):
            chamadas.append(("update_bot_sem_avancar", id_conversa, cursor))
            return 1

        cursor = object()

        with patch.object(
            valida_historico,
            "inserir_historico_mensagem_cliente",
            fake_inserir,
        ), patch.object(
            valida_historico,
            "buscar_resposta_bot_por_mensagem_cliente",
            fake_buscar_resposta,
        ), patch.object(
            valida_historico,
            "atualizar_conversa_resposta_bot_sem_avancar",
            fake_update_bot,
        ):
            contexto = valida_historico.valida_historico(
                mensagem_base(retry=2),
                contexto_banco_base(last_from="cliente", etapa=2),
                cursor,
            )

        self.assertEqual(contexto["id_etapa_cliente"], 1)
        self.assertEqual(contexto["id_etapa_resposta"], 2)
        self.assertEqual(contexto["last_message_from"], "bot")
        self.assertEqual(
            chamadas,
            [("update_bot_sem_avancar", 10, cursor)],
        )


if __name__ == "__main__":
    unittest.main()
```

## Passo 13 - Validacao

Rodar:

```powershell
C:\Chatbot\venv\.venv\Scripts\python.exe -m compileall -q core callback workers main.py tests
C:\Chatbot\venv\.venv\Scripts\python.exe callback\manage.py check
C:\Chatbot\venv\.venv\Scripts\python.exe -m unittest discover -s tests -v
git diff --check
```

## O Que Esta Mudanca Resolve

Com esse desenho, `last_message_from` passa a ser semanticamente correto:

```text
cliente registrado no historico -> conversa.last_message_from = cliente
bot registrado no historico -> conversa.last_message_from = bot
```

E o sistema ainda consegue lidar com retry:

```text
worker cai depois de registrar cliente e last_from=cliente
mensagem volta para fila
proximo retry reutiliza a etapa persistida do cliente
bot responde a etapa correta

worker cai depois de persistir resposta do bot e antes de marcar fila como sent
mensagem volta para fila
retry encontra cliente e bot vinculados a mesma mensagem da fila
retry usa as etapas persistidas e nao envia novamente
conversa nao retrocede nem pula etapa
```

## Consequencias

Essa mudanca cria um estado intermediario persistido:

```text
last_message_from = cliente
```

Esse estado significa:

```text
cliente ja respondeu, mas o bot ainda nao fechou o turno
```

Isso e semanticamente correto, mas aumenta a responsabilidade do sistema em tratar bem:

- retry;
- queda apos historico do cliente;
- queda apos envio Meta;
- tratamento sem avancar etapa;
- webhook com fila aberta;
- idempotencia por historico.

## Limite conhecido mantido pelo experimento

O experimento nao elimina a janela em que a Meta confirma o envio, mas o banco
ou o worker falha antes de persistir o historico do bot. Sem um identificador
idempotente aceito pela Meta ou uma arquitetura de outbox, o retry ainda pode
enviar uma resposta duplicada nesse caso raro.

Esse risco permanece explicitamente aceito. O experimento garante que os
estados que ja chegaram ao banco sejam recuperados sem pular ou retroceder
etapa.

## Recomendacao de aplicacao

Aplicar somente com banco e servidores de teste ativos, executar toda a suite e
simular manualmente:

- conversa nova;
- conversa em andamento;
- midia nao suportada;
- retry antes da resposta do bot;
- retry depois da resposta do bot persistida;
- resposta do bot persistida com fila ainda `processing`;
- falha da Meta;
- falha do banco depois do envio da Meta.
