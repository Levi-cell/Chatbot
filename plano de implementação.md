# Plano de implementacao: bloqueio Meta por flood no webhook

Este plano ainda nao aplica a implementacao no codigo. Ele descreve a implementacao simples, em ordem, com o codigo completo de cada arquivo que deve ser criado ou modificado.

## Decisao da tabela

A tabela de bloqueio fica assim:

```text
id_bloqueio
id_cliente NULL
wa_id_cliente NOT NULL
id_unidade NOT NULL
phone_id_unidade NOT NULL
```

Regra clara:

- `wa_id_cliente + id_unidade` e o bloqueio unico. O mesmo cliente pode ser bloqueado em varias unidades, mas apenas uma vez por unidade.
- `id_unidade` e obrigatorio, porque unidade e controlada pelo Django admin e o bloqueio da Meta e por unidade/phone number.
- `phone_id_unidade` fica salvo junto para chamada direta da PyWa/Meta no bloqueio e desbloqueio.
- `id_cliente` e opcional. Ao bloquear um floodador, o sistema procura `wa_id_cliente` em `chatbot.cliente.waid_telefone`.
- Se encontrar cliente, salva o `id_cliente` para rastrear mensagens/conversas depois.
- Se nao encontrar cliente, salva `id_cliente = NULL`, indicando que o flood aconteceu antes do cadastro daquele telefone como cliente.
- O worker nao consulta essa tabela e nao precisa saber que ela existe.

Comportamento final:

- Redis conta mensagens por `wa_id_cliente + phone_id_unidade` antes de inserir na fila.
- As regras de flood ficam em `callback/webhook/services/flood_guard.py`, na constante `REGRAS_FLOOD`.
- O bloqueio acontece se qualquer uma das regras bater:
  - `60` mensagens em `1` segundo.
  - `10` mensagens em `5` segundos.
  - `30` mensagens em `60` segundos.
- A mensagem que disparou qualquer limite nao entra na fila.
- Em mensagem normal, o anti-flood nao consulta banco nem chama Meta. O custo extra fica restrito a uma chamada agrupada ao Redis.
- Banco entra apenas se Redis falhar ou quando o flood ja foi detectado e precisa registrar o bloqueio.
- Meta/PyWa entra apenas quando o cliente precisa ser bloqueado ou quando o admin exclui um bloqueio para desbloquear.
- Se Redis falhar, o banco tenta fazer a contagem em uma tabela tecnica de eventos do webhook, tambem antes da fila.
- Se Redis e banco falharem, o webhook segue o fluxo normal; se o banco estiver fora, a fila tambem nao sera preenchida.
- Ao identificar flood, o sistema chama PyWa para bloquear o `wa_id_cliente` naquele `phone_id_unidade`.
- O bloqueio e permanente na Meta e registrado na tabela `cliente_bloqueado_meta`.
- Se o mesmo `wa_id_cliente` floodar outra unidade, sera criado outro registro com o mesmo `wa_id_cliente` e outro `id_unidade`.
- O Django admin nao adiciona nem edita bloqueios manualmente. Ele apenas permite excluir um registro; ao excluir, chama PyWa para desbloquear aquele cliente naquela unidade.

## Passo 1: criar `core/database/floodscript.py`

```python
import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.flood_setup")


def criar_tabelas_bloqueio_flood():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SET TIME ZONE 'America/Sao_Paulo';

            CREATE UNIQUE INDEX IF NOT EXISTS uq_unidade_id_phone_number_id
            ON chatbot.unidade (id_unidade, phone_number_id);

            CREATE TABLE IF NOT EXISTS chatbot.cliente_bloqueado_meta (
                id_bloqueio SERIAL PRIMARY KEY,
                id_cliente INT NULL,
                wa_id_cliente VARCHAR(50) NOT NULL,
                id_unidade INT NOT NULL,
                phone_id_unidade VARCHAR(100) NOT NULL,

                CONSTRAINT fk_cliente_bloqueado_meta_cliente
                    FOREIGN KEY (id_cliente)
                    REFERENCES chatbot.cliente(id_cliente)
                    ON DELETE SET NULL,

                CONSTRAINT fk_cliente_bloqueado_meta_unidade_phone
                    FOREIGN KEY (id_unidade, phone_id_unidade)
                    REFERENCES chatbot.unidade(id_unidade, phone_number_id)
                    ON UPDATE CASCADE
                    ON DELETE CASCADE,

                CONSTRAINT uq_cliente_bloqueado_meta_wa_unidade
                    UNIQUE (wa_id_cliente, id_unidade)
            );

            CREATE INDEX IF NOT EXISTS idx_cliente_bloqueado_meta_id_cliente
            ON chatbot.cliente_bloqueado_meta (id_cliente)
            WHERE id_cliente IS NOT NULL;

            CREATE INDEX IF NOT EXISTS idx_cliente_bloqueado_meta_wa_id
            ON chatbot.cliente_bloqueado_meta (wa_id_cliente);

            CREATE INDEX IF NOT EXISTS idx_cliente_bloqueado_meta_id_unidade
            ON chatbot.cliente_bloqueado_meta (id_unidade);

            CREATE INDEX IF NOT EXISTS idx_cliente_bloqueado_meta_phone_id
            ON chatbot.cliente_bloqueado_meta (phone_id_unidade);

            CREATE TABLE IF NOT EXISTS chatbot.webhook_flood_evento (
                id_evento BIGSERIAL PRIMARY KEY,
                wa_id_cliente VARCHAR(50) NOT NULL,
                phone_id_unidade VARCHAR(100) NOT NULL,
                id_hash_msg VARCHAR(255) NOT NULL UNIQUE,
                received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_webhook_flood_evento_janela
            ON chatbot.webhook_flood_evento (
                wa_id_cliente,
                phone_id_unidade,
                received_at DESC
            );

            CREATE INDEX IF NOT EXISTS idx_webhook_flood_evento_limpeza
            ON chatbot.webhook_flood_evento (received_at);
        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_tabelas_bloqueio_flood")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=criar_tabelas_bloqueio_flood erro=%s", erro)

    finally:
        if conn:
            conn.close()
```

