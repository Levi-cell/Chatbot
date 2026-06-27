# Plano reduzido de otimização do Django Admin

## Decisão

Este plano preserva o comportamento administrativo atual:

```text
criação de unidade
-> registra na Meta
-> tenta salvar banco e cache

exclusão de unidade
-> desregistra na Meta
-> tenta excluir do banco e atualizar cache

edição de unidade
-> altera somente banco e cache
-> não chama Meta
```

Não haverá compensação automática.

Se a Meta funcionar e o banco ou Redis falhar depois, a operação realizada na
Meta permanecerá como está. O Admin mostrará explicitamente:

```text
Meta atualizada com sucesso.
Banco e cache local não foram confirmados.
É necessária conferência manual.
```

Essa regra é intencional para operações de desregistro: se o administrador
retirou o registro da unidade, uma falha posterior do banco não deve reativar o
número na Meta.

## O que este plano altera

1. PIN de registro sai do código e vai para o `.env`.
2. Requisições de registro/desregistro ganham timeout de 30/35 segundos.
3. O Admin diferencia falha do banco de falha do Redis quando possível.
4. O Admin informa quando a Meta funcionou antes da falha local.
5. Os links de cliente capturam somente `NoReverseMatch`.
6. Um job manual compara unidades do banco com registros Cloud API da WABA.
7. Um miss de unidade no Redis é confirmado no banco antes de ser ignorado.

## O que este plano não altera

- não cria compensação Meta;
- não sincroniza edição de `status_pagamento` com a Meta;
- não sincroniza edição de `phone_number_id` com a Meta;
- não transforma Redis em cache de melhor esforço;
- não muda o momento atual de atualização do Redis;
- não muda worker, fila, histórico, retries ou turnos;
- no webhook, altera somente o fallback de unidade ausente no Redis;
- não muda permissões de clientes;
- não muda scripts de deploy.

## Fluxos finais

### Meta falha

```text
Meta falha
-> banco não é alterado
-> Redis não é alterado
-> Admin mostra erro
```

### Meta funciona e banco falha

```text
Meta funciona
-> banco falha
-> transação local sofre rollback
-> Redis não é confirmado
-> Meta permanece como está
-> Admin mostra alerta explícito
```

### Meta funciona e Redis falha

O comportamento estrito atual é preservado:

```text
Meta funciona
-> Redis falha no preflight ou na reconstrução
-> banco não é confirmado
-> Meta permanece como está
-> Admin mostra alerta explícito
```

### Edição comum

```text
Meta não é chamada
-> banco/cache tentam atualizar
-> falha local é apresentada sem mencionar sucesso Meta
```

---

## Passo 1 - Atualizar o exemplo de ambiente

Arquivo alterado:

```text
.env.example
```

Código completo:

```dotenv
# Copie este arquivo para .env e preencha somente no ambiente local.
# Nunca registre o arquivo .env no Git.

DJANGO_SECRET_KEY=troque-por-uma-chave-forte
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_CSRF_TRUSTED_ORIGINS=
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DJANGO_SECURE_HSTS_SECONDS=0

DB_HOST=
DB_NAME=
DB_USER=
DB_PASSWORD=
DB_PORT=5432

REDIS_HOST=
REDIS_PORT=6379
REDIS_USERNAME=default
REDIS_PASSWORD=
REDIS_SSL=False

META_ACCESS_TOKEN=
META_WEBHOOK_VERIFY_TOKEN=troque-por-um-token-forte
META_APP_SECRET=
META_WEBHOOK_SIGNATURE_REQUIRED=False
META_WABA_ID=
META_PHONE_NUMBER_ID_DEV=
META_PHONE_REGISTRATION_PIN=
META_HTTP_CONNECT_TIMEOUT_SECONDS=30
META_HTTP_READ_TIMEOUT_SECONDS=35

WEBHOOK_MAX_BODY_BYTES=262144
```

Antes da aplicação, o `.env` local deve receber o PIN real. Ele não deve ser
registrado no Git.

---

## Passo 2 - Centralizar configuração Meta

Arquivo alterado:

```text
core/integrations/whatsapp/tools/config.py
```

Código completo:

```python
from core.config_env import env_int, env_optional, env_required


TOKEN_USUARIO_META = env_required("META_ACCESS_TOKEN")
WABA_ID = env_optional("META_WABA_ID")
PHONE_NUMBER_ID_DEV = env_optional("META_PHONE_NUMBER_ID_DEV")
PHONE_REGISTRATION_PIN = env_optional("META_PHONE_REGISTRATION_PIN")

META_HTTP_TIMEOUT = (
    env_int("META_HTTP_CONNECT_TIMEOUT_SECONDS", 30),
    env_int("META_HTTP_READ_TIMEOUT_SECONDS", 35),
)


def get_token_usuario_meta():
    return TOKEN_USUARIO_META


def get_waba_id():
    if not WABA_ID:
        raise RuntimeError(
            "Variavel de ambiente obrigatoria ausente: META_WABA_ID"
        )

    return WABA_ID


def get_phone_registration_pin():
    if not PHONE_REGISTRATION_PIN:
        raise RuntimeError(
            "Variavel de ambiente obrigatoria ausente: "
            "META_PHONE_REGISTRATION_PIN"
        )

    return PHONE_REGISTRATION_PIN


def get_meta_http_timeout():
    return META_HTTP_TIMEOUT
```

---

## Passo 3 - Adicionar timeout sem alterar o contrato das funções

### Arquivo 1 alterado

```text
core/integrations/whatsapp/tools/ativando_numero.py
```

Código completo:

```python
import logging

import requests

from core.integrations.whatsapp.tools.config import (
    get_meta_http_timeout,
    get_phone_registration_pin,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.registro")


def registrar_numero_whatsapp(phone_number_id, pin=None):
    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/register"

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "pin": pin or get_phone_registration_pin(),
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=get_meta_http_timeout(),
    )

    logger.info(
        "whatsapp_numero_registro_resposta | acao=registrar_numero phone_number_id=%s status=%s",
        short_value(phone_number_id),
        response.status_code,
    )

    return response.status_code, _normalizar_resposta(response)


def _normalizar_resposta(response):
    try:
        return response.json()

    except ValueError:
        return {
            "success": response.ok,
            "text": response.text,
        }
```

### Arquivo 2 alterado

```text
core/integrations/whatsapp/tools/desativando_numero.py
```

Código completo:

```python
import logging

import requests

from core.integrations.whatsapp.tools.config import (
    get_meta_http_timeout,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.registro")


def desregistrar_numero_whatsapp(phone_number_id):
    url = f"https://graph.facebook.com/v25.0/{phone_number_id}/deregister"

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        url,
        headers=headers,
        timeout=get_meta_http_timeout(),
    )

    logger.info(
        "whatsapp_numero_desregistro_resposta | acao=desregistrar_numero phone_number_id=%s status=%s",
        short_value(phone_number_id),
        response.status_code,
    )

    return response.status_code, _normalizar_resposta(response)


def _normalizar_resposta(response):
    try:
        return response.json()

    except ValueError:
        return {
            "success": response.ok,
            "text": response.text,
        }
```

O contrato `(status_code, resposta)` é preservado. O Admin continua decidindo
sucesso pelos códigos `200/204` e pelo campo `success`.

---

## Passo 4 - Adicionar reconciliação manual de unidades

Arquivo alterado:

```text
core/integrations/whatsapp/tools/block_report.py
```

Código completo:

