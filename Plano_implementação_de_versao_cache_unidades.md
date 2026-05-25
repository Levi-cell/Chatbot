# Relatorio - Plano de Versao do Cache de Unidades

## Objetivo

Implementar uma estrategia de baixo custo para manter o `cache_unidade` sincronizado com o banco mesmo quando o Redis cair e voltar com dados antigos.

Regras da estrategia:

- Webhook e worker continuam usando cache-first.
- Banco continua sendo fallback quando Redis falhar ou cache estiver estruturalmente invalido.
- Uma tabela pequena no banco guarda a versao oficial do cache de unidades.
- Toda criacao, edicao ou exclusao de unidade no Django Admin incrementa essa versao.
- O Redis guarda a versao que carregou.
- Quando Redis volta com versao diferente da versao oficial do banco, o cache de unidades e recarregado.
- A tabela inteira de unidades so e consultada quando houver divergencia de versao ou fallback real.

## Passo 1 - Criar `core/repositories/cache_control.py`

```python
CACHE_UNIDADES_NOME = "unidades"


def criar_tabela_cache_controle_sql(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chatbot.cache_controle (
            nome VARCHAR(100) PRIMARY KEY,
            versao BIGINT NOT NULL DEFAULT 1,
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
    """)


def garantir_linha_cache_unidades(cursor):
    cursor.execute("""
        INSERT INTO chatbot.cache_controle (nome, versao, atualizado_em)
        VALUES (%s, 1, NOW())
        ON CONFLICT (nome) DO NOTHING;
    """, (CACHE_UNIDADES_NOME,))


def buscar_versao_cache_unidades(cursor):
    garantir_linha_cache_unidades(cursor)

    cursor.execute("""
        SELECT versao
        FROM chatbot.cache_controle
        WHERE nome = %s
        LIMIT 1;
    """, (CACHE_UNIDADES_NOME,))

    resultado = cursor.fetchone()
    return int(resultado[0]) if resultado else 1


def incrementar_versao_cache_unidades(cursor):
    cursor.execute("""
        INSERT INTO chatbot.cache_controle (nome, versao, atualizado_em)
        VALUES (%s, 1, NOW())
        ON CONFLICT (nome)
        DO UPDATE SET
            versao = chatbot.cache_controle.versao + 1,
            atualizado_em = NOW()
        RETURNING versao;
    """, (CACHE_UNIDADES_NOME,))

    resultado = cursor.fetchone()
    return int(resultado[0])
```

## Passo 2 - Criar `core/database/cache_control_script.py`

```python
from core.database.connection_aws import get_conn
from core.repositories.cache_control import (
    criar_tabela_cache_controle_sql,
    garantir_linha_cache_unidades,
)


def criar_cache_controle():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        criar_tabela_cache_controle_sql(cursor)
        garantir_linha_cache_unidades(cursor)

        conn.commit()
        print("Controle de cache criado com sucesso!")

    except Exception as erro:
        if conn:
            conn.rollback()
        print("Erro ao criar controle de cache:", erro)

    finally:
        if conn:
            conn.close()
```

## Passo 3 - Alterar `core/cache/cache_unidade.py`

