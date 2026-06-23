# Plano de Segurança V1

## Estado

Este plano ainda não está aplicado. Ele existe para orientar uma aplicação futura,
curta e controlada, antes do primeiro contrato real ou antes de colocar o projeto
em produção com cliente.

O objetivo é fazer apenas o mínimo profissional da V1:

- remover credenciais reais dos arquivos Python;
- carregar configurações por variáveis de ambiente;
- manter `.env` local fora do Git;
- fornecer `.env.example` sem valores reais;
- evitar que testes dependam de credenciais reais;
- mascarar identificadores sensíveis nos logs;
- documentar o mínimo de LGPD sem alterar banco, fluxo ou regra de negócio.

## Contexto do Produto

A V1 começará com baixa visibilidade, poucos contratos e crescimento gradual.
Mesmo assim, credenciais hardcoded são um risco que vale corrigir cedo, porque
podem vazar por Git, print, backup, zip, deploy ou compartilhamento acidental.

Esta etapa não tenta transformar a V1 em uma arquitetura corporativa pesada. Ela
remove riscos baratos de corrigir agora e deixa temas complexos documentados para
a V2.

## Escopo Permitido

Pode alterar:

- `.gitignore`;
- `requirements.txt`;
- `.env.example`;
- `core/config_env.py`;
- `callback/callback/settings.py`;
- `callback/webhook/views.py`;
- `core/database/connection_aws.py`;
- `core/cache/redis_client.py`;
- `core/integrations/whatsapp/tools/config.py`;
- `core/logging_config.py`;
- `tests/__init__.py`;
- `tests/unit/test_security_config.py`;
- `LGPD_MINIMA_V1.md`.

Não pode alterar:

- fluxo do webhook;
- fluxo do worker;
- regras de fila;
- regras de turno;
- regras de bloqueio;
- regras de anti-flood;
- schema do banco;
- funções SQL;
- etapas de atendimento;
- senders PyWa;
- commits, rollbacks e locks.

## Fora do Escopo da V1

Fica para a V2:

- criptografia de telefone em coluna própria;
- coluna HMAC para busca/indexação;
- AWS KMS;
- AWS Secrets Manager;
- rotação automática de segredos;
- anonimização e retenção automática de dados;
- exportação/remoção automática de dados por solicitação LGPD;
- ElastiCache;
- Load Balancer;
- AWS WAF;
- múltiplos workers;
- deploy sem downtime.

## Pré-requisito Operacional

Antes de aplicar este plano, criar localmente um `.env` a partir de `.env.example`
com os valores reais do ambiente. O `.env` nunca deve entrar no Git.

Depois de remover os segredos do código, rotacionar:

- token da Meta;
- verify token do webhook;
- senha PostgreSQL;
- senha Redis;
- `DJANGO_SECRET_KEY`.

Mesmo que o código novo não exponha mais os valores, os valores antigos já podem
ter passado por histórico de Git, prints ou conversas.

## Passo 1 - `.gitignore`

Código completo proposto:

```gitignore
__pycache__/
*.py[cod]
*$py.class
codex_patch/
dev_cache_inicial.py

.env
.env.*
!.env.example
```

## Passo 2 - `requirements.txt`

Adicionar `python-dotenv`. Código completo proposto:

```text
anyio==4.12.1
asgiref==3.11.1
certifi==2026.1.4
charset-normalizer==3.4.4
Django==6.0.2
h11==0.16.0
httpcore==1.0.9
httpx==0.28.1
idna==3.11
psycopg==3.3.3
psycopg-binary==3.3.3
psycopg2==2.9.11
python-dotenv==1.2.2
pywa==3.8.0
redis==7.4.0
requests==2.32.5
sqlparse==0.5.5
typing_extensions==4.15.0
tzdata==2025.3
urllib3==2.6.3
```

## Passo 3 - `.env.example`

Código completo proposto:

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

WEBHOOK_MAX_BODY_BYTES=262144
```

## Passo 4 - `core/config_env.py`

Arquivo novo. Código completo proposto:

```python
import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env", override=False)


def env_required(name):
    value = os.getenv(name)

    if value is None or not value.strip():
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")

    return value.strip()


def env_optional(name, default=""):
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip()


def env_bool(name, default=False):
    value = os.getenv(name)

    if value is None:
        return default

    normalized = value.strip().lower()

    if normalized in {"1", "true", "yes", "sim"}:
        return True

    if normalized in {"0", "false", "no", "nao"}:
        return False

    raise RuntimeError(f"Valor booleano invalido em {name}: {value}")