```python
import requests

from core.database.connection_aws import get_conn
from core.integrations.whatsapp.tools.config import (
    get_meta_http_timeout,
    get_token_usuario_meta,
    get_waba_id,
)
from core.integrations.whatsapp.tools.usuarios import (
    listar_usuarios_bloqueados_meta,
)
from core.repositories.bloqueio_meta import (
    listar_bloqueios_meta_banco_para_reconciliacao,
)
from core.repositories.querys import (
    buscar_unidades_para_listagem_bloqueios,
)


def listar_bloqueados_de_cada_unidade(imprimir=True):
    conn = get_conn(application_name="script_chatbot")
    cursor = conn.cursor()
    resultado = []

    try:
        unidades = buscar_unidades_para_listagem_bloqueios(
            cursor
        )

        for id_unidade, nome_unidade, phone_id_unidade in unidades:
            if imprimir:
                print(
                    f"unidade {id_unidade} {nome_unidade} "
                    f"phone id ({phone_id_unidade}):"
                )

            bloqueados = listar_usuarios_bloqueados_meta(
                phone_id_unidade
            )
            wa_ids_bloqueados = [
                wa_id
                for wa_id in (
                    _extrair_wa_id_bloqueado(usuario)
                    for usuario in bloqueados
                )
                if wa_id
            ]

            resultado.append({
                "id_unidade": id_unidade,
                "nome_unidade": nome_unidade,
                "phone_id_unidade": str(phone_id_unidade),
                "wa_ids_bloqueados": wa_ids_bloqueados,
            })

            if imprimir and not wa_ids_bloqueados:
                print("   - nenhum numero bloqueado")

            if imprimir:
                for wa_id in wa_ids_bloqueados:
                    print(f"   - {wa_id} numero bloqueado")

                print()

        return resultado

    finally:
        conn.close()


def job_reconciliacao_bloqueios_cliente_unidades_meta():
    bloqueios_meta = listar_bloqueados_de_cada_unidade(
        imprimir=False,
    )
    bloqueios_banco = _listar_bloqueios_banco()

    meta_por_chave = {}
    banco_por_chave = {}

    for unidade in bloqueios_meta:
        phone_id_unidade = unidade["phone_id_unidade"]

        for wa_id_cliente in unidade["wa_ids_bloqueados"]:
            chave = (phone_id_unidade, wa_id_cliente)
            meta_por_chave[chave] = unidade

    for bloqueio in bloqueios_banco:
        chave = (
            bloqueio["phone_id_unidade"],
            bloqueio["wa_id_cliente"],
        )
        banco_por_chave[chave] = bloqueio

    somente_meta = sorted(
        set(meta_por_chave) - set(banco_por_chave)
    )
    somente_banco = sorted(
        set(banco_por_chave) - set(meta_por_chave)
    )
    sincronizados = sorted(
        set(meta_por_chave) & set(banco_por_chave)
    )

    print("===== RECONCILIACAO BLOQUEIOS META X BANCO =====")
    print(f"bloqueios_sincronizados: {len(sincronizados)}")
    print(f"somente_na_meta: {len(somente_meta)}")
    print(f"somente_no_banco: {len(somente_banco)}")
    print()

    if somente_meta:
        print("SOMENTE NA META:")
        for phone_id_unidade, wa_id_cliente in somente_meta:
            unidade = meta_por_chave[
                (phone_id_unidade, wa_id_cliente)
            ]
            print(
                f"   - wa_id {wa_id_cliente} bloqueado na Meta, "
                f"mas ausente no banco | unidade "
                f"{unidade['id_unidade']} "
                f"{unidade['nome_unidade']} phone id "
                f"({phone_id_unidade})"
            )
        print()

    if somente_banco:
        print("SOMENTE NO BANCO:")
        for phone_id_unidade, wa_id_cliente in somente_banco:
            bloqueio = banco_por_chave[
                (phone_id_unidade, wa_id_cliente)
            ]
            print(
                f"   - wa_id {wa_id_cliente} registrado no banco, "
                f"mas ausente na Meta | bloqueio "
                f"{bloqueio['id_bloqueio']} unidade "
                f"{bloqueio['id_unidade']} "
                f"{bloqueio['nome_unidade']} phone id "
                f"({phone_id_unidade})"
            )
        print()

    if not somente_meta and not somente_banco:
        print("OK: banco e Meta estao sincronizados.")

    return {
        "sincronizados": sincronizados,
        "somente_meta": somente_meta,
        "somente_banco": somente_banco,
    }


def job_reconciliacao_register__waba_unidades_meta():
    unidades_banco = _listar_unidades_banco()
    numeros_waba_meta = _listar_numeros_waba_meta()

    banco_por_phone_id = {
        unidade["phone_id_unidade"]: unidade
        for unidade in unidades_banco
    }
    meta_por_phone_id = {
        numero["phone_id_unidade"]: numero
        for numero in numeros_waba_meta
        if numero["registrado_cloud_api"]
    }

    phone_ids_banco = set(banco_por_phone_id)
    phone_ids_meta = set(meta_por_phone_id)

    sincronizados = sorted(
        phone_ids_banco & phone_ids_meta
    )
    somente_meta = sorted(
        phone_ids_meta - phone_ids_banco
    )
    somente_banco = sorted(
        phone_ids_banco - phone_ids_meta
    )

    print(
        "===== RECONCILIACAO REGISTER WABA META X BANCO ====="
    )
    print(f"unidades_sincronizadas: {len(sincronizados)}")
    print(f"somente_na_meta: {len(somente_meta)}")
    print(f"somente_no_banco: {len(somente_banco)}")
    print()

    if sincronizados:
        print("SINCRONIZADAS:")
        for phone_id_unidade in sincronizados:
            unidade = banco_por_phone_id[phone_id_unidade]
            numero_meta = meta_por_phone_id[phone_id_unidade]
            print(
                f"   - unidade {unidade['id_unidade']} "
                f"{unidade['nome_unidade']} | phone id "
                f"({phone_id_unidade}) | Meta status "
                f"{numero_meta['status']}"
            )
        print()

    if somente_meta:
        print("SOMENTE NA META:")
        for phone_id_unidade in somente_meta:
            numero_meta = meta_por_phone_id[phone_id_unidade]
            print(
                f"   - phone id ({phone_id_unidade}) registrado "
                f"como Cloud API na Meta, mas ausente no banco | "
                f"numero {numero_meta['display_phone_number']} | "
                f"nome {numero_meta['verified_name']} | "
                f"status {numero_meta['status']}"
            )
        print()

    if somente_banco:
        print("SOMENTE NO BANCO:")
        for phone_id_unidade in somente_banco:
            unidade = banco_por_phone_id[phone_id_unidade]
            print(
                f"   - unidade {unidade['id_unidade']} "
                f"{unidade['nome_unidade']} | phone id "
                f"({phone_id_unidade}) existe no banco, mas nao "
                "aparece registrado como Cloud API na Meta"
            )
        print()

    if not somente_meta and not somente_banco:
        print(
            "OK: unidades do banco e registros Cloud API da Meta "
            "estao sincronizados."
        )

    return {
        "unidades_banco": unidades_banco,
        "numeros_waba_meta": numeros_waba_meta,
        "sincronizados": sincronizados,
        "somente_meta": somente_meta,
        "somente_banco": somente_banco,
    }


def _listar_unidades_banco():
    conn = get_conn(application_name="script_chatbot")
    cursor = conn.cursor()

    try:
        unidades = buscar_unidades_para_listagem_bloqueios(
            cursor
        )

    finally:
        conn.close()

    return [
        {
            "id_unidade": id_unidade,
            "nome_unidade": nome_unidade,
            "phone_id_unidade": str(phone_id_unidade),
        }
        for (
            id_unidade,
            nome_unidade,
            phone_id_unidade,
        ) in unidades
    ]


def _listar_numeros_waba_meta():
    url = (
        f"https://graph.facebook.com/v25.0/"
        f"{get_waba_id()}/phone_numbers"
    )
    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
    }
    params = {
        "fields": (
            "id,display_phone_number,verified_name,"
            "quality_rating,code_verification_status,"
            "platform_type,name_status,status"
        ),
        "limit": 100,
    }
    numeros = []

    while url:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=get_meta_http_timeout(),
        )
        response.raise_for_status()
        payload = response.json()

        for numero in payload.get("data", []):
            platform_type = numero.get("platform_type")
            numeros.append({
                "phone_id_unidade": str(numero["id"]),
                "display_phone_number": numero.get(
                    "display_phone_number"
                ),
                "verified_name": numero.get("verified_name"),
                "quality_rating": numero.get(
                    "quality_rating"
                ),
                "code_verification_status": numero.get(
                    "code_verification_status"
                ),
                "platform_type": platform_type,
                "name_status": numero.get("name_status"),
                "status": numero.get("status"),
                "registrado_cloud_api": (
                    platform_type == "CLOUD_API"
                ),
            })

        url = payload.get("paging", {}).get("next")
        params = None

    return numeros


def _listar_bloqueios_banco():
    conn = get_conn(application_name="script_chatbot")
    cursor = conn.cursor()

    try:
        bloqueios = (
            listar_bloqueios_meta_banco_para_reconciliacao(
                cursor
            )
        )

    finally:
        conn.close()

    return [
        {
            "id_bloqueio": id_bloqueio,
            "wa_id_cliente": str(wa_id_cliente),
            "id_unidade": id_unidade,
            "phone_id_unidade": str(phone_id_unidade),
            "nome_unidade": nome_unidade,
        }
        for (
            id_bloqueio,
            wa_id_cliente,
            id_unidade,
            phone_id_unidade,
            nome_unidade,
        ) in bloqueios
    ]


def _extrair_wa_id_bloqueado(usuario):
    wa_id = getattr(usuario, "wa_id", usuario)

    if wa_id is None:
        return None

    wa_id = str(wa_id).strip()
    return wa_id or None


"""FUNCOES MANUAIS"""
# job_reconciliacao_bloqueios_cliente_unidades_meta()
# job_reconciliacao_register__waba_unidades_meta()
```