## Passo 2: modificar `core/database/setup_database.py`

```python
import logging

from core.database.bank_script import (
    criar_tabelas,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    definir_timezone_role,
    alterar_banco,
    configurar_timeouts_avancados,
)
from core.database.floodscript import criar_tabelas_bloqueio_flood
from core.database.cache_control_script import criar_cache_controle
from core.database.connection_test import connection_teste_psql
from core.database.povoar_etapas import insere_etapa_once
from core.cache.cache_conversas_bloqueadas import limpar_cache_conversas_bloqueadas_dev
from core.cache.cache_unidade import recarregar_cache_unidades


logger = logging.getLogger("db.setup")


def setup_database_aws():
    logger.info("banco_setup_iniciado | acao=configurar_banco")
    connection_teste_psql()
    definir_timezone_role()
    criar_tabelas()
    criar_cache_controle()
    alterar_banco()
    criar_tabelas_bloqueio_flood()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()
    configurar_timeouts_avancados()
    insere_etapa_once()
    recarregar_cache_unidades()
    # Linha exclusiva para DEV: limpa bloqueios antigos quando o banco for recriado.
    limpar_cache_conversas_bloqueadas_dev()

    logger.info("banco_setup_finalizado | acao=configurar_banco")


setup_database_aws()
```

## Passo 3: modificar `core/integrations/whatsapp/pywa_tools.py`

```python
import logging

from pywa import WhatsApp
from pywa.types.templates import TemplateLanguage

from core.logging_config import short_value


logger = logging.getLogger("whatsapp.pywa")

# URL dev webhook: https://gladys-tetrarchic-dovie.ngrok-free.dev/webhook/
TOKEN = "EAATYGW2lhwgBQ4NNpLFVOzkhBCfH7SeWuus3RkF47cq9ldlK7QnU9UHhYZAH9xfWlOnf6p3sbbZAZC179mGXxiS6ZBLRt0EU5bWPrkjLOsjP1mAWVrPR8xadDOnEOWDuyhD0SFhojrOpqcKoo68NzqNdtJMGNqdoKEAZCGP1xdD1EMVn6J2CY86XZCWe30HQZDZD"
PHONE_NUMBER_ID = "954435134428733"


wa = WhatsApp(
    token=TOKEN,
    phone_id=PHONE_NUMBER_ID,
)


def enviar_mensagem_texto(to, text, client=None):
    cliente = client or wa

    sent_message = cliente.send_message(
        to=to,
        text=text,
    )

    id_hash_msg = _extrair_id_mensagem_enviada(sent_message)

    logger.info(
        "whatsapp_mensagem_enviada | acao=enviar tipo=text to=%s id_hash_msg=%s",
        short_value(to),
        id_hash_msg,
    )

    return id_hash_msg


def enviar_template(to, name, language="en_US", client=None):
    cliente = client or wa

    sent_message = cliente.send_template(
        to=to,
        name=name,
        language=TemplateLanguage(language),
    )

    id_hash_msg = _extrair_id_mensagem_enviada(sent_message)

    logger.info(
        "whatsapp_template_enviado | acao=enviar_template template=%s language=%s to=%s id_hash_msg=%s",
        name,
        language,
        short_value(to),
        id_hash_msg,
    )

    return id_hash_msg


def bloquear_usuario_meta(wa_id_cliente, phone_id_unidade, client=None):
    cliente = client or wa

    resultado = cliente.block_users(
        users=[str(wa_id_cliente)],
        phone_id=str(phone_id_unidade),
    )

    erros = getattr(resultado, "errors", None)
    if erros:
        raise RuntimeError(f"PyWa retornou erro ao bloquear usuario: {erros}")

    logger.warning(
        "whatsapp_usuario_bloqueado | acao=bloquear wa_id_cliente=%s phone_id_unidade=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
    )

    return resultado


def desbloquear_usuario_meta(wa_id_cliente, phone_id_unidade, client=None):
    cliente = client or wa

    resultado = cliente.unblock_users(
        users=[str(wa_id_cliente)],
        phone_id=str(phone_id_unidade),
    )

    erros = getattr(resultado, "errors", None)
    if erros:
        raise RuntimeError(f"PyWa retornou erro ao desbloquear usuario: {erros}")

    logger.warning(
        "whatsapp_usuario_desbloqueado | acao=desbloquear wa_id_cliente=%s phone_id_unidade=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
    )

    return resultado


def _extrair_id_mensagem_enviada(sent_message):
    id_hash_msg = getattr(sent_message, "id", None)

    if not id_hash_msg:
        raise ValueError("PyWa nao retornou id da mensagem enviada")

    return id_hash_msg
```

## Passo 4: criar `core/cache/cache_bloqueio_meta.py`