def env_int(name, default=None):
    value = os.getenv(name)

    if value is None:
        if default is None:
            raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {name}")
        return default

    try:
        return int(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"Valor inteiro invalido em {name}: {value}") from exc


def env_csv(name, default=None):
    value = os.getenv(name)

    if value is None:
        return list(default or [])

    return [item.strip() for item in value.split(",") if item.strip()]
```

## Passo 5 - `callback/callback/settings.py`

Código completo proposto:

```python
from pathlib import Path

from core.config_env import env_bool, env_csv, env_int, env_optional, env_required


BASE_DIR = Path(__file__).resolve().parent.parent

CSRF_TRUSTED_ORIGINS = env_csv("DJANGO_CSRF_TRUSTED_ORIGINS")

SECRET_KEY = env_required("DJANGO_SECRET_KEY")

DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_csv("DJANGO_ALLOWED_HOSTS", ["localhost", "127.0.0.1"])

WEBHOOK_MAX_BODY_BYTES = env_int("WEBHOOK_MAX_BODY_BYTES", 256 * 1024)

META_APP_SECRET = env_optional("META_APP_SECRET")
META_WEBHOOK_SIGNATURE_REQUIRED = env_bool(
    "META_WEBHOOK_SIGNATURE_REQUIRED",
    False,
)

SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", False)
SESSION_COOKIE_SECURE = env_bool("DJANGO_SESSION_COOKIE_SECURE", False)
CSRF_COOKIE_SECURE = env_bool("DJANGO_CSRF_COOKIE_SECURE", False)
SECURE_HSTS_SECONDS = env_int("DJANGO_SECURE_HSTS_SECONDS", 0)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'webhook',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'callback.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": "%(asctime)s | %(levelname)-7s | %(name)-32s | %(filename)s:%(lineno)d | %(message)s",
            "datefmt": "%H:%M:%S",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },

    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },

    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}

WSGI_APPLICATION = 'callback.wsgi.application'

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_required("DB_NAME"),
        "USER": env_required("DB_USER"),
        "PASSWORD": env_required("DB_PASSWORD"),
        "HOST": env_required("DB_HOST"),
        "PORT": env_int("DB_PORT", 5432),
        "OPTIONS": {
            "options": "-c search_path=chatbot"
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = 'static/'
```

## Passo 6 - `callback/webhook/views.py`

Código completo proposto:

```python
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core.config_env import env_required

from .services.post_flow import responder_post_webhook


logger = logging.getLogger("webhook.request")

VERIFY_TOKEN = env_required("META_WEBHOOK_VERIFY_TOKEN")


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

    if request.method == "POST":
        return responder_post_webhook(request)

    logger.warning("metodo_nao_permitido | metodo=%s", request.method)
    return JsonResponse({"status": "method_not_allowed"}, status=405)
```

## Passo 7 - `core/database/connection_aws.py`

Código completo proposto:

```python
import logging

import psycopg2

from core.config_env import env_int, env_required


logger = logging.getLogger("db.connection")

setup = {
    "host": env_required("DB_HOST"),
    "database": env_required("DB_NAME"),
    "user": env_required("DB_USER"),
    "password": env_required("DB_PASSWORD"),
    "port": env_int("DB_PORT", 5432),
}


def get_conn(application_name=None):
    connect_kwargs = dict(setup)

    if application_name:
        connect_kwargs["application_name"] = application_name

    conn = psycopg2.connect(**connect_kwargs)
    logger.debug(
        "banco_conexao_aberta | acao=connect host=%s database=%s user=%s application_name=%s",
        setup["host"],
        setup["database"],
        setup["user"],
        application_name,
    )
    return conn


# conn.close automaticamente fecha qualquer cursor associado a ela.
# Se fizer conn.close, nao precisa fazer cursor.close.
```

## Passo 8 - `core/cache/redis_client.py`

Código completo proposto:

```python
import logging
import threading
import time

import redis

from core.config_env import env_bool, env_int, env_optional, env_required


logger = logging.getLogger(__name__)

_redis_client = None
_lock = threading.Lock()

REDIS_HOST = env_required("REDIS_HOST")
REDIS_PORT = env_int("REDIS_PORT", 6379)
REDIS_USERNAME = env_optional("REDIS_USERNAME") or None
REDIS_PASSWORD = env_optional("REDIS_PASSWORD") or None
REDIS_SSL = env_bool("REDIS_SSL", False)


def get_redis():
    """
    Singleton thread-safe com inicializacao unica do client Redis.
    """

    global _redis_client

    if _redis_client is None:
        with _lock:
            if _redis_client is None:
                _redis_client = _create_client()

    return _redis_client


def _create_client():
    """
    Cria conexao Redis com validacao inicial.
    """

    try:
        client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            decode_responses=True,
            username=REDIS_USERNAME,
            password=REDIS_PASSWORD,
            ssl=REDIS_SSL,
            socket_connect_timeout=5,
            socket_timeout=5,
            health_check_interval=30,
        )

        client.ping()

        logger.info("redis_conectado | status=ok")
        return client

    except Exception as e:
        logger.error("redis_conectar_falhou | erro=%s", e)
        raise