### Garantias do job

- usa o único `META_WABA_ID` configurado;
- pagina todos os números retornados pela Meta;
- considera registrado o número com `platform_type == "CLOUD_API"`;
- consulta todas as unidades cadastradas no banco;
- mostra sincronizados, somente na Meta e somente no banco;
- não registra, desregistra, cria, edita ou exclui nada;
- não é importado pelo webhook nem pelo worker;
- só executa quando chamado manualmente.

O campo `platform_type` é usado porque estar associado à WABA não significa,
sozinho, que o número esteja registrado para Cloud API.

---

## Passo 5 - Consultar o banco em miss de unidade no webhook

Arquivo alterado:

```text
core/cache/cache_unidade.py
```

Código completo:

```python
import logging
import threading
import time

from core.database.connection_aws import get_conn
from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value
from core.repositories.cache_control import (
    buscar_versao_cache_unidades,
)
from core.repositories.querys import (
    buscar_id_unidade_por_phone_id,
    pegar_unidades,
)


logger = logging.getLogger("cache.unidades")

REDIS_KEY = "unidades_cache"
CACHE_VERSION_KEY = "unidades_cache_version"
CACHE_DB_VERSION_KEY = "unidades_cache_db_version"
CACHE_TEMP_KEY = f"{REDIS_KEY}:tmp"
VERSAO_CHECK_INTERVAL_SEGUNDOS = 300

_redis_unidades_falhou = False
_ultima_checagem_versao = 0
_versao_lock = threading.Lock()


class UnidadeNaoEncontrada(Exception):
    pass


class CacheUnidadesIndisponivel(Exception):
    pass


class ValidacaoUnidadeIndisponivel(Exception):
    pass


def carregar_unidades_redis_primeira_vez():
    conn = None

    try:
        conn = get_conn(application_name="cache_chatbot")
        cursor = conn.cursor()
        return carregar_cache_redis(cursor)

    finally:
        if conn:
            conn.close()


def recarregar_cache_unidades():
    conn = None

    try:
        conn = get_conn(application_name="cache_chatbot")
        cursor = conn.cursor()
        return carregar_cache_redis(cursor)

    except Exception as exc:
        logger.exception(
            "cache_recarregar_falhou | origem=admin acao=manter_cache_atual erro=%s",
            exc,
        )
        return None

    finally:
        if conn:
            conn.close()


def validar_cache_unidades_disponivel_ou_erro():
    try:
        r = get_redis_safe(
            retries=1,
            delay=0,
            validate=True,
        )
        key = f"{REDIS_KEY}:admin_preflight"
        r.set(key, "ok", ex=10)
        r.delete(key)

        logger.debug(
            "cache_unidades_preflight_ok | acao=permitir_admin"
        )
        return True

    except Exception as exc:
        _marcar_redis_falhou()
        logger.exception(
            "cache_unidades_preflight_falhou | acao=bloquear_admin erro=%s",
            exc,
        )
        raise CacheUnidadesIndisponivel(
            "Redis indisponivel para atualizar cache de unidades"
        ) from exc


def recarregar_cache_unidades_ou_erro(cursor=None):
    conn = None

    try:
        cursor_uso = cursor

        if cursor_uso is None:
            conn = get_conn(application_name="cache_chatbot")
            cursor_uso = conn.cursor()

        return carregar_cache_redis(
            cursor_uso,
            redis_retries=1,
            redis_delay=0,
        )

    except Exception as exc:
        _marcar_redis_falhou()
        logger.exception(
            "cache_recarregar_falhou | origem=admin acao=bloquear_alteracao erro=%s",
            exc,
        )
        raise CacheUnidadesIndisponivel(
            "Redis falhou ao recriar cache de unidades"
        ) from exc

    finally:
        if conn:
            conn.close()


def carregar_cache_redis(
    cursor,
    redis_retries=3,
    redis_delay=2,
):
    r = get_redis_safe(
        retries=redis_retries,
        delay=redis_delay,
    )
    unidades = _normalizar_unidades(pegar_unidades(cursor))
    versao_banco = buscar_versao_cache_unidades(cursor)
    total = _salvar_cache(r, unidades, versao_banco)

    _marcar_versao_conferida()
    logger.info(
        "cache_atualizado | acao=salvar_redis unidades=%s versao=%s",
        total,
        versao_banco,
    )
    return total


def carregar_unidades_cache_webhook(cursor):
    return carregar_cache_redis(cursor)


def obter_id_unidade_redis_ou_plsql(
    id_phone_unidade,
    cursor,
):
    phone_key = _normalizar_phone_number_id(
        id_phone_unidade
    )

    if phone_key is None:
        raise UnidadeNaoEncontrada(
            "phone_number_id invalido"
        )

    try:
        r = get_redis_safe(
            retries=1,
            delay=0,
            validate=False,
        )
        _sincronizar_cache_unidades_por_versao(
            r,
            origem="worker",
            cursor=cursor,
        )

        if _cache_valido(r):
            id_unidade = r.hget(REDIS_KEY, phone_key)

            if _id_unidade_valido(id_unidade):
                return int(id_unidade)

            raise UnidadeNaoEncontrada(
                "Unidade nao encontrada no cache ativo: "
                f"{phone_key}"
            )

        logger.warning(
            "cache_invalido | acao=fallback_banco origem=worker phone_number_id=%s",
            short_value(phone_key),
        )

    except UnidadeNaoEncontrada:
        raise

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning(
            "cache_indisponivel | acao=fallback_banco origem=worker phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )

    id_unidade = buscar_id_unidade_por_phone_id(
        phone_key,
        cursor,
    )

    _tentar_recarregar_cache(cursor, origem="worker")

    if not _id_unidade_valido(id_unidade):
        raise UnidadeNaoEncontrada(
            f"Unidade nao encontrada: {phone_key}"
        )

    return int(id_unidade)


def garantir_cache_unidades_se_necessario(cursor):
    try:
        r = get_redis_safe(
            retries=1,
            delay=0,
            validate=False,
        )
        _sincronizar_cache_unidades_por_versao(
            r,
            origem="manual",
            cursor=cursor,
        )

        if not _cache_valido(r):
            logger.info(
                "cache_invalido | acao=recarregar origem=manual"
            )
            return carregar_cache_redis(
                cursor,
                redis_retries=1,
                redis_delay=0,
            )

        return None

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning(
            "cache_validacao_falhou | origem=manual acao=manter_cache_atual erro=%s",
            exc,
        )
        return None


def unidade_esta_ativa(phone_number_id):
    phone_key = _normalizar_phone_number_id(
        phone_number_id
    )

    if phone_key is None:
        return False

    try:
        r = get_redis_safe(
            retries=1,
            delay=0,
            validate=False,
        )
        _sincronizar_cache_unidades_por_versao(
            r,
            origem="webhook",
        )

        if _cache_valido(r):
            if r.hexists(REDIS_KEY, phone_key):
                return True

            logger.info(
                "cache_unidade_miss | acao=confirmar_no_banco origem=webhook phone_number_id=%s",
                short_value(phone_key),
            )
            return _unidade_esta_ativa_banco_e_repara_cache(
                phone_key,
                reparar_cache_se_ausente=False,
            )

        logger.warning(
            "cache_invalido | acao=fallback_banco origem=webhook phone_number_id=%s",
            short_value(phone_key),
        )

    except ValidacaoUnidadeIndisponivel:
        raise

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning(
            "cache_indisponivel | acao=fallback_banco origem=webhook phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )

    return _unidade_esta_ativa_banco_e_repara_cache(
        phone_key,
        reparar_cache_se_ausente=True,
    )


def _unidade_esta_ativa_banco_e_repara_cache(
    phone_key,
    reparar_cache_se_ausente=True,
):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        id_unidade = buscar_id_unidade_por_phone_id(
            phone_key,
            cursor,
        )
        unidade_encontrada = _id_unidade_valido(id_unidade)

        if unidade_encontrada or reparar_cache_se_ausente:
            _tentar_recarregar_cache(
                cursor,
                origem="webhook",
            )

        return unidade_encontrada

    except Exception as exc:
        logger.exception(
            "fallback_banco_unidade_falhou | origem=webhook acao=levantar_indisponibilidade phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )
        raise ValidacaoUnidadeIndisponivel(
            "Nao foi possivel validar a unidade no Redis "
            "nem no banco"
        ) from exc

    finally:
        if conn:
            conn.close()


def _sincronizar_cache_unidades_por_versao(
    r,
    origem,
    cursor=None,
):
    if not _deve_conferir_versao():
        return None

    with _versao_lock:
        if not _deve_conferir_versao():
            return None

        conn = None

        try:
            cursor_uso = cursor

            if cursor_uso is None:
                conn = get_conn(
                    application_name=(
                        _application_name_por_origem(origem)
                    )
                )
                cursor_uso = conn.cursor()

            versao_banco = buscar_versao_cache_unidades(
                cursor_uso
            )
            versao_redis = _int_ou_none(
                r.get(CACHE_DB_VERSION_KEY)
            )

            if (
                versao_redis != versao_banco
                or not _cache_valido(r)
            ):
                logger.info(
                    "cache_versao_divergente | origem=%s redis=%s banco=%s acao=recarregar",
                    origem,
                    versao_redis,
                    versao_banco,
                )
                return carregar_cache_redis(
                    cursor_uso,
                    redis_retries=1,
                    redis_delay=0,
                )

            _marcar_versao_conferida()
            return None

        except Exception as exc:
            _marcar_checagem_tentada()
            logger.warning(
                "cache_versao_checar_falhou | origem=%s acao=manter_cache_atual erro=%s",
                origem,
                exc,
            )
            return None

        finally:
            if conn:
                conn.close()


def _tentar_recarregar_cache(cursor, origem):
    try:
        return carregar_cache_redis(
            cursor,
            redis_retries=1,
            redis_delay=0,
        )

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning(
            "cache_reparo_falhou | origem=%s acao=manter_cache_atual erro=%s",
            origem,
            exc,
        )
        return None


def _salvar_cache(r, unidades, versao_banco):
    total = len(unidades)

    pipe = r.pipeline()
    pipe.delete(CACHE_TEMP_KEY)

    if total > 0:
        pipe.hset(CACHE_TEMP_KEY, mapping=unidades)
        pipe.rename(CACHE_TEMP_KEY, REDIS_KEY)
    else:
        pipe.delete(REDIS_KEY)

    pipe.set(CACHE_VERSION_KEY, total)
    pipe.set(CACHE_DB_VERSION_KEY, versao_banco)
    pipe.execute()

    return total


def _cache_valido(r):
    try:
        versao = r.get(CACHE_VERSION_KEY)

        if versao is None:
            return False

        total_esperado = int(versao)

        if total_esperado == 0:
            return True

        return (
            r.hlen(REDIS_KEY)
            == total_esperado
        )

    except Exception as exc:
        logger.warning(
            "cache_validacao_erro | acao=considerar_invalido_e_usar_fallback erro=%s",
            exc,
        )
        return False


def _deve_conferir_versao():
    agora = time.monotonic()

    if _redis_unidades_falhou:
        return True

    if _ultima_checagem_versao == 0:
        return True

    return (
        agora - _ultima_checagem_versao
        >= VERSAO_CHECK_INTERVAL_SEGUNDOS
    )


def _marcar_redis_falhou():
    global _redis_unidades_falhou
    _redis_unidades_falhou = True


def _marcar_versao_conferida():
    global _redis_unidades_falhou
    global _ultima_checagem_versao

    _redis_unidades_falhou = False
    _ultima_checagem_versao = time.monotonic()


def _marcar_checagem_tentada():
    global _ultima_checagem_versao
    _ultima_checagem_versao = time.monotonic()


def _int_ou_none(valor):
    try:
        return int(valor)

    except (TypeError, ValueError):
        return None


def _application_name_por_origem(origem):
    if origem == "worker":
        return "worker_chatbot"

    if origem == "webhook":
        return "webhook_chatbot"

    return "cache_chatbot"


def _normalizar_unidades(unidades_raw):
    if isinstance(unidades_raw, dict):
        return {
            str(phone_number_id).strip(): int(id_unidade)
            for phone_number_id, id_unidade
            in unidades_raw.items()
            if (
                phone_number_id
                and _id_unidade_valido(id_unidade)
            )
        }

    if isinstance(unidades_raw, list):
        unidades = {}

        for unidade in unidades_raw:
            if isinstance(unidade, dict):
                phone_number_id = unidade.get(
                    "phone_number_id"
                )
                id_unidade = unidade.get("id_unidade")

            else:
                try:
                    phone_number_id = unidade[0]
                    id_unidade = unidade[1]

                except (TypeError, IndexError):
                    continue

            if (
                phone_number_id
                and _id_unidade_valido(id_unidade)
            ):
                unidades[
                    str(phone_number_id).strip()
                ] = int(id_unidade)

        return unidades

    return {}


def _id_unidade_valido(id_unidade):
    try:
        return int(id_unidade) > 0

    except (TypeError, ValueError):
        return False


def _normalizar_phone_number_id(id_phone_unidade):
    if id_phone_unidade is None:
        return None

    phone_key = str(id_phone_unidade).strip()
    return phone_key or None
```