```python
import hashlib
import logging
import time

from core.database.redis_client import get_redis_safe
from core.logging_config import short_value


logger = logging.getLogger("cache.bloqueio_meta")

RATE_PREFIX = "webhook_flood_rate"
BLOQUEIO_PREFIX = "cliente_bloqueado_meta"


def avaliar_flood_redis(
    wa_id_cliente,
    phone_id_unidade,
    regras,
):
    if not wa_id_cliente or not phone_id_unidade:
        return {
            "redis_ok": True,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "dados_invalidos",
            "regra": None,
        }

    try:
        r = get_redis_safe(retries=1, delay=0)
        agora = time.time()
        bloqueio_key = _bloqueio_key(wa_id_cliente, phone_id_unidade)

        pipe = r.pipeline()

        pipe.exists(bloqueio_key)

        for regra in regras:
            janela_segundos = regra["janela_segundos"]
            janela = int(agora // janela_segundos)
            key = _rate_key(wa_id_cliente, phone_id_unidade, janela_segundos, janela)
            pipe.incr(key)
            pipe.expire(key, janela_segundos + 10)

        resultados = pipe.execute()

        if bool(resultados[0]):
            return {
                "redis_ok": True,
                "bloqueado": True,
                "flood": False,
                "total": 0,
                "motivo": "cliente_ja_bloqueado_cache",
                "regra": None,
            }

        maior_total = 0
        indice = 1

        for regra in regras:
            total = int(resultados[indice])
            indice += 2
            maior_total = max(maior_total, total)

            if total >= regra["limite"]:
                return {
                    "redis_ok": True,
                    "bloqueado": False,
                    "flood": True,
                    "total": total,
                    "limite": regra["limite"],
                    "janela_segundos": regra["janela_segundos"],
                    "motivo": "redis",
                    "regra": regra["nome"],
                }

        return {
            "redis_ok": True,
            "bloqueado": False,
            "flood": False,
            "total": maior_total,
            "motivo": "redis",
            "regra": None,
        }

    except Exception as exc:
        logger.warning(
            "rate_limit_redis_falhou | acao=fallback_banco wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            "redis_ok": False,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "redis_indisponivel",
            "regra": None,
        }


def registrar_cliente_bloqueado_meta_cache(wa_id_cliente, phone_id_unidade):
    key = _bloqueio_key(wa_id_cliente, phone_id_unidade)

    if key is None:
        return False

    try:
        r = get_redis_safe(retries=1, delay=0)
        r.set(key, "1")
        return True

    except Exception as exc:
        logger.warning(
            "bloqueio_meta_cache_registrar_falhou | acao=ignorar wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return False


def remover_cliente_bloqueado_meta_cache(wa_id_cliente, phone_id_unidade):
    key = _bloqueio_key(wa_id_cliente, phone_id_unidade)

    if key is None:
        return False

    try:
        r = get_redis_safe(retries=1, delay=0)
        return bool(r.delete(key))

    except Exception as exc:
        logger.warning(
            "bloqueio_meta_cache_remover_falhou | acao=ignorar wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return False


def _rate_key(wa_id_cliente, phone_id_unidade, janela_segundos, janela):
    digest = _digest(wa_id_cliente, phone_id_unidade)
    return f"{RATE_PREFIX}:{janela_segundos}:{janela}:{digest}"


def _bloqueio_key(wa_id_cliente, phone_id_unidade):
    digest = _digest(wa_id_cliente, phone_id_unidade)

    if digest is None:
        return None

    return f"{BLOQUEIO_PREFIX}:{digest}"


def _digest(wa_id_cliente, phone_id_unidade):
    wa_id_cliente = _normalizar(wa_id_cliente)
    phone_id_unidade = _normalizar(phone_id_unidade)

    if not wa_id_cliente or not phone_id_unidade:
        return None

    raw = f"{phone_id_unidade}:{wa_id_cliente}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalizar(valor):
    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None
```

## Passo 5: criar `core/repositories/bloqueio_meta.py`