def get_redis_safe(retries=3, delay=2, validate=True):
    """
    Versao resiliente para worker.
    - tenta reutilizar client
    - valida conexao com ping quando validate=True
    - recria se necessario
    """

    global _redis_client

    for attempt in range(1, retries + 1):
        try:
            client = get_redis()

            if validate:
                client.ping()

            return client

        except Exception as e:
            logger.warning(
                "redis_indisponivel | tentativa=%s total=%s erro=%s",
                attempt,
                retries,
                e,
            )

            _redis_client = None

            time.sleep(delay)

    raise ConnectionError("Redis indisponivel apos multiplas tentativas")


def confirmar_conexao_redis():
    """
    Healthcheck simples para uso externo.
    """

    try:
        client = get_redis_safe()
        resultado = client.ping()
        logger.info("redis_healthcheck_ok | ping=%s", resultado)
        return resultado

    except Exception as e:
        logger.error("redis_healthcheck_falhou | erro=%s", e)
        return False
```

## Passo 9 - `core/integrations/whatsapp/tools/config.py`

Código completo proposto:

```python
from core.config_env import env_optional, env_required


TOKEN_USUARIO_META = env_required("META_ACCESS_TOKEN")
WABA_ID = env_optional("META_WABA_ID")
PHONE_NUMBER_ID_DEV = env_optional("META_PHONE_NUMBER_ID_DEV")


def get_token_usuario_meta():
    return TOKEN_USUARIO_META
```

## Passo 10 - `core/logging_config.py`

Código completo proposto:

```python
import logging
import sys


LOG_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-32s | %(filename)s:%(lineno)d | %(message)s"
DATE_FORMAT = "%H:%M:%S"


def setup_logging(level=logging.INFO):
    root_logger = logging.getLogger()

    if root_logger.handlers:
        return

    logging.basicConfig(
        level=level,
        format=LOG_FORMAT,
        datefmt=DATE_FORMAT,
        stream=sys.stdout,
    )


def short_value(value, head=4, tail=4):
    if value is None:
        return "-"

    text = str(value)

    if text.isdigit() and len(text) >= 8:
        return f"{text[:2]}...{text[-2:]}"

    limit = head + tail + 3

    if len(text) <= limit:
        return text

    return f"{text[:head]}...{text[-tail:]}"
```

## Passo 11 - `tests/__init__.py`

Código completo proposto:

```python
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
CALLBACK_DIR = ROOT_DIR / "callback"

TEST_ENV = {
    "DJANGO_SECRET_KEY": "test-secret-key-not-for-production",
    "DJANGO_DEBUG": "False",
    "DJANGO_ALLOWED_HOSTS": "testserver,localhost",
    "DB_HOST": "localhost",
    "DB_NAME": "test_chatbot",
    "DB_USER": "test_user",
    "DB_PASSWORD": "test_password",
    "DB_PORT": "5432",
    "REDIS_HOST": "localhost",
    "REDIS_PORT": "6379",
    "REDIS_USERNAME": "",
    "REDIS_PASSWORD": "",
    "REDIS_SSL": "False",
    "META_ACCESS_TOKEN": "test-meta-token",
    "META_WEBHOOK_VERIFY_TOKEN": "test-verify-token",
    "META_WEBHOOK_SIGNATURE_REQUIRED": "False",
}

for name, value in TEST_ENV.items():
    os.environ[name] = value

for path in (str(ROOT_DIR), str(CALLBACK_DIR)):
    while path in sys.path:
        sys.path.remove(path)

sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(1, str(CALLBACK_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "callback.callback.settings")

try:
    import django

    django.setup()
except Exception:
    # Alguns testes unitarios puros nao dependem do Django inicializado.
    # Quando um teste precisar do Django, a propria falha apontara a configuracao.
    pass
```

## Passo 12 - `tests/unit/test_security_config.py`

Arquivo novo. Código completo proposto:

```python
import os
import unittest
from unittest.mock import patch

from core.config_env import env_bool, env_csv, env_int, env_required
from core.logging_config import short_value


class SecurityConfigTests(unittest.TestCase):
    def test_short_value_mascara_wa_id_com_13_digitos(self):
        self.assertEqual(short_value("5571999999999"), "55...99")

    def test_short_value_mascara_telefone_com_11_digitos(self):
        self.assertEqual(short_value("71999999999"), "71...99")

    def test_short_value_preserva_identificador_curto(self):
        self.assertEqual(short_value("123"), "123")

    def test_env_required_rejeita_valor_ausente(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SEGREDO_TESTE"):
                env_required("SEGREDO_TESTE")

    def test_helpers_convertem_tipos_sem_ambiguidade(self):
        with patch.dict(
            os.environ,
            {
                "BOOL_TESTE": "sim",
                "INT_TESTE": "42",
                "CSV_TESTE": "um, dois",
            },
            clear=False,
        ):
            self.assertTrue(env_bool("BOOL_TESTE"))
            self.assertEqual(env_int("INT_TESTE"), 42)
            self.assertEqual(env_csv("CSV_TESTE"), ["um", "dois"])


if __name__ == "__main__":
    unittest.main()
```

## Passo 13 - `LGPD_MINIMA_V1.md`

Arquivo novo. Código completo proposto:

```markdown
# LGPD Mínima - V1

## Objetivo

Registrar o tratamento mínimo de dados pessoais na V1 sem alterar banco, fluxo,
worker, webhook ou regras de negócio.

A V1 começará com poucos contratos e baixa visibilidade, mas ainda precisa ter
clareza sobre quais dados trata e por quê.

## Dados Tratados

O sistema pode tratar:

- telefone ou `wa_id` do cliente;
- mensagens recebidas pelo WhatsApp;
- respostas enviadas pelo bot;
- unidade vinculada ao atendimento;
- status de fila;
- status da conversa;
- histórico de mensagens;
- bloqueios temporários por conversa finalizada;
- bloqueios por flood ou abuso;
- logs técnicos com identificadores mascarados.

## Finalidade

Os dados são tratados para:

- atendimento automatizado pelo WhatsApp;
- agendamento ou triagem comercial;
- controle de turno da conversa;
- prevenção contra flood e abuso;
- recuperação de estados intermediários;
- rastreabilidade técnica de falhas;
- suporte operacional via Django Admin.

## Compromissos da V1

Na V1, o projeto deve:

- não coletar dados fora do necessário para o fluxo;
- não registrar credenciais reais em código, README, prints ou logs;
- carregar credenciais por variável de ambiente;
- manter `.env` fora do Git;
- mascarar identificadores numéricos longos nos logs;
- manter tabelas administrativas com permissões restritas;
- preservar as regras de negócio já definidas para fila, turno, bloqueios e
  recuperação.

## Fora do Escopo da V1

Ficam para a V2:

- política formal de retenção;
- anonimização automática;
- exclusão/exportação automatizada por solicitação;
- revisão jurídica completa da base legal;
- política de privacidade pública;
- termos formais com unidades contratantes;
- registro completo de tratamento;
- criptografia de telefone em coluna própria;
- coluna HMAC para busca sem expor telefone original.

## Observação

Este documento não substitui revisão jurídica. Ele apenas registra o mínimo
técnico-operacional para a V1 nascer com mais clareza e menor exposição.
```

## Validação

Depois de aplicar:

```powershell
python -m pip install -r requirements.txt
python -m compileall -q core callback workers main.py
python -m unittest tests.unit.test_security_config
python -m unittest discover -s tests -p "test_*.py"
python callback/manage.py check
git check-ignore -v .env
git ls-files .env
```

Resultado esperado:

- testes passando;
- `manage.py check` sem erro;
- `.env` ignorado pelo Git;
- `.env` não rastreado;
- nenhum valor real novo em arquivo rastreado;
- fluxo do webhook e worker inalterado.

## Critérios de Aceite

- Credenciais reais saíram dos arquivos Python.
- O projeto inicia com `.env` local preenchido.
- Ausência de variável obrigatória falha cedo com nome claro.
- Testes usam somente valores fictícios.
- Identificadores numéricos longos não aparecem completos nos logs.
- Nenhuma regra de negócio foi alterada.
- Nenhum schema de banco foi alterado.
- Temas avançados foram registrados na `_V2`.