### Comportamento acrescentado

```text
cache válido + unidade presente
-> retorna True sem consultar banco

cache válido + unidade ausente
-> consulta banco

banco encontrou unidade ativa
-> retorna True
-> tenta reconstruir Redis

banco confirmou ausência/inatividade
-> retorna False
-> não reconstrói desnecessariamente o cache válido

banco falhou
-> ValidacaoUnidadeIndisponivel
-> post_flow retorna HTTP 503
```

O worker permanece inalterado. Seu fluxo de
`reparar_cache_unidade_stale_se_fk_invalida()` continua responsável por um ID
stale que ainda estava presente no Redis, mas deixou de existir no banco.

### Testes do fallback

Arquivo alterado:

```text
tests/unit/test_cache_and_admin.py
```

Código completo:

```python
import unittest
from unittest.mock import patch

from django.contrib import admin, messages

from webhook.admin import UnidadeAdmin
from webhook.models import Unidade
from core.cache import cache_reset, cache_unidade
from core.cache.runtime import (
    cache_cliente,
    cache_conversas_bloqueadas,
)


class FakeRedis:
    def __init__(self):
        self.deleted = []
        self.patterns = []

    def delete(self, *keys):
        self.deleted.extend(keys)
        return len(keys)

    def scan_iter(self, match, count=500):
        self.patterns.append((match, count))
        return [f"{match}:1", f"{match}:2"]


class FakeRedisUnidade:
    def __init__(self, presente):
        self.presente = presente

    def hexists(self, _key, _field):
        return self.presente


class FakeRequest:
    user = "tester"

    def __init__(self):
        self.messages = []


def capturar_message_user(
    _self,
    request,
    message,
    level=messages.INFO,
):
    request.messages.append((message, level))


class CacheAndAdminTests(unittest.TestCase):
    def test_cache_cliente_redis_falha_retorna_none(self):
        with patch.object(
            cache_cliente,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ):
            self.assertIsNone(
                cache_cliente.buscar_cliente_cache(
                    "5571999999999"
                )
            )

    def test_cache_unidade_redis_falha_usa_banco(self):
        chamadas = []

        with patch.object(
            cache_unidade,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_unidade,
            "_unidade_esta_ativa_banco_e_repara_cache",
            lambda phone, **_kwargs: (
                chamadas.append(phone) or True
            ),
        ):
            self.assertTrue(
                cache_unidade.unidade_esta_ativa("123456")
            )

        self.assertEqual(chamadas, ["123456"])

    def test_cache_unidade_miss_confirma_no_banco(self):
        redis_fake = FakeRedisUnidade(presente=False)
        chamadas = []

        with patch.object(
            cache_unidade,
            "get_redis_safe",
            return_value=redis_fake,
        ), patch.object(
            cache_unidade,
            "_sincronizar_cache_unidades_por_versao",
        ), patch.object(
            cache_unidade,
            "_cache_valido",
            return_value=True,
        ), patch.object(
            cache_unidade,
            "_unidade_esta_ativa_banco_e_repara_cache",
            lambda phone, **kwargs: (
                chamadas.append((phone, kwargs)) or True
            ),
        ):
            resultado = cache_unidade.unidade_esta_ativa(
                "123456"
            )

        self.assertTrue(resultado)
        self.assertEqual(
            chamadas,
            [
                (
                    "123456",
                    {"reparar_cache_se_ausente": False},
                )
            ],
        )

    def test_cache_unidade_hit_nao_consulta_banco(self):
        redis_fake = FakeRedisUnidade(presente=True)

        with patch.object(
            cache_unidade,
            "get_redis_safe",
            return_value=redis_fake,
        ), patch.object(
            cache_unidade,
            "_sincronizar_cache_unidades_por_versao",
        ), patch.object(
            cache_unidade,
            "_cache_valido",
            return_value=True,
        ), patch.object(
            cache_unidade,
            "_unidade_esta_ativa_banco_e_repara_cache",
        ) as fallback_banco:
            resultado = cache_unidade.unidade_esta_ativa(
                "123456"
            )

        self.assertTrue(resultado)
        fallback_banco.assert_not_called()

    def test_cache_unidade_redis_e_banco_falham_sinaliza_indisponibilidade(
        self,
    ):
        with patch.object(
            cache_unidade,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_unidade,
            "get_conn",
            side_effect=ConnectionError("banco caiu"),
        ):
            with self.assertRaises(
                cache_unidade.ValidacaoUnidadeIndisponivel
            ):
                cache_unidade.unidade_esta_ativa("123456")

    def test_cache_conversa_bloqueada_redis_falha_usa_banco(
        self,
    ):
        chamadas = []

        with patch.object(
            cache_conversas_bloqueadas,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_conversas_bloqueadas,
            "_conversa_esta_bloqueada_banco_e_repara_cache",
            lambda cliente, phone: (
                chamadas.append((cliente, phone)) or True
            ),
        ):
            self.assertTrue(
                cache_conversas_bloqueadas
                .conversa_esta_bloqueada_cache(
                    "5571999999999",
                    "123456",
                )
            )

        self.assertEqual(
            chamadas,
            [("5571999999999", "123456")],
        )

    def test_cache_reset_limpa_prefixos_e_recria_unidades(self):
        fake_redis = FakeRedis()

        with patch.object(
            cache_reset,
            "get_redis_safe",
            return_value=fake_redis,
        ), patch.object(
            cache_reset,
            "recarregar_cache_unidades",
            return_value=3,
        ):
            resultado = cache_reset.resetar_cache_redis_dev()

        self.assertEqual(
            resultado["unidades_recriadas"],
            3,
        )
        self.assertGreaterEqual(
            resultado["chaves_exatas_removidas"],
            1,
        )
        self.assertEqual(
            resultado["chaves_por_prefixo_removidas"],
            6,
        )
        self.assertTrue(
            any(
                padrao == "cliente_cache:*"
                for padrao, _count in fake_redis.patterns
            )
        )
        self.assertTrue(
            any(
                padrao == "conversa_bloqueada:*"
                for padrao, _count in fake_redis.patterns
            )
        )
        self.assertTrue(
            any(
                padrao.startswith("webhook_flood_rate")
                for padrao, _count in fake_redis.patterns
            )
        )

    def test_admin_unidade_bloqueia_alteracao_se_redis_falhar(
        self,
    ):
        unidade_admin = UnidadeAdmin(Unidade, admin.site)
        request = FakeRequest()

        with patch.object(
            UnidadeAdmin,
            "message_user",
            capturar_message_user,
        ), patch(
            "webhook.admin.validar_cache_unidades_disponivel_ou_erro",
            side_effect=(
                cache_unidade.CacheUnidadesIndisponivel(
                    "redis caiu"
                )
            ),
        ):
            resultado = (
                unidade_admin
                ._validar_cache_unidades_antes_de_alterar(
                    request,
                    "salvar",
                    meta_validada=True,
                )
            )

        self.assertFalse(resultado)
        self.assertEqual(
            request.messages[0][1],
            messages.ERROR,
        )
        self.assertIn(
            "Redis falhou",
            request.messages[0][0],
        )
        self.assertIn(
            "não foi salva no banco",
            request.messages[0][0],
        )


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 6 - Melhorar os avisos do Django Admin

Arquivo alterado:

```text
callback/webhook/admin.py
```

Código completo:

```python
import logging