```python
import logging

from core.logging_config import short_value


logger = logging.getLogger("db.bloqueio_meta")


def registrar_evento_flood_banco(
    wa_id_cliente,
    phone_id_unidade,
    id_hash_msg,
    cursor,
):
    cursor.execute("""
        INSERT INTO chatbot.webhook_flood_evento (
            wa_id_cliente,
            phone_id_unidade,
            id_hash_msg,
            received_at
        )
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (id_hash_msg) DO NOTHING;
    """, (wa_id_cliente, phone_id_unidade, id_hash_msg))
    logger.debug(
        "flood_evento_insert | acao=registrar wa_id_cliente=%s phone_id_unidade=%s id_hash_msg=%s linhas=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        short_value(id_hash_msg),
        cursor.rowcount,
    )


def contar_eventos_flood_banco(
    wa_id_cliente,
    phone_id_unidade,
    cursor,
    janela_segundos=60,
):
    cursor.execute("""
        SELECT COUNT(*)
        FROM chatbot.webhook_flood_evento
        WHERE wa_id_cliente = %s
          AND phone_id_unidade = %s
          AND received_at >= NOW() - (%s * INTERVAL '1 second');
    """, (wa_id_cliente, phone_id_unidade, janela_segundos))

    resultado = cursor.fetchone()
    total = int(resultado[0]) if resultado else 0
    logger.debug(
        "flood_evento_count | acao=contar wa_id_cliente=%s phone_id_unidade=%s janela=%s total=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        janela_segundos,
        total,
    )
    return total


def limpar_eventos_flood_antigos(cursor, horas=2):
    cursor.execute("""
        DELETE FROM chatbot.webhook_flood_evento
        WHERE received_at < NOW() - (%s * INTERVAL '1 hour');
    """, (horas,))

    logger.debug(
        "flood_evento_limpeza | acao=limpar_antigos horas=%s linhas=%s",
        horas,
        cursor.rowcount,
    )
    return cursor.rowcount


def buscar_id_cliente_por_wa_id(wa_id_cliente, cursor):
    cursor.execute("""
        SELECT id_cliente
        FROM chatbot.cliente
        WHERE waid_telefone = %s
        LIMIT 1;
    """, (wa_id_cliente,))

    resultado = cursor.fetchone()
    id_cliente = resultado[0] if resultado else None
    logger.debug(
        "cliente_consulta | acao=buscar_por_wa_id wa_id_cliente=%s encontrado=%s",
        short_value(wa_id_cliente),
        bool(id_cliente),
    )
    return id_cliente


def buscar_unidade_bloqueio_por_phone_id(phone_id_unidade, cursor):
    cursor.execute("""
        SELECT id_unidade, phone_number_id
        FROM chatbot.unidade
        WHERE phone_number_id = %s
          AND status_ativo = TRUE
        LIMIT 1;
    """, (phone_id_unidade,))

    resultado = cursor.fetchone()
    logger.debug(
        "unidade_consulta | acao=buscar_para_bloqueio phone_id_unidade=%s encontrada=%s",
        short_value(phone_id_unidade),
        bool(resultado),
    )
    return resultado


def registrar_cliente_bloqueado_meta_banco(
    id_cliente,
    wa_id_cliente,
    id_unidade,
    phone_id_unidade,
    cursor,
):
    cursor.execute("""
        INSERT INTO chatbot.cliente_bloqueado_meta (
            id_cliente,
            wa_id_cliente,
            id_unidade,
            phone_id_unidade
        )
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (wa_id_cliente, id_unidade) DO UPDATE
        SET
            id_cliente = COALESCE(EXCLUDED.id_cliente, chatbot.cliente_bloqueado_meta.id_cliente),
            phone_id_unidade = EXCLUDED.phone_id_unidade
        RETURNING id_bloqueio;
    """, (
        id_cliente,
        wa_id_cliente,
        id_unidade,
        phone_id_unidade,
    ))

    resultado = cursor.fetchone()
    id_bloqueio = resultado[0] if resultado else None
    logger.debug(
        "bloqueio_meta_upsert | acao=registrar_bloqueio wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s id_bloqueio=%s linhas=%s",
        short_value(wa_id_cliente),
        id_cliente,
        id_unidade,
        short_value(phone_id_unidade),
        id_bloqueio,
        cursor.rowcount,
    )
    return id_bloqueio


def cliente_bloqueado_meta_existe_banco(
    wa_id_cliente,
    phone_id_unidade,
    cursor,
):
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM chatbot.cliente_bloqueado_meta
            WHERE wa_id_cliente = %s
              AND phone_id_unidade = %s
            LIMIT 1
        );
    """, (wa_id_cliente, phone_id_unidade))

    resultado = cursor.fetchone()
    existe = bool(resultado[0]) if resultado else False
    logger.debug(
        "bloqueio_meta_consulta | acao=existe wa_id_cliente=%s phone_id_unidade=%s existe=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        existe,
    )
    return existe
```

## Passo 6: criar `callback/webhook/services/flood_guard.py`