```python
import logging
import threading
import time

from core.database.connection_aws import get_conn
from core.database.redis_client import get_redis_safe
from core.logging_config import short_value
from core.repositories.cache_control import buscar_versao_cache_unidades
from core.repositories.querys import buscar_id_unidade_por_phone_id, pegar_unidades


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


def carregar_unidades_redis_primeira_vez():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()
        return carregar_cache_redis(cursor)

    finally:
        if conn:
            conn.close()


def recarregar_cache_unidades():
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()
        return carregar_cache_redis(cursor)

    except Exception as exc:
        logger.exception("cache_recarregar_falhou | origem=admin erro=%s", exc)
        return None

    finally:
        if conn:
            conn.close()


def carregar_cache_redis(cursor, redis_retries=3, redis_delay=2):
    r = get_redis_safe(retries=redis_retries, delay=redis_delay)
    unidades = _normalizar_unidades(pegar_unidades(cursor))
    versao_banco = buscar_versao_cache_unidades(cursor)
    total = _salvar_cache(r, unidades, versao_banco)

    _marcar_versao_conferida()
    logger.info("cache_atualizado | unidades=%s versao=%s", total, versao_banco)
    return total


def carregar_unidades_cache_webhook(cursor):
    return carregar_cache_redis(cursor)


def obter_id_unidade_redis_ou_plsql(id_phone_unidade, cursor):
    phone_key = _normalizar_phone_number_id(id_phone_unidade)

    if phone_key is None:
        raise UnidadeNaoEncontrada("phone_number_id invalido")

    try:
        r = get_redis_safe(retries=1, delay=0)
        _sincronizar_cache_unidades_por_versao(r, origem="worker", cursor=cursor)

        if _cache_valido(r):
            id_unidade = r.hget(REDIS_KEY, phone_key)

            if _id_unidade_valido(id_unidade):
                return int(id_unidade)

            raise UnidadeNaoEncontrada(f"Unidade nao encontrada no cache ativo: {phone_key}")

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

    id_unidade = buscar_id_unidade_por_phone_id(phone_key, cursor)

    _tentar_recarregar_cache(cursor, origem="worker")

    if not _id_unidade_valido(id_unidade):
        raise UnidadeNaoEncontrada(f"Unidade nao encontrada: {phone_key}")

    return int(id_unidade)


def garantir_cache_unidades_se_necessario(cursor):
    try:
        r = get_redis_safe(retries=1, delay=0)
        _sincronizar_cache_unidades_por_versao(r, origem="manual", cursor=cursor)

        if not _cache_valido(r):
            logger.info("cache_invalido | acao=recarregar origem=manual")
            return carregar_cache_redis(cursor, redis_retries=1, redis_delay=0)

        return None

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning("cache_validacao_falhou | origem=manual erro=%s", exc)
        return None


def unidade_esta_ativa(phone_number_id):
    phone_key = _normalizar_phone_number_id(phone_number_id)

    if phone_key is None:
        return False

    try:
        r = get_redis_safe(retries=1, delay=0)
        _sincronizar_cache_unidades_por_versao(r, origem="webhook")

        if _cache_valido(r):
            return bool(r.hexists(REDIS_KEY, phone_key))

        logger.warning(
            "cache_invalido | acao=fallback_banco origem=webhook phone_number_id=%s",
            short_value(phone_key),
        )

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning(
            "cache_indisponivel | acao=fallback_banco origem=webhook phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )

    return _unidade_esta_ativa_banco_e_repara_cache(phone_key)


def _unidade_esta_ativa_banco_e_repara_cache(phone_key):
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        id_unidade = buscar_id_unidade_por_phone_id(phone_key, cursor)

        _tentar_recarregar_cache(cursor, origem="webhook")

        return _id_unidade_valido(id_unidade)

    except Exception as exc:
        logger.exception(
            "fallback_banco_unidade_falhou | origem=webhook phone_number_id=%s erro=%s",
            short_value(phone_key),
            exc,
        )
        return False

    finally:
        if conn:
            conn.close()


def _sincronizar_cache_unidades_por_versao(r, origem, cursor=None):
    if not _deve_conferir_versao():
        return None

    with _versao_lock:
        if not _deve_conferir_versao():
            return None

        conn = None

        try:
            cursor_uso = cursor

            if cursor_uso is None:
                conn = get_conn()
                cursor_uso = conn.cursor()

            versao_banco = buscar_versao_cache_unidades(cursor_uso)
            versao_redis = _int_ou_none(r.get(CACHE_DB_VERSION_KEY))

            if versao_redis != versao_banco or not _cache_valido(r):
                logger.info(
                    "cache_versao_divergente | origem=%s redis=%s banco=%s acao=recarregar",
                    origem,
                    versao_redis,
                    versao_banco,
                )
                return carregar_cache_redis(cursor_uso, redis_retries=1, redis_delay=0)

            _marcar_versao_conferida()
            return None

        except Exception as exc:
            _marcar_checagem_tentada()
            logger.warning(
                "cache_versao_checar_falhou | origem=%s erro=%s",
                origem,
                exc,
            )
            return None

        finally:
            if conn:
                conn.close()


def _tentar_recarregar_cache(cursor, origem):
    try:
        return carregar_cache_redis(cursor, redis_retries=1, redis_delay=0)

    except Exception as exc:
        _marcar_redis_falhou()
        logger.warning(
            "cache_reparo_falhou | origem=%s erro=%s",
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

        return r.hlen(REDIS_KEY) == total_esperado

    except Exception:
        return False


def _deve_conferir_versao():
    agora = time.monotonic()

    if _redis_unidades_falhou:
        return True

    if _ultima_checagem_versao == 0:
        return True

    return (agora - _ultima_checagem_versao) >= VERSAO_CHECK_INTERVAL_SEGUNDOS


def _marcar_redis_falhou():
    global _redis_unidades_falhou
    _redis_unidades_falhou = True


def _marcar_versao_conferida():
    global _redis_unidades_falhou, _ultima_checagem_versao
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


def _normalizar_unidades(unidades_raw):
    if isinstance(unidades_raw, dict):
        return {
            str(phone_number_id).strip(): int(id_unidade)
            for phone_number_id, id_unidade in unidades_raw.items()
            if phone_number_id and _id_unidade_valido(id_unidade)
        }

    if isinstance(unidades_raw, list):
        unidades = {}

        for unidade in unidades_raw:
            if isinstance(unidade, dict):
                phone_number_id = unidade.get("phone_number_id")
                id_unidade = unidade.get("id_unidade")
            else:
                try:
                    phone_number_id, id_unidade = unidade[0], unidade[1]
                except (TypeError, IndexError):
                    continue

            if phone_number_id and _id_unidade_valido(id_unidade):
                unidades[str(phone_number_id).strip()] = int(id_unidade)

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

## Passo 4 - Alterar `callback/webhook/admin.py`

```python
from django.contrib import admin, messages
from django.db import connection, transaction
from django.utils.html import format_html
from django.urls import reverse
import logging