from django.contrib import admin, messages
from django.db import DatabaseError, connection
from django.http import HttpResponseRedirect
from django.urls import NoReverseMatch, reverse
from django.utils.html import format_html

from core.cache.cache_unidade import (
    CacheUnidadesIndisponivel,
    recarregar_cache_unidades_ou_erro,
    validar_cache_unidades_disponivel_ou_erro,
)
from core.integrations.whatsapp.tools.ativando_numero import (
    registrar_numero_whatsapp,
)
from core.integrations.whatsapp.tools.desativando_numero import (
    desregistrar_numero_whatsapp,
)
from core.integrations.whatsapp.tools.usuarios import (
    desbloquear_usuario_meta,
)
from core.logging_config import short_value
from core.repositories.cache_control import (
    incrementar_versao_cache_unidades,
)

from .models import (
    CacheControle,
    Cliente,
    ClienteBloqueadoMeta,
    Conversa,
    Dependente,
    Etapa,
    FilaMensagens,
    HistoricoMensagens,
    RespostasDesafios,
    Unidade,
    WebhookFloodEvento,
)


logger = logging.getLogger(__name__)


class SomenteVisualizacaoAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):

    list_display = (
        "id_unidade",
        "nome",
        "cnpj",
        "telefone",
        "email_responsavel",
        "link_agendamento_clickable",
        "status_pagamento",
    )

    search_fields = (
        "nome",
        "cnpj",
        "telefone",
        "email_responsavel",
        "link_agendamento",
    )

    list_filter = ("status_pagamento",)
    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"

    def changeform_view(
        self,
        request,
        object_id=None,
        form_url="",
        extra_context=None,
    ):
        try:
            return super().changeform_view(
                request,
                object_id=object_id,
                form_url=form_url,
                extra_context=extra_context,
            )

        except CacheUnidadesIndisponivel as exc:
            if self._falha_cache_originada_no_banco(exc):
                return self._responder_falha_banco(
                    request,
                    object_id,
                    exc,
                )

            logger.exception(
                "admin_unidade_cache_falhou | acao=rollback_admin object_id=%s meta_ok=%s erro=%s",
                object_id,
                self._meta_sucesso_nesta_requisicao(request),
                exc,
            )
            self.message_user(
                request,
                self._mensagem_falha_redis(request),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(request.path)

        except DatabaseError as exc:
            return self._responder_falha_banco(
                request,
                object_id,
                exc,
            )

    def get_form(self, request, obj=None, change=False, **kwargs):
        base_form = super().get_form(
            request,
            obj,
            change=change,
            **kwargs,
        )
        model_admin = self

        class UnidadeAdminForm(base_form):
            def _post_clean(self):
                super()._post_clean()

                if change or self.errors:
                    if change and not self.errors:
                        model_admin._validar_cache_unidades_form(
                            self,
                            request,
                            meta_validada=False,
                        )
                    return

                phone_number_id = self.cleaned_data.get(
                    "phone_number_id"
                )

                if not phone_number_id:
                    return

                if not model_admin._registrar_meta_antes_de_salvar(
                    request,
                    phone_number_id,
                ):
                    self.add_error(
                        "phone_number_id",
                        (
                            "A Meta falhou ao registrar este número. "
                            "Unidade não foi salva."
                        ),
                    )
                    return

                model_admin._validar_cache_unidades_form(
                    self,
                    request,
                    meta_validada=True,
                )

        return UnidadeAdminForm

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._registrar_alteracao_cache_unidades()

    def delete_model(self, request, obj):
        if not self._meta_desregistrada_nesta_requisicao(
            request,
            obj,
        ):
            if not self._desregistrar_meta_antes_de_excluir(
                request,
                obj,
            ):
                return

        if not self._cache_validado_nesta_requisicao(
            request,
            obj,
        ):
            if not self._validar_cache_unidades_antes_de_alterar(
                request,
                "excluir",
                meta_validada=True,
            ):
                return

        super().delete_model(request, obj)
        self._registrar_alteracao_cache_unidades()

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_unidade_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            (
                "Exclusão em massa de unidade não permitida. "
                "Exclua uma unidade por vez."
            ),
            level=messages.ERROR,
        )

    def delete_view(self, request, object_id, extra_context=None):
        try:
            if request.method == "POST":
                obj = self.get_object(request, object_id)

                if obj and not self._desregistrar_meta_antes_de_excluir(
                    request,
                    obj,
                ):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj and not (
                    self._validar_cache_unidades_antes_de_alterar(
                        request,
                        "excluir",
                        meta_validada=True,
                    )
                ):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj:
                    self._marcar_meta_desregistrada_na_requisicao(
                        request,
                        obj,
                    )
                    self._marcar_cache_validado_na_requisicao(
                        request,
                        obj,
                    )

            return super().delete_view(
                request,
                object_id,
                extra_context,
            )

        except CacheUnidadesIndisponivel as exc:
            if self._falha_cache_originada_no_banco(exc):
                return self._responder_falha_banco_delete(
                    request,
                    object_id,
                    exc,
                )

            logger.exception(
                "admin_unidade_cache_delete_falhou | acao=rollback_admin object_id=%s meta_ok=%s erro=%s",
                object_id,
                self._meta_sucesso_nesta_requisicao(request),
                exc,
            )
            self.message_user(
                request,
                self._mensagem_falha_redis(request),
                level=messages.ERROR,
            )
            return HttpResponseRedirect(
                reverse(
                    "admin:webhook_unidade_change",
                    args=[object_id],
                )
            )

        except DatabaseError as exc:
            return self._responder_falha_banco_delete(
                request,
                object_id,
                exc,
            )

    def _registrar_alteracao_cache_unidades(self):
        with connection.cursor() as cursor:
            versao = incrementar_versao_cache_unidades(cursor)
            total_unidades = recarregar_cache_unidades_ou_erro(
                cursor
            )

        logger.info(
            "cache_unidades_versao_incrementada | acao=incrementar_versao_e_recarregar versao=%s unidades=%s",
            versao,
            total_unidades,
        )

    def link_agendamento_clickable(self, obj):
        if obj.link_agendamento:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_agendamento,
            )
        return "-"

    link_agendamento_clickable.short_description = "Agendamento"

    def _registrar_meta_antes_de_salvar(
        self,
        request,
        phone_number_id,
    ):
        try:
            status, resposta = registrar_numero_whatsapp(
                phone_number_id
            )

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_registrar_falhou | acao=bloquear_save phone_number_id=%s status=%s resposta=%s",
                    short_value(phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    (
                        "Erro ao registrar número no WhatsApp. "
                        f"Unidade não foi salva: {resposta}"
                    ),
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="registrar",
                phone_number_id=phone_number_id,
            )
            logger.info(
                "whatsapp_numero_registrado | acao=permitir_save phone_number_id=%s status=%s",
                short_value(phone_number_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_numero_registrar_erro | acao=bloquear_save phone_number_id=%s erro=%s",
                short_value(phone_number_id),
                exc,
            )
            self.message_user(
                request,
                (
                    "Erro inesperado ao registrar número. "
                    f"Unidade não foi salva: {exc}"
                ),
                level=messages.ERROR,
            )
            return False

    def _desregistrar_meta_antes_de_excluir(
        self,
        request,
        obj,
    ):
        try:
            status, resposta = desregistrar_numero_whatsapp(
                obj.phone_number_id
            )

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_desregistrar_falhou | acao=bloquear_delete phone_number_id=%s status=%s resposta=%s",
                    short_value(obj.phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    (
                        "Erro ao remover registro do número na Meta. "
                        f"Unidade mantida no banco: {resposta}"
                    ),
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desregistrar",
                phone_number_id=obj.phone_number_id,
            )
            logger.warning(
                "whatsapp_numero_desregistrado | acao=permitir_delete phone_number_id=%s status=%s",
                short_value(obj.phone_number_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_numero_desregistrar_erro | acao=bloquear_delete phone_number_id=%s erro=%s",
                short_value(obj.phone_number_id),
                exc,
            )
            self.message_user(
                request,
                (
                    "Erro inesperado ao remover registro do número "
                    f"na Meta. Unidade mantida no banco: {exc}"
                ),
                level=messages.ERROR,
            )
            return False

    def _marcar_meta_sucesso(
        self,
        request,
        acao,
        phone_number_id,
    ):
        request._unidade_meta_sucesso = {
            "acao": acao,
            "phone_number_id": str(phone_number_id),
        }

    @staticmethod
    def _meta_sucesso_nesta_requisicao(request):
        return bool(
            getattr(
                request,
                "_unidade_meta_sucesso",
                None,
            )
        )

    def _marcar_meta_desregistrada_na_requisicao(
        self,
        request,
        obj,
    ):
        ids = getattr(
            request,
            "_unidades_meta_desregistradas",
            set(),
        )
        ids.add(obj.id_unidade)
        request._unidades_meta_desregistradas = ids

    def _meta_desregistrada_nesta_requisicao(
        self,
        request,
        obj,
    ):
        ids = getattr(
            request,
            "_unidades_meta_desregistradas",
            set(),
        )
        return obj.id_unidade in ids

    def _marcar_cache_validado_na_requisicao(
        self,
        request,
        obj,
    ):
        ids = getattr(
            request,
            "_unidades_cache_validadas",
            set(),
        )
        ids.add(obj.id_unidade)
        request._unidades_cache_validadas = ids

    def _cache_validado_nesta_requisicao(
        self,
        request,
        obj,
    ):
        ids = getattr(
            request,
            "_unidades_cache_validadas",
            set(),
        )
        return obj.id_unidade in ids

    def _validar_cache_unidades_form(
        self,
        form,
        request,
        meta_validada,
    ):
        if self._validar_cache_unidades_antes_de_alterar(
            request,
            "salvar",
            meta_validada=meta_validada,
        ):
            return

        form.add_error(
            None,
            self._mensagem_cache_unidades_falhou(
                meta_validada
            ),
        )

    def _validar_cache_unidades_antes_de_alterar(
        self,
        request,
        acao,
        meta_validada=False,
    ):
        try:
            validar_cache_unidades_disponivel_ou_erro()
            logger.info(
                "cache_unidades_preflight_admin_ok | acao=%s",
                acao,
            )
            return True

        except CacheUnidadesIndisponivel as exc:
            logger.error(
                "cache_unidades_preflight_admin_falhou | acao=%s erro=%s",
                acao,
                exc,
            )

            if request is not None:
                self.message_user(
                    request,
                    self._mensagem_cache_unidades_falhou(
                        meta_validada
                    ),
                    level=messages.ERROR,
                )

            return False

    def _responder_falha_banco(
        self,
        request,
        object_id,
        exc,
    ):
        logger.exception(
            "admin_unidade_banco_falhou | acao=rollback_sem_compensacao object_id=%s meta_ok=%s erro=%s",
            object_id,
            self._meta_sucesso_nesta_requisicao(request),
            exc,
        )
        self.message_user(
            request,
            self._mensagem_falha_banco(request),
            level=messages.ERROR,
        )
        return HttpResponseRedirect(request.path)

    def _responder_falha_banco_delete(
        self,
        request,
        object_id,
        exc,
    ):
        logger.exception(
            "admin_unidade_banco_delete_falhou | acao=rollback_sem_compensacao object_id=%s meta_ok=%s erro=%s",
            object_id,
            self._meta_sucesso_nesta_requisicao(request),
            exc,
        )
        self.message_user(
            request,
            self._mensagem_falha_banco(request),
            level=messages.ERROR,
        )
        return HttpResponseRedirect(
            reverse(
                "admin:webhook_unidade_change",
                args=[object_id],
            )
        )

    def _mensagem_falha_banco(self, request):
        if self._meta_sucesso_nesta_requisicao(request):
            return (
                "A Meta concluiu a operação com sucesso, mas o banco "
                "falhou. A alteração da Meta foi mantida; banco e "
                "cache local não foram confirmados. Faça uma "
                "conferência manual."
            )

        return (
            "O banco falhou e nenhuma alteração local foi "
            "confirmada. Nenhuma operação Meta foi concluída nesta "
            "requisição."
        )

    def _mensagem_falha_redis(self, request):
        if self._meta_sucesso_nesta_requisicao(request):
            return (
                "A Meta concluiu a operação com sucesso, mas o Redis "
                "falhou. A alteração da Meta foi mantida; nenhuma "
                "alteração foi confirmada no banco ou no cache. Faça "
                "uma conferência manual."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteração foi confirmada no banco."
        )

    @staticmethod
    def _mensagem_cache_unidades_falhou(meta_validada):
        if meta_validada:
            return (
                "A Meta concluiu a operação com sucesso, mas o Redis "
                "falhou. A alteração da Meta foi mantida e a unidade "
                "não foi salva no banco. Faça uma conferência manual."
            )

        return (
            "O Redis falhou ao atualizar o cache de unidades. "
            "Nenhuma alteração foi feita no banco."
        )

    @staticmethod
    def _falha_cache_originada_no_banco(exc):
        causa = exc.__cause__

        while causa is not None:
            if isinstance(causa, DatabaseError):
                return True

            causa = causa.__cause__

        return False

    @staticmethod
    def _meta_resposta_sucesso(status, resposta):
        if status not in (200, 204):
            return False

        if (
            isinstance(resposta, dict)
            and resposta.get("success") is False
        ):
            return False

        return True


@admin.register(Cliente)
class ClienteAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

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


@admin.register(Dependente)
class DependenteAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

    list_display = (
        "id_dependente",
        "id_cliente",
        "nome_dependente",
        "telefone_dependente",
        "email_dependente",
    )

    search_fields = (
        "nome_dependente",
        "telefone_dependente",
        "email_dependente",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
    )

    ordering = ("id_dependente",)
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente"
        )


@admin.register(Etapa)
class EtapaAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

    list_display = (
        "id_etapa",
        "nome_etapa",
    )

    search_fields = ("nome_etapa",)
    ordering = ("id_etapa",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(Conversa)
class ConversaAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

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
                (
                    obj.id_cliente.nome
                    or obj.id_cliente.waid_telefone
                ),
            )

        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
            return (
                obj.id_cliente.nome
                or obj.id_cliente.waid_telefone
            )

    cliente_link.short_description = "Cliente"


@admin.register(FilaMensagens)
class FilaMensagensAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

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

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa"
        )

    def status_colorido(self, obj):
        cores = {
            "sent": "green",
            "failed": "red",
            "pending": "#555",
            "processing": "orange",
        }
        cor = cores.get(obj.status, "#000")
        return format_html(
            '<b style="color:{};">{}</b>',
            cor,
            obj.status,
        )

    status_colorido.short_description = "Status"

    def erro_resumido(self, obj):
        if not obj.last_error:
            return "-"

        texto = obj.last_error[:60]

        return format_html(
            '<span title="{}">{}</span>',
            obj.last_error,
            texto + (
                "..."
                if len(obj.last_error) > 60
                else ""
            ),
        )

    erro_resumido.short_description = "Erro"