```python
import logging

from django.http import JsonResponse

from core.cache.cache_bloqueio_meta import (
    avaliar_flood_redis,
    registrar_cliente_bloqueado_meta_cache,
)
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.pywa_tools import bloquear_usuario_meta
from core.logging_config import short_value
from core.repositories.bloqueio_meta import (
    buscar_id_cliente_por_wa_id,
    buscar_unidade_bloqueio_por_phone_id,
    cliente_bloqueado_meta_existe_banco,
    contar_eventos_flood_banco,
    limpar_eventos_flood_antigos,
    registrar_cliente_bloqueado_meta_banco,
    registrar_evento_flood_banco,
)


logger = logging.getLogger("webhook.flood_guard")

REGRAS_FLOOD = (
    {
        "nome": "rajada_extrema",
        "limite": 60,
        "janela_segundos": 1,
    },
    {
        "nome": "rajada_curta",
        "limite": 10,
        "janela_segundos": 5,
    },
    {
        "nome": "spam_minuto",
        "limite": 30,
        "janela_segundos": 60,
    },
)


def responder_se_flood(data):
    phone_id_unidade = _extrair_phone_number_id(data)
    wa_id_cliente = _extrair_cliente_telefone(data)
    id_hash_msg = _extrair_id_hash_msg(data)

    flood = bloquear_cliente_se_flood(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
    )

    if not flood["bloqueado"]:
        return None

    logger.warning(
        "mensagem_ignorada | motivo=%s regra=%s acao=bloqueio_meta_nao_enfileirar cliente=%s phone_number_id=%s total=%s",
        flood["motivo"],
        flood.get("regra"),
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        flood["total"],
    )

    return JsonResponse({
        "status": "ignored",
        "reason": flood["motivo"],
    })


def bloquear_cliente_se_flood(wa_id_cliente, phone_id_unidade, id_hash_msg):
    if not wa_id_cliente or not phone_id_unidade or not id_hash_msg:
        return {
            "bloqueado": False,
            "motivo": "dados_invalidos",
            "total": 0,
            "regra": None,
        }

    rate_redis = avaliar_flood_redis(
        wa_id_cliente,
        phone_id_unidade,
        regras=REGRAS_FLOOD,
    )

    if rate_redis["redis_ok"]:
        if rate_redis["bloqueado"]:
            return {
                "bloqueado": True,
                "motivo": rate_redis["motivo"],
                "total": rate_redis["total"],
                "regra": rate_redis["regra"],
            }

        if rate_redis["flood"]:
            return _bloquear_e_registrar(
                wa_id_cliente,
                phone_id_unidade,
                origem="redis",
                total=rate_redis["total"],
                regra=rate_redis["regra"],
            )

        return {
            "bloqueado": False,
            "motivo": "abaixo_limite_redis",
            "total": rate_redis["total"],
            "regra": None,
        }

    rate_banco = _avaliar_flood_banco(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
    )

    if rate_banco["bloqueado"]:
        return {
            "bloqueado": True,
            "motivo": rate_banco["motivo"],
            "total": rate_banco["total"],
            "regra": rate_banco["regra"],
        }

    if rate_banco["flood"]:
        return _bloquear_e_registrar(
            wa_id_cliente,
            phone_id_unidade,
            origem="banco",
            total=rate_banco["total"],
            regra=rate_banco["regra"],
        )

    return {
        "bloqueado": False,
        "motivo": rate_banco["motivo"],
        "total": rate_banco["total"],
        "regra": None,
    }


def _avaliar_flood_banco(wa_id_cliente, phone_id_unidade, id_hash_msg):
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        if cliente_bloqueado_meta_existe_banco(
            wa_id_cliente,
            phone_id_unidade,
            cursor,
        ):
            return {
                "banco_ok": True,
                "bloqueado": True,
                "flood": False,
                "total": 0,
                "motivo": "cliente_ja_bloqueado_banco",
                "regra": None,
            }

        registrar_evento_flood_banco(
            wa_id_cliente,
            phone_id_unidade,
            id_hash_msg,
            cursor,
        )
        maior_total = 0
        total = 0
        regra_estourada = None

        for regra in REGRAS_FLOOD:
            total = contar_eventos_flood_banco(
                wa_id_cliente,
                phone_id_unidade,
                cursor,
                janela_segundos=regra["janela_segundos"],
            )

            maior_total = max(maior_total, total)

            if total >= regra["limite"]:
                regra_estourada = regra
                break

        limpar_eventos_flood_antigos(cursor)

        conn.commit()

        return {
            "banco_ok": True,
            "bloqueado": False,
            "flood": regra_estourada is not None,
            "total": total if regra_estourada else maior_total,
            "motivo": "banco",
            "regra": regra_estourada["nome"] if regra_estourada else None,
        }

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.warning(
            "rate_limit_banco_falhou | acao=seguir_fluxo wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            "banco_ok": False,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "banco_indisponivel",
            "regra": None,
        }

    finally:
        if conn:
            conn.close()


def _bloquear_e_registrar(wa_id_cliente, phone_id_unidade, origem, total, regra):
    registro = _registrar_bloqueio_banco(wa_id_cliente, phone_id_unidade)
    meta_ok = False

    try:
        bloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
        meta_ok = True

    except Exception as exc:
        logger.exception(
            "bloqueio_meta_falhou | acao=continuar_bloqueio_local origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s erro=%s",
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
            exc,
        )

    if registro["id_bloqueio"] or meta_ok:
        registrar_cliente_bloqueado_meta_cache(
            wa_id_cliente,
            phone_id_unidade,
        )

    logger.warning(
        "flood_bloqueado | acao=registrar_resultado origem=%s regra=%s wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s total=%s id_bloqueio=%s meta_ok=%s",
        origem,
        regra,
        short_value(wa_id_cliente),
        registro["id_cliente"],
        registro["id_unidade"],
        short_value(phone_id_unidade),
        total,
        registro["id_bloqueio"],
        meta_ok,
    )

    return {
        "bloqueado": True,
        "motivo": f"flood_{origem}",
        "total": total,
        "regra": regra,
        "id_bloqueio": registro["id_bloqueio"],
        "id_cliente": registro["id_cliente"],
        "id_unidade": registro["id_unidade"],
        "meta_ok": meta_ok,
    }


def _registrar_bloqueio_banco(wa_id_cliente, phone_id_unidade):
    conn = None
    registro_vazio = {
        "id_bloqueio": None,
        "id_cliente": None,
        "id_unidade": None,
    }

    try:
        conn = get_conn()
        cursor = conn.cursor()

        id_cliente = buscar_id_cliente_por_wa_id(wa_id_cliente, cursor)
        unidade = buscar_unidade_bloqueio_por_phone_id(
            phone_id_unidade,
            cursor,
        )

        if not unidade:
            raise ValueError(f"Unidade ativa nao encontrada: {phone_id_unidade}")

        id_unidade, phone_id_cadastrado = unidade

        id_bloqueio = registrar_cliente_bloqueado_meta_banco(
            id_cliente,
            wa_id_cliente,
            id_unidade,
            phone_id_cadastrado,
            cursor,
        )

        conn.commit()

        return {
            "id_bloqueio": id_bloqueio,
            "id_cliente": id_cliente,
            "id_unidade": id_unidade,
        }

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.exception(
            "bloqueio_meta_registro_banco_falhou | acao=bloquear_meta_mesmo_assim wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return registro_vazio

    finally:
        if conn:
            conn.close()


def _extrair_phone_number_id(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    metadata = value.get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    contacts = value.get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None


def _extrair_id_hash_msg(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    messages = value.get("messages", [{}])
    return messages[0].get("id") if messages else None
```

## Passo 7: modificar `callback/webhook/models.py`