from core.cache.cache_unidade import recarregar_cache_unidades
from core.integrations.whatsapp.ativando_numero import registrar_numero_whatsapp
from core.repositories.cache_control import incrementar_versao_cache_unidades

from .models import (
    Cliente,
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
                    logger.error(f"Erro ao registrar numero {obj.phone_number_id}: {resposta}")
                    self.message_user(
                        request,
                        f"Erro ao registrar numero no WhatsApp: {resposta}",
                        level=messages.ERROR
                    )
                else:
                    logger.info(f"Numero {obj.phone_number_id} registrado com sucesso")
                    self.message_user(
                        request,
                        "Numero registrado com sucesso no WhatsApp!",
                        level=messages.SUCCESS
                    )

            except Exception as e:
                logger.exception(f"Erro inesperado ao registrar numero {obj.phone_number_id}")
                self.message_user(
                    request,
                    f"Erro inesperado ao registrar numero: {str(e)}",
                    level=messages.ERROR
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

        logger.info("cache_unidades_versao_incrementada | versao=%s", versao)
        transaction.on_commit(recarregar_cache_unidades)

    def link_agendamento_clickable(self, obj):
        if obj.link_agendamento:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_agendamento
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
            "id_etapa_atual"
        )

    def cliente_link(self, obj):
        if not obj.id_cliente:
            return "-"

        try:
            url = reverse(
                "admin:webhook_cliente_change",
                args=[obj.id_cliente.id_cliente]
            )
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.id_cliente.nome or obj.id_cliente.waid_telefone
            )
        except Exception:
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"


@admin.register(FilaMensagens)
class FilaMensagensAdmin(admin.ModelAdmin):

    list_display = (
        "id_mensagem",
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
    )

    list_filter = (
        "status",
        "tipo_mensagem",
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
        return super().get_queryset(request)

    @admin.action(description="Reprocessar mensagens selecionadas")
    def reprocessar(self, request, queryset):
        if queryset.count() > 100:
            self.message_user(
                request,
                "Limite de 100 mensagens por vez.",
                level=messages.ERROR
            )
            return

        queryset.update(status="pending", retry_count=0, last_error=None)
        logger.info(f"{request.user} reprocessou {queryset.count()} mensagens")

    @admin.action(description="Marcar como erro")
    def marcar_erro(self, request, queryset):
        queryset.update(status="failed")
        logger.warning(f"{request.user} marcou {queryset.count()} mensagens como erro")

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
            texto + ("..." if len(obj.last_error) > 60 else "")
        )

    erro_resumido.short_description = "Erro"


@admin.register(HistoricoMensagens)
class HistoricoMensagensAdmin(admin.ModelAdmin):

    list_display = (
        "id_mensagem",
        "tipo_mensagem",
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
```

## Passo 5 - Alterar `core/database/setup_database.py`

```python
from core.database.bank_script import (
    criar_tabelas,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    definir_timezone_role,
    alterar_banco,
    configurar_timeouts_avancados
)
from core.database.cache_control_script import criar_cache_controle
from core.database.connection_test import connection_teste_psql
from core.database.povoar_etapas import insere_etapa_once
from core.cache.cache_conversas_bloqueadas import limpar_cache_conversas_bloqueadas_dev
from core.cache.cache_unidade import recarregar_cache_unidades


def setup_database_aws():
    connection_teste_psql()
    definir_timezone_role()
    criar_tabelas()
    criar_cache_controle()
    alterar_banco()
    criar_funcao_dequeue_message()
    criar_funcoes_lock()
    configurar_timeouts_avancados()
    insere_etapa_once()
    recarregar_cache_unidades()
    # Linha exclusiva para DEV: limpa bloqueios antigos quando o banco for recriado.
    limpar_cache_conversas_bloqueadas_dev()

    print("Banco totalmente configurado")


setup_database_aws()
```

## Fluxo final esperado

```text
Admin altera unidade
=> banco incrementa versao
=> admin tenta recarregar Redis

Redis online
=> cache atualizado na hora

Redis offline
=> versao do banco sobe
=> Redis fica com cache antigo

Redis volta
=> webhook/worker consultam Redis primeiro
=> checagem leve compara versao do banco com versao do Redis
=> se divergente, cache de unidades e recarregado pelo banco
=> Redis volta a refletir as unidades ativas reais
```

## Custo esperado da checagem de versao

Com `VERSAO_CHECK_INTERVAL_SEGUNDOS = 300`, cada processo faz no maximo uma consulta pequena a cada 5 minutos:

```text
12 consultas por hora
288 consultas por dia
8.640 consultas por mes por processo
```

Com webhook e worker separados:

```text
17.280 consultas pequenas por mes
```

Essa consulta e pequena porque le apenas uma linha da tabela `chatbot.cache_controle`. A tabela completa de unidades so e consultada quando a versao diverge, quando o cache esta invalido ou quando ha fallback real.