@admin.register(HistoricoMensagens)
class HistoricoMensagensAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

    list_display = (
        "id_mensagem",
        "quem_enviou",
        "tipo_mensagem",
        "status_envio",
        "id_conversa",
        "id_etapa",
        "id_mensagem_fila",
        "id_hash_cliente_origem",
        "cliente_telefone",
        "received_data_hora",
    )

    search_fields = (
        "cliente_telefone",
        "id_hash_msg",
        "id_hash_cliente_origem",
        "id_mensagem_fila__id_mensagem",
    )

    list_filter = (
        "quem_enviou",
        "status_envio",
        "id_etapa",
        "tipo_mensagem",
    )

    ordering = ("-received_data_hora",)
    date_hierarchy = "received_data_hora"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related(
            "id_conversa",
            "id_etapa",
            "id_mensagem_fila",
        )


@admin.register(RespostasDesafios)
class RespostasDesafiosAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

    list_display = (
        "id_resposta_desafio",
        "id_conversa",
        "id_etapa",
        "resposta",
        "id_historico_mensagem_cliente",
        "criado_em",
    )

    search_fields = ("resposta",)
    list_filter = ("id_etapa",)
    ordering = ("-criado_em",)
    date_hierarchy = "criado_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa",
            "id_etapa",
        )