```python
from django.db import models


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=200, blank=True, null=True)
    waid_telefone = models.CharField(unique=True, max_length=50)
    email = models.CharField(unique=True, max_length=200, blank=True, null=True)

    def __str__(self):
        return self.nome or self.waid_telefone

    class Meta:
        managed = False
        db_table = 'cliente'


class Conversa(models.Model):
    id_conversa = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='id_cliente')
    id_unidade = models.ForeignKey('Unidade', models.DO_NOTHING, db_column='id_unidade')
    id_etapa_atual = models.ForeignKey('Etapa', models.DO_NOTHING, db_column='id_etapa_atual', blank=True, null=True)
    status_ativa = models.BooleanField(default=True)
    status_dependente = models.BooleanField(blank=True, null=True, default=False)
    last_interaction_at = models.DateTimeField(blank=True, null=True)
    last_message_from = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[("cliente", "cliente"), ("bot", "bot")],
    )
    followup_stage = models.IntegerField(blank=True, null=True, default=0)
    followup_last_sent_at = models.DateTimeField(blank=True, null=True)
    lead_no_funil = models.BooleanField(blank=True, null=True, default=False)
    processing = models.BooleanField(blank=True, null=True, default=False)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    lock_version = models.IntegerField(blank=True, null=True, default=0)
    iniciou_em = models.DateTimeField()
    finalizou_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'conversa'


class Etapa(models.Model):
    id_etapa = models.AutoField(primary_key=True)
    nome_etapa = models.CharField(unique=True, max_length=100)

    class Meta:
        managed = False
        db_table = 'etapa'


class FilaMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.SET_NULL,
        db_column='id_conversa',
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=20,
        default="pending",
        choices=[
            ("pending", "pending"),
            ("processing", "processing"),
            ("sent", "sent"),
            ("failed", "failed"),
        ],
    )
    retry_count = models.IntegerField(blank=True, null=True, default=0)
    next_attempt_at = models.DateTimeField(blank=True, null=True)
    processing_started_at = models.DateTimeField(blank=True, null=True)
    received_data_hora = models.DateTimeField()
    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(unique=True, max_length=255)
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
    last_error = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'fila_mensagens'


class HistoricoMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)

    id_conversa = models.ForeignKey(
        Conversa,
        models.DO_NOTHING,
        db_column='id_conversa',
    )

    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        blank=True,
        null=True,
    )

    received_data_hora = models.DateTimeField()

    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(max_length=255)
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
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

    class Meta:
        managed = False
        db_table = 'historico_mensagens'
        unique_together = (('id_mensagem', 'received_data_hora'),)


class Unidade(models.Model):
    id_unidade = models.AutoField(primary_key=True)
    nome = models.CharField(unique=True, max_length=300)
    cnpj = models.CharField(unique=True, max_length=50)
    email_responsavel = models.CharField(unique=True, max_length=255)
    telefone = models.CharField(unique=True, max_length=20)
    phone_number_id = models.CharField(unique=True, max_length=100)
    link_agendamento = models.CharField(unique=True, max_length=400)
    status_ativo = models.BooleanField(blank=True, null=True, default=True)

    def __str__(self):
        return self.nome

    class Meta:
        managed = False
        db_table = 'unidade'


class ClienteBloqueadoMeta(models.Model):
    id_bloqueio = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.SET_NULL,
        db_column='id_cliente',
        blank=True,
        null=True,
        related_name='bloqueios_meta',
    )
    wa_id_cliente = models.CharField(max_length=50)
    id_unidade = models.ForeignKey(
        Unidade,
        models.DO_NOTHING,
        db_column='id_unidade',
        related_name='bloqueios_meta',
    )
    phone_id_unidade = models.CharField(max_length=100)

    def __str__(self):
        return f"{self.wa_id_cliente} / {self.phone_id_unidade}"

    class Meta:
        managed = False
        db_table = 'cliente_bloqueado_meta'
        unique_together = (('wa_id_cliente', 'id_unidade'),)
```

## Passo 8: modificar `callback/webhook/admin.py`