@admin.register(WebhookFloodEvento)
class WebhookFloodEventoAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

    list_display = (
        "id_evento",
        "wa_id_cliente",
        "phone_id_unidade",
        "id_hash_msg",
        "received_at",
    )

    search_fields = (
        "wa_id_cliente",
        "phone_id_unidade",
        "id_hash_msg",
    )

    list_filter = ("phone_id_unidade",)
    ordering = ("-received_at",)
    date_hierarchy = "received_at"
    list_per_page = 50
    empty_value_display = "-"


@admin.register(CacheControle)
class CacheControleAdmin(
    SomenteVisualizacaoAdminMixin,
    admin.ModelAdmin,
):

    list_display = (
        "nome",
        "versao",
        "atualizado_em",
    )

    search_fields = ("nome",)
    ordering = ("nome",)
    list_per_page = 50
    empty_value_display = "-"


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

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def get_readonly_fields(self, request, obj=None):
        return [field.name for field in self.model._meta.fields]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_cliente",
            "id_unidade",
        )

    def delete_view(
        self,
        request,
        object_id,
        extra_context=None,
    ):
        if request.method == "POST":
            obj = self.get_object(request, object_id)

            if obj and not self._desbloquear_meta_antes_de_excluir(
                request,
                obj,
            ):
                return HttpResponseRedirect(
                    reverse(
                        "admin:webhook_clientebloqueadometa_change",
                        args=[object_id],
                    )
                )

        return super().delete_view(
            request,
            object_id,
            extra_context,
        )

    def delete_model(self, request, obj):
        logger.warning(
            "admin_bloqueio_meta_excluido | acao=excluir_registro usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
            request.user,
            short_value(obj.wa_id_cliente),
            short_value(obj.phone_id_unidade),
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        logger.warning(
            "admin_bloqueio_meta_exclusao_massa_bloqueada | acao=manter_registros usuario=%s total=%s",
            request.user,
            queryset.count(),
        )
        self.message_user(
            request,
            (
                "Exclusão em massa desativada. Desbloqueie um "
                "cliente por unidade de cada vez."
            ),
            level=messages.ERROR,
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
                (
                    obj.id_cliente.nome
                    or obj.id_cliente.waid_telefone
                ),
            )

        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
            return (
                obj.id_cliente.nome
                or obj.id_cliente.waid_telefone
            )

    cliente_link.short_description = "Cliente"

    def _desbloquear_meta_antes_de_excluir(
        self,
        request,
        obj,
    ):
        try:
            desbloquear_usuario_meta(
                obj.wa_id_cliente,
                obj.phone_id_unidade,
            )

            logger.warning(
                "admin_cliente_desbloqueado_meta | acao=desbloquear_meta_antes_excluir usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
            )

            self.message_user(
                request,
                (
                    f"Cliente {obj.wa_id_cliente} desbloqueado na "
                    "Meta. Registro removido do banco."
                ),
                level=messages.SUCCESS,
            )
            return True

        except Exception as exc:
            logger.exception(
                "admin_desbloqueio_meta_falhou | acao=manter_registro usuario=%s wa_id_cliente=%s phone_id_unidade=%s erro=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
                exc,
            )
            self.message_user(
                request,
                (
                    "Falha ao desbloquear na Meta. "
                    f"Registro mantido no banco: {exc}"
                ),
                level=messages.ERROR,
            )
            return False
```

### O que permanece igual

- criar unidade continua Meta-first;
- excluir unidade continua Meta-first;
- editar unidade continua sem chamada Meta;
- Redis continua obrigatório para confirmar a alteração local;
- nenhuma operação inversa é enviada à Meta;
- clientes e tabelas operacionais continuam somente leitura;
- desbloqueio de cliente continua Meta-first.

---

## Passo 7 - Atualizar o contrato de exceções do Admin

Arquivo alterado:

```text
tests/unit/test_try_except_contract.py
```

Código completo:

```python
import ast
import inspect
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin as django_admin
from django.urls import NoReverseMatch

from core.cache import cache_unidade
from core.repositories import inserts
from webhook import admin as webhook_admin
from webhook.models import ClienteBloqueadoMeta, Conversa
from workers.worker_flow.response_flow import flow_worker


class CursorComFalha:
    def execute(self, *_args, **_kwargs):
        raise RuntimeError("banco falhou")


class RedisComFalha:
    def get(self, _key):
        raise ConnectionError("redis caiu")


class TryExceptContractTests(unittest.TestCase):
    def test_inserts_nao_capturam_excecao_do_orquestrador(self):
        for funcao in (
            inserts.inserindo_em_cliente_caso_seja_novo,
            inserts.inserindo_em_conversa_caso_seja_nova,
        ):
            arvore = ast.parse(
                textwrap.dedent(inspect.getsource(funcao))
            )
            self.assertFalse(
                any(
                    isinstance(no, ast.Try)
                    for no in ast.walk(arvore)
                ),
                msg=funcao.__name__,
            )

    def test_inserts_continuam_propagando_a_mesma_excecao(self):
        with self.assertRaisesRegex(
            RuntimeError,
            "banco falhou",
        ):
            inserts.inserindo_em_cliente_caso_seja_novo(
                "5571999999999",
                CursorComFalha(),
            )

        with self.assertRaisesRegex(
            RuntimeError,
            "banco falhou",
        ):
            inserts.inserindo_em_conversa_caso_seja_nova(
                1,
                1,
                CursorComFalha(),
            )

    def test_cache_invalido_mantem_false_e_sinaliza_erro(self):
        with patch.object(
            cache_unidade.logger,
            "warning",
        ) as warning:
            resultado = cache_unidade._cache_valido(
                RedisComFalha()
            )

        self.assertFalse(resultado)
        warning.assert_called_once()

    def test_links_admin_fazem_fallback_apenas_para_rota_ausente(self):
        cliente = SimpleNamespace(
            id_cliente=10,
            nome="Cliente Teste",
            waid_telefone="5571999999999",
        )
        obj = SimpleNamespace(id_cliente=cliente)

        admins = (
            webhook_admin.ConversaAdmin(
                Conversa,
                django_admin.site,
            ),
            webhook_admin.ClienteBloqueadoMetaAdmin(
                ClienteBloqueadoMeta,
                django_admin.site,
            ),
        )

        for model_admin in admins:
            with self.subTest(
                admin=model_admin.__class__.__name__
            ), patch.object(
                webhook_admin,
                "reverse",
                side_effect=NoReverseMatch("rota ausente"),
            ), patch.object(
                webhook_admin.logger,
                "exception",
            ) as logger_exception:
                self.assertEqual(
                    model_admin.cliente_link(obj),
                    "Cliente Teste",
                )
                logger_exception.assert_called_once()

    def test_links_admin_propagam_erro_inesperado(self):
        cliente = SimpleNamespace(
            id_cliente=10,
            nome="Cliente Teste",
            waid_telefone="5571999999999",
        )
        obj = SimpleNamespace(id_cliente=cliente)
        model_admin = webhook_admin.ConversaAdmin(
            Conversa,
            django_admin.site,
        )

        with patch.object(
            webhook_admin,
            "reverse",
            side_effect=RuntimeError("falha inesperada"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "falha inesperada",
            ):
                model_admin.cliente_link(obj)

    def test_worker_preserva_barreira_generica_e_retry(self):
        source = inspect.getsource(flow_worker.worker_flow)

        self.assertIn("except Exception as erro:", source)
        self.assertIn("handle_erro_generico(", source)
        self.assertIn(
            "reparar_cache_cliente_stale_se_fk_invalida",
            source,
        )
        self.assertIn(
            "reparar_cache_unidade_stale_se_fk_invalida",
            source,
        )

    def test_worker_fecha_conexao_em_finally_independente(self):
        source = inspect.getsource(flow_worker.worker_flow)

        self.assertIn(
            (
                "finally:\n"
                "                    try:\n"
                "                        conn_ciclo.close()"
            ),
            source,
        )
        self.assertIn("conexao_ciclo_close_falhou", source)


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 8 - Testar o aviso sem compensação

Arquivo criado:

```text
tests/unit/test_admin_unidade_falha_local.py
```

Código completo:

```python
import inspect
import unittest
from types import SimpleNamespace

from django.contrib import admin
from django.db import DatabaseError

from webhook.admin import UnidadeAdmin
from webhook.models import Unidade


class AdminUnidadeFalhaLocalTests(unittest.TestCase):
    def setUp(self):
        self.model_admin = UnidadeAdmin(Unidade, admin.site)

    def test_mensagem_banco_sem_meta_nao_declara_sucesso_meta(self):
        request = SimpleNamespace()

        mensagem = self.model_admin._mensagem_falha_banco(
            request
        )

        self.assertIn("banco falhou", mensagem)
        self.assertIn(
            "Nenhuma operação Meta",
            mensagem,
        )

    def test_mensagem_banco_com_meta_preserva_estado_externo(self):
        request = SimpleNamespace(
            _unidade_meta_sucesso={
                "acao": "desregistrar",
                "phone_number_id": "123",
            }
        )

        mensagem = self.model_admin._mensagem_falha_banco(
            request
        )

        self.assertIn(
            "Meta concluiu a operação com sucesso",
            mensagem,
        )
        self.assertIn(
            "alteração da Meta foi mantida",
            mensagem,
        )
        self.assertIn(
            "conferência manual",
            mensagem,
        )

    def test_mensagem_redis_com_meta_nao_promete_compensacao(self):
        request = SimpleNamespace(
            _unidade_meta_sucesso={
                "acao": "registrar",
                "phone_number_id": "123",
            }
        )

        mensagem = self.model_admin._mensagem_falha_redis(
            request
        )

        self.assertIn("Redis falhou", mensagem)
        self.assertIn(
            "alteração da Meta foi mantida",
            mensagem,
        )
        self.assertNotIn("compens", mensagem.lower())

    def test_cache_wrapped_database_error_e_identificado(self):
        erro_banco = DatabaseError("banco caiu")
        erro_cache = RuntimeError("cache não atualizou")
        erro_cache.__cause__ = erro_banco

        self.assertTrue(
            self.model_admin._falha_cache_originada_no_banco(
                erro_cache
            )
        )

    def test_plano_nao_adiciona_compensacao_ao_admin(self):
        source = inspect.getsource(UnidadeAdmin)

        self.assertNotIn("compensar", source)
        self.assertNotIn(
            "sincronizar_edicao_unidade",
            source,
        )


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 9 - Testar a reconciliação somente leitura

Arquivo criado:

```text
tests/unit/test_reconciliacao_unidades_meta.py
```

Código completo:

```python
import inspect
import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from core.integrations.whatsapp.tools import block_report


class ReconciliacaoUnidadesMetaTests(unittest.TestCase):
    def test_compara_banco_com_registros_cloud_api(self):
        unidades_banco = [
            {
                "id_unidade": 1,
                "nome_unidade": "Unidade sincronizada",
                "phone_id_unidade": "phone-1",
            },
            {
                "id_unidade": 2,
                "nome_unidade": "Somente banco",
                "phone_id_unidade": "phone-2",
            },
        ]
        numeros_meta = [
            {
                "phone_id_unidade": "phone-1",
                "display_phone_number": "+55 71 0000-0001",
                "verified_name": "Unidade sincronizada",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "platform_type": "CLOUD_API",
                "name_status": "APPROVED",
                "status": "CONNECTED",
                "registrado_cloud_api": True,
            },
            {
                "phone_id_unidade": "phone-3",
                "display_phone_number": "+55 71 0000-0003",
                "verified_name": "Somente Meta",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "platform_type": "CLOUD_API",
                "name_status": "APPROVED",
                "status": "CONNECTED",
                "registrado_cloud_api": True,
            },
            {
                "phone_id_unidade": "phone-2",
                "display_phone_number": "+55 71 0000-0002",
                "verified_name": "Nao Cloud API",
                "quality_rating": "GREEN",
                "code_verification_status": "VERIFIED",
                "platform_type": "NOT_APPLICABLE",
                "name_status": "APPROVED",
                "status": "DISCONNECTED",
                "registrado_cloud_api": False,
            },
        ]

        with patch.object(
            block_report,
            "_listar_unidades_banco",
            return_value=unidades_banco,
        ), patch.object(
            block_report,
            "_listar_numeros_waba_meta",
            return_value=numeros_meta,
        ), redirect_stdout(io.StringIO()):
            resultado = (
                block_report
                .job_reconciliacao_register__waba_unidades_meta()
            )

        self.assertEqual(
            resultado["sincronizados"],
            ["phone-1"],
        )
        self.assertEqual(
            resultado["somente_banco"],
            ["phone-2"],
        )
        self.assertEqual(
            resultado["somente_meta"],
            ["phone-3"],
        )

    def test_job_nao_possui_operacao_de_escrita_meta(self):
        source = inspect.getsource(
            block_report
            .job_reconciliacao_register__waba_unidades_meta
        )

        self.assertNotIn(
            "registrar_numero_whatsapp",
            source,
        )
        self.assertNotIn(
            "desregistrar_numero_whatsapp",
            source,
        )
        self.assertNotIn("cursor.execute", source)


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 10 - Validação após aplicação

Executar:

```powershell
python -m unittest discover -s tests -t .
python callback/manage.py check
python callback/manage.py check --deploy
```

Testes manuais:

```text
1. Simular falha Meta na criação:
   -> banco e Redis não mudam.

2. Simular Meta com sucesso e banco com falha:
   -> Meta permanece alterada;
   -> banco sofre rollback;
   -> Admin informa o sucesso Meta e a falha local.

3. Simular Meta com sucesso e Redis com falha:
   -> Meta permanece alterada;
   -> banco não é confirmado;
   -> Admin solicita conferência manual.

4. Editar apenas dados da unidade:
   -> Meta não é chamada.

5. Excluir unidade:
   -> Meta desregistra primeiro;
   -> falha posterior não registra novamente o número.

6. Confirmar que Cliente, Conversa, Fila e Histórico continuam
   somente leitura.
```

## Critérios de aceite

```text
- nenhum código de compensação existe;
- edição continua sem sincronizar Meta;
- Redis continua obrigatório para alteração administrativa;
- sucesso Meta seguido de falha local é informado claramente;
- banco continua sofrendo rollback nas falhas locais;
- Meta nunca é revertida automaticamente;
- PIN não permanece fixo no código;
- timeout usado é (30, 35);
- erros inesperados dos links não são mascarados;
- worker permanece intacto;
- webhook muda somente no fallback de miss de unidade;
- todos os testes passam.
```