```python
from django.contrib import admin, messages
from django.db import connection, transaction
from django.utils.html import format_html
from django.urls import reverse
import logging

from core.cache.cache_bloqueio_meta import remover_cliente_bloqueado_meta_cache
from core.cache.cache_unidade import recarregar_cache_unidades
from core.integrations.whatsapp.ativando_numero import registrar_numero_whatsapp
from core.integrations.whatsapp.pywa_tools import desbloquear_usuario_meta
from core.logging_config import short_value
from core.repositories.cache_control import incrementar_versao_cache_unidades

from .models import (
    Cliente,
    ClienteBloqueadoMeta,
    Conversa,
    Etapa,
    FilaMensagens,
    HistoricoMensagens,
    Unidade,
)

logger = logging.getLogger(__name__)


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):

    list_display = (
        "id_unidade",
        "nome",
        "cnpj",
        "telefone",
        "email_responsavel",
        "link_agendamento_clickable",
        "status_ativo",
    )

    search_fields = (
        "nome",
        "cnpj",
        "telefone",
        "email_responsavel",
        "link_agendamento",
    )

    list_filter = ("status_ativo",)
    ordering = ("nome",)

    list_per_page = 50
    empty_value_display = "-"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._registrar_alteracao_cache_unidades()

        if not change:
            try:
                status, resposta = registrar_numero_whatsapp(obj.phone_number_id)

                if status != 200:
                    logger.error(
                        "whatsapp_numero_registrar_falhou | acao=registrar_numero phone_number_id=%s status=%s resposta=%s",
                        short_value(obj.phone_number_id),
                        status,
                        resposta,
                    )
                    self.message_user(
                        request,
                        f"Erro ao registrar numero no WhatsApp: {resposta}",
                        level=messages.ERROR,
                    )
                else:
                    logger.info(
                        "whatsapp_numero_registrado | acao=registrar_numero phone_number_id=%s status=%s",
                        short_value(obj.phone_number_id),
                        status,
                    )
                    self.message_user(
                        request,
                        "Numero registrado com sucesso no WhatsApp!",
                        level=messages.SUCCESS,
                    )

            except Exception as e:
                logger.exception(
                    "whatsapp_numero_registrar_erro | acao=registrar_numero phone_number_id=%s",
                    short_value(obj.phone_number_id),
                )
                self.message_user(
                    request,
                    f"Erro inesperado ao registrar numero: {str(e)}",
                    level=messages.ERROR,
                )

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self._registrar_alteracao_cache_unidades()

    def delete_queryset(self, request, queryset):
        super().delete_queryset(request, queryset)
        self._registrar_alteracao_cache_unidades()

    def _registrar_alteracao_cache_unidades(self):
        with connection.cursor() as cursor:
            versao = incrementar_versao_cache_unidades(cursor)

        logger.info("cache_unidades_versao_incrementada | acao=incrementar_versao versao=%s", versao)
        transaction.on_commit(recarregar_cache_unidades)

    def link_agendamento_clickable(self, obj):
        if obj.link_agendamento:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_agendamento,
            )
        return "-"

    link_agendamento_clickable.short_description = "Agendamento"


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):

    list_display = (
        "id_cliente",
        "nome",
        "waid_telefone",
        "email",
    )

    search_fields = (
        "nome",
        "waid_telefone",
        "email",
    )

    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(Etapa)
class EtapaAdmin(admin.ModelAdmin):

    list_display = (
        "id_etapa",
        "nome_etapa",
    )

    search_fields = ("nome_etapa",)
    ordering = ("nome_etapa",)

    list_per_page = 50
    empty_value_display = "-"


@admin.register(Conversa)
class ConversaAdmin(admin.ModelAdmin):

    list_display = (
        "id_conversa",
        "cliente_link",
        "id_unidade",
        "id_etapa_atual",
        "status_ativa",
        "last_message_from",
        "followup_stage",
        "lead_no_funil",
        "processing",
        "last_interaction_at",
        "iniciou_em",
    )

    search_fields = (
        "id_cliente__waid_telefone",
        "id_cliente__nome",
    )

    list_filter = (
        "status_ativa",
        "lead_no_funil",
        "last_message_from",
        "followup_stage",
        "processing",
        "id_unidade",
        "id_etapa_atual",
    )

    ordering = ("-iniciou_em",)

    date_hierarchy = "iniciou_em"
    list_per_page = 50

    readonly_fields = (
        "lock_version",
        "processing_started_at",
        "iniciou_em",
        "finalizou_em",
    )

    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_cliente",
            "id_unidade",
            "id_etapa_atual",
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except Exception:
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"


@admin.register(FilaMensagens)
class FilaMensagensAdmin(admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "id_conversa",
        "status_colorido",
        "tipo_mensagem",
        "cliente_telefone",
        "id_hash_msg",
        "received_data_hora",
        "retry_count",
        "next_attempt_at",
        "erro_resumido",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_conversa__id_conversa",
    )

    list_filter = (
        "status",
        "tipo_mensagem",
        "id_conversa",
    )

    ordering = ("-received_data_hora",)
    date_hierarchy = "received_data_hora"

    list_per_page = 50
    empty_value_display = "-"

    readonly_fields = ("last_error",)

    actions = ["reprocessar", "marcar_erro"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("id_conversa")

    @admin.action(description="Reprocessar mensagens selecionadas")
    def reprocessar(self, request, queryset):
        if queryset.count() > 100:
            self.message_user(
                request,
                "Limite de 100 mensagens por vez.",
                level=messages.ERROR,
            )
            return

        queryset.update(status="pending", retry_count=0, last_error=None)
        logger.info(
            "admin_fila_reprocessada | acao=reprocessar usuario=%s total=%s",
            request.user,
            queryset.count(),
        )

    @admin.action(description="Marcar como erro")
    def marcar_erro(self, request, queryset):
        queryset.update(status="failed")
        logger.warning(
            "admin_fila_marcada_erro | acao=marcar_failed usuario=%s total=%s",
            request.user,
            queryset.count(),
        )

    def status_colorido(self, obj):
        cores = {
            "sent": "green",
            "failed": "red",
            "pending": "#555",
            "processing": "orange",
        }
        cor = cores.get(obj.status, "#000")
        return format_html('<b style="color:{};">{}</b>', cor, obj.status)

    status_colorido.short_description = "Status"

    def erro_resumido(self, obj):
        if not obj.last_error:
            return "-"

        texto = obj.last_error[:60]

        return format_html(
            '<span title="{}">{}</span>',
            obj.last_error,
            texto + ("..." if len(obj.last_error) > 60 else ""),
        )

    erro_resumido.short_description = "Erro"


@admin.register(HistoricoMensagens)
class HistoricoMensagensAdmin(admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "origem",
        "tipo_mensagem",
        "status_envio",
        "id_conversa",
        "id_etapa",
        "cliente_telefone",
        "received_data_hora",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
    )

    list_filter = (
        "origem",
        "status_envio",
        "id_etapa",
        "tipo_mensagem",
    )

    ordering = ("-received_data_hora",)

    date_hierarchy = "received_data_hora"
    list_per_page = 50

    empty_value_display = "-"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_conversa",
            "id_etapa",
        )

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(ClienteBloqueadoMeta)
class ClienteBloqueadoMetaAdmin(admin.ModelAdmin):

    list_display = (
        "id_bloqueio",
        "cliente_link",
        "wa_id_cliente",
        "id_unidade",
        "phone_id_unidade",
    )

    search_fields = (
        "wa_id_cliente",
        "phone_id_unidade",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
        "id_unidade__nome",
    )

    list_filter = ("id_unidade",)
    ordering = ("wa_id_cliente", "id_unidade__nome")
    list_per_page = 50
    empty_value_display = "-"

    def has_add_permission(self, request):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_unidade",
        )

    def delete_model(self, request, obj):
        wa_id_cliente = obj.wa_id_cliente
        phone_id_unidade = obj.phone_id_unidade

        super().delete_model(request, obj)

        transaction.on_commit(
            lambda: self._desbloquear_meta(
                request,
                wa_id_cliente,
                phone_id_unidade,
            )
        )

    def delete_queryset(self, request, queryset):
        bloqueios = list(
            queryset.values_list(
                "wa_id_cliente",
                "phone_id_unidade",
            )
        )

        super().delete_queryset(request, queryset)

        transaction.on_commit(
            lambda: self._desbloquear_varios_meta(request, bloqueios)
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente],
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except Exception:
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"

    def _desbloquear_varios_meta(self, request, bloqueios):
        for wa_id_cliente, phone_id_unidade in bloqueios:
            self._desbloquear_meta(request, wa_id_cliente, phone_id_unidade)

    def _desbloquear_meta(self, request, wa_id_cliente, phone_id_unidade):
        try:
            desbloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
            remover_cliente_bloqueado_meta_cache(
                wa_id_cliente,
                phone_id_unidade,
            )

            logger.warning(
                "admin_cliente_desbloqueado_meta | acao=desbloquear_meta usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
                request.user,
                short_value(wa_id_cliente),
                short_value(phone_id_unidade),
            )

            self.message_user(
                request,
                f"Cliente {wa_id_cliente} desbloqueado na unidade {phone_id_unidade}.",
                level=messages.SUCCESS,
            )

        except Exception as exc:
            logger.exception(
                "admin_desbloqueio_meta_falhou | acao=desbloquear_meta usuario=%s wa_id_cliente=%s phone_id_unidade=%s erro=%s",
                request.user,
                short_value(wa_id_cliente),
                short_value(phone_id_unidade),
                exc,
            )
            self.message_user(
                request,
                f"Registro removido, mas falhou ao desbloquear na Meta: {exc}",
                level=messages.ERROR,
            )
```

## Passo 9: modificar `callback/webhook/views.py`

```python
import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core.cache.cache_conversas_bloqueadas import conversa_esta_bloqueada_cache
from core.cache.cache_unidade import unidade_esta_ativa
from core.logging_config import short_value
from .services.flood_guard import responder_se_flood
from .services.populating_fila_mensagens import povoando_fila


logger = logging.getLogger("webhook.request")

VERIFY_TOKEN = "123456"


@csrf_exempt
def callback(request):
    logger.info("request_recebido | metodo=%s path=%s", request.method, request.path)

    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("verificacao_meta_ok | mode=%s", mode)
            return HttpResponse(challenge)

        logger.warning("verificacao_meta_falhou | mode=%s", mode)
        return HttpResponse("Webhook ativo")

    if request.method != "POST":
        logger.warning("metodo_nao_permitido | metodo=%s", request.method)
        return JsonResponse({"status": "method_not_allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))

        phone_number_id = _extrair_phone_number_id(data)
        cliente_telefone = _extrair_cliente_telefone(data)

        if not unidade_esta_ativa(phone_number_id):
            logger.info(
                "mensagem_ignorada | motivo=unidade_inativa acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({"status": "ignored"})

        if resposta_flood := responder_se_flood(data):
            return resposta_flood

        if cliente_telefone and conversa_esta_bloqueada_cache(
            cliente_telefone,
            phone_number_id,
        ):
            logger.info(
                "mensagem_ignorada | motivo=conversa_bloqueada acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({
                "status": "ignored",
                "reason": "blocked_conversation",
            })

        if povoando_fila(data):
            logger.info(
                "request_processado | status=enfileirado acao=fila_insert cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
        else:
            logger.warning(
                "request_processado | status=nao_enfileirado acao=ignorar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )

    except Exception:
        logger.exception(
            "request_erro | acao=retornar_ok metodo=%s path=%s",
            request.method,
            request.path,
        )

    return JsonResponse({"status": "ok"})


def _extrair_phone_number_id(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    metadata = value.get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    contacts = value.get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None
```

## Ordem de execucao depois de aplicar o codigo

1. Subir o banco com `python -m core.database.setup_database` ou chamar `criar_tabelas_bloqueio_flood()` uma vez.
2. Rodar `python callback/manage.py check`.
3. Subir webhook e worker.
4. Simular 9 mensagens do mesmo `wa_id_cliente + phone_id_unidade` em 5 segundos: deve enfileirar.
5. Simular a 10a mensagem em 5 segundos: deve chamar PyWa, registrar em `cliente_bloqueado_meta` e nao enfileirar.
6. Liberar o registro pelo admin para testar de novo.
7. Simular 29 mensagens do mesmo `wa_id_cliente + phone_id_unidade` no mesmo minuto: deve enfileirar.
8. Simular a 30a mensagem no mesmo minuto: deve chamar PyWa, registrar em `cliente_bloqueado_meta` e nao enfileirar.
9. Conferir que a regra `60 mensagens em 1 segundo` existe como protecao extrema, mesmo que a regra de `10 mensagens em 5 segundos` normalmente bloqueie antes.
10. Conferir que `id_cliente` fica preenchido quando `wa_id_cliente` ja existir em `chatbot.cliente`.
11. Conferir que `id_cliente` fica `NULL` quando `wa_id_cliente` ainda nao existir em `chatbot.cliente`.
12. Excluir o registro pelo admin: deve chamar `desbloquear_usuario_meta(wa_id_cliente, phone_id_unidade)` e remover o cache local de bloqueio.
