# Otimização de Custo - Produção V1 Econômica

## Objetivo

Reduzir custo mensal da primeira produção sem alterar regra de negócio, fluxo do webhook, fluxo do worker, proteção anti-flood, proteção de turno, logs importantes ou lógica do sistema.

A ideia é manter a V1 simples e séria:

- 1 servidor pequeno para Django, worker, Nginx e Redis local.
- RDS PostgreSQL pequeno.
- HTTPS direto no Nginx.
- Sem ElastiCache no começo.
- Sem Load Balancer no começo.
- Sem AWS WAF no começo.
- Backups e alertas de custo ativos.

## Estado atual do projeto

Pelo código atual, o projeto já usa um banco RDS:

```text
chatbotdb.chi8soygomha.sa-east-1.rds.amazonaws.com
```

Então não é obrigatório criar outro RDS agora. O passo correto é:

```text
Manter o RDS existente e revisar se ele está pequeno, Single-AZ, com backup e security group correto.
```

Também foi identificado que o Redis atual está apontando para serviço externo:

```text
redis-14738.crce216.sa-east-1-2.ec2.cloud.redislabs.com
```

Para reduzir custo na V1, a recomendação é trocar isso para Redis local na própria EC2:

```text
127.0.0.1:6379
```

## O que esta otimização não muda

- Não muda webhook.
- Não muda worker.
- Não muda flow_sender.
- Não muda repositories.
- Não muda regras de conversa bloqueada.
- Não muda regras de anti-flood.
- Não muda regra de uma mensagem por turno.
- Não muda locks.
- Não muda commits e rollbacks.
- Não muda estrutura principal do banco.

---

# Parte 1 - Configurações externas

## Passo 1 - Manter e revisar o RDS existente

Você já tem RDS. Então este passo não é criar um novo banco obrigatoriamente.

Configuração recomendada:

```text
Serviço: Amazon RDS PostgreSQL
Região: mesma região da EC2, preferencialmente sa-east-1 se já está assim
Modo: Single-AZ
Classe: pequena, como db.t4g.micro ou equivalente
Backup automático: 7 dias
Public access: No
Storage autoscaling: ligado com limite baixo/controlado
Deletion protection: opcional na V1, recomendado quando tiver cliente real
```

Security Group do RDS:

```text
Entrada TCP 5432:
    origem: Security Group da EC2

Não liberar 5432 para 0.0.0.0/0.
Não deixar o RDS público.
```

Resultado esperado:

```text
EC2 consegue conectar no RDS.
Internet pública não consegue conectar diretamente no RDS.
```

## Passo 2 - Criar uma EC2 pequena para app, worker e Redis local

Configuração recomendada:

```text
Sistema: Ubuntu LTS
Tipo: t3.micro, t4g.micro, t3.small ou t4g.small
Disco: 20 GB a 30 GB
```

Security Group da EC2:

```text
SSH 22:
    origem: somente seu IP

HTTP 80:
    origem: 0.0.0.0/0

HTTPS 443:
    origem: 0.0.0.0/0
```

Não abrir Redis publicamente:

```text
6379:
    não abrir para internet
```

## Passo 3 - Instalar dependências na EC2

No terminal da EC2:

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx redis-server git
```

Ativar Redis local:

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

Testar Redis:

```bash
redis-cli ping
```

Resultado esperado:

```text
PONG
```

## Passo 4 - Subir o projeto na EC2

Exemplo:

```bash
git clone <url-do-repositorio>
cd Chatbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Passo 5 - Configurar variáveis de ambiente no servidor

Criar arquivo de ambiente fora do código versionado.

Exemplo:

```bash
sudo nano /etc/chatbot.env
```

Conteúdo modelo:

```env
DJANGO_SECRET_KEY=trocar_por_secret_forte
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=seudominio.com.br,www.seudominio.com.br
DJANGO_CSRF_TRUSTED_ORIGINS=https://seudominio.com.br,https://www.seudominio.com.br

WEBHOOK_MAX_BODY_BYTES=262144
META_APP_SECRET=app_secret_da_meta
META_WEBHOOK_SIGNATURE_REQUIRED=True

DB_HOST=chatbotdb.chi8soygomha.sa-east-1.rds.amazonaws.com
DB_NAME=db_chatbot
DB_USER=fushi
DB_PASSWORD=senha_do_banco
DB_PORT=5432

REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_USERNAME=
REDIS_PASSWORD=
REDIS_SOCKET_CONNECT_TIMEOUT=5
REDIS_SOCKET_TIMEOUT=5
REDIS_HEALTH_CHECK_INTERVAL=30
```

Importante:

```text
Não commitar esse arquivo.
Não colocar senha real em README.
Não colocar token real no código.
```

## Passo 6 - Configurar Gunicorn como serviço

Exemplo de serviço:

```ini
[Unit]
Description=Chatbot Django Gunicorn
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/Chatbot/callback
EnvironmentFile=/etc/chatbot.env
ExecStart=/home/ubuntu/Chatbot/.venv/bin/gunicorn callback.wsgi:application --bind 127.0.0.1:8000 --workers 2 --timeout 60
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Salvar em:

```text
/etc/systemd/system/chatbot-web.service
```

Ativar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable chatbot-web
sudo systemctl start chatbot-web
sudo systemctl status chatbot-web
```

## Passo 7 - Configurar worker como serviço

Exemplo:

```ini
[Unit]
Description=Chatbot Worker
After=network.target chatbot-web.service

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/Chatbot
EnvironmentFile=/etc/chatbot.env
ExecStart=/home/ubuntu/Chatbot/.venv/bin/python -m workers.worker_flow.flow_main
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Salvar em:

```text
/etc/systemd/system/chatbot-worker.service
```

Ativar:

```bash
sudo systemctl daemon-reload
sudo systemctl enable chatbot-worker
sudo systemctl start chatbot-worker
sudo systemctl status chatbot-worker
```

## Passo 8 - Configurar Nginx + HTTPS

Exemplo Nginx:

```nginx
server {
    listen 80;
    server_name seudominio.com.br www.seudominio.com.br;

    client_max_body_size 256k;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Instalar HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d seudominio.com.br -d www.seudominio.com.br
```

Na Meta, usar:

```text
https://seudominio.com.br/webhook
```

## Passo 9 - Backups

No RDS:

```text
Backup automático: ligado
Retenção: 7 dias na V1
Snapshot manual antes de alterações grandes
```

No servidor:

```text
Código vem do GitHub.
Banco fica no RDS.
Redis local é cache; se perder, o sistema recompõe pelo banco.
```

## Passo 10 - Logs e rotação

Se usar systemd:

```bash
journalctl -u chatbot-web -f
journalctl -u chatbot-worker -f
```

Para limitar logs do journald:

```bash
sudo nano /etc/systemd/journald.conf
```

Sugestão:

```ini
SystemMaxUse=1G
RuntimeMaxUse=256M
MaxRetentionSec=14day
```

Depois:

```bash
sudo systemctl restart systemd-journald
```

## Passo 11 - Alertas de custo AWS

Criar AWS Budget mensal:

```text
Alerta 1: US$ 20
Alerta 2: US$ 35
Alerta 3: US$ 50
```

Isso evita surpresa de custo.

## Passo 12 - O que não usar na V1 para economizar

```text
Não usar ElastiCache agora.
Não usar Load Balancer agora.
Não usar WAF agora.
Não usar CloudFront agora, a menos que tenha motivo real.
Não criar múltiplas EC2 agora.
Não criar múltiplos workers agora.
```

Essas peças ficam para V2 ou para quando houver tráfego/contratos suficientes.

---

# Parte 2 - Ajustes de código necessários para produção econômica

Os passos abaixo não mudam a lógica do sistema. Eles apenas tiram configurações sensíveis/hardcoded do código e permitem apontar para Redis local e RDS por variável de ambiente.

Só aplicar estes passos depois de configurar as variáveis no servidor.

---

## Passo 13 - Atualizar `core/database/connection_aws.py`

Arquivo completo:

```python
import logging
import os

import psycopg2


logger = logging.getLogger("db.connection")


def _env_obrigatoria(nome):
    valor = os.getenv(nome)

    if valor is None or not valor.strip():
        raise RuntimeError(f"Variavel de ambiente obrigatoria ausente: {nome}")

    return valor.strip()


def _montar_setup():
    return {
        "host": _env_obrigatoria("DB_HOST"),
        "database": _env_obrigatoria("DB_NAME"),
        "user": _env_obrigatoria("DB_USER"),
        "password": _env_obrigatoria("DB_PASSWORD"),
        "port": os.getenv("DB_PORT", "5432").strip(),
    }


def get_conn(application_name=None):
    connect_kwargs = _montar_setup()

    if application_name:
        connect_kwargs["application_name"] = application_name

    conn = psycopg2.connect(**connect_kwargs)
    logger.debug(
        "banco_conexao_aberta | acao=connect host=%s database=%s user=%s application_name=%s",
        connect_kwargs["host"],
        connect_kwargs["database"],
        connect_kwargs["user"],
        application_name,
    )
    return conn


# conn.close automaticamente fecha qualquer cursor associado a ela.
# Se fizer conn.close, nao precisa fazer cursor.close.
```

Resultado:

```text
Banco continua sendo RDS.
Senha sai do código.
Ambiente local/producao escolhe o banco por variável de ambiente.
```

---

## Passo 14 - Atualizar `core/database/redis_client.py`

Arquivo completo:

```python
import logging
import os
import threading
import time

import redis


logger = logging.getLogger(__name__)

_redis_client = None
_lock = threading.Lock()


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
    Na V1 economica, o padrao e Redis local na mesma EC2.
    """

    try:
        client = redis.Redis(
            host=os.getenv("REDIS_HOST", "127.0.0.1").strip(),
            port=int(os.getenv("REDIS_PORT", "6379")),
            decode_responses=True,
            username=os.getenv("REDIS_USERNAME") or None,
            password=os.getenv("REDIS_PASSWORD") or None,
            socket_connect_timeout=int(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5")),
            socket_timeout=int(os.getenv("REDIS_SOCKET_TIMEOUT", "5")),
            health_check_interval=int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30")),
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

Resultado:

```text
Redis passa a ser configurável por ambiente.
Na EC2, usa Redis local.
Em dev, também pode usar Redis local ou outro host configurado.
```

---

## Passo 15 - Atualizar `callback/callback/settings.py`

Arquivo completo:

```python
import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(nome, padrao=False):
    valor = os.getenv(nome)

    if valor is None:
        return padrao

    return valor.strip().lower() in {"1", "true", "yes", "sim"}


def _env_lista(nome, padrao=None):
    valor = os.getenv(nome)

    if valor is None:
        return padrao or []

    return [
        item.strip()
        for item in valor.split(",")
        if item.strip()
    ]


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "django-insecure-dev-local")

DEBUG = _env_bool("DJANGO_DEBUG", padrao=True)

ALLOWED_HOSTS = _env_lista("DJANGO_ALLOWED_HOSTS", ["*"])

CSRF_TRUSTED_ORIGINS = _env_lista(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    [
        "https://gladys-tetrarchic-dovie.ngrok-free.dev",
    ],
)

WEBHOOK_MAX_BODY_BYTES = int(os.getenv("WEBHOOK_MAX_BODY_BYTES", 256 * 1024))

META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_WEBHOOK_SIGNATURE_REQUIRED = _env_bool(
    "META_WEBHOOK_SIGNATURE_REQUIRED",
    padrao=False,
)

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
        "NAME": os.getenv("DB_NAME", "db_chatbot"),
        "USER": os.getenv("DB_USER", "fushi"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
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

Resultado:

```text
Settings fica pronto para produção sem segredo hardcoded.
DEBUG pode ser False via ambiente.
ALLOWED_HOSTS e CSRF mudam sem editar código.
Banco usado pelo Django fica sincronizado com o banco usado pelo psycopg2.
```

---

# Parte 3 - Ordem recomendada para aplicar

## Ordem segura

1. Confirmar RDS atual e security groups.
2. Criar EC2.
3. Instalar Redis local, Nginx, Python e Git.
4. Subir projeto na EC2.
5. Criar `/etc/chatbot.env`.
6. Aplicar os passos de código 13, 14 e 15.
7. Rodar testes:

```bash
python -m compileall -q core callback workers main.py
python callback/manage.py check
```

8. Testar conexão com RDS.
9. Testar conexão com Redis local.
10. Rodar setup do banco se for ambiente novo.
11. Subir Gunicorn.
12. Subir worker.
13. Configurar Nginx.
14. Configurar HTTPS.
15. Atualizar callback URL na Meta para:

```text
https://seudominio.com.br/webhook
```

16. Criar alertas de custo na AWS.

## Validações finais

```text
GET /webhook responde verificação da Meta.
POST /webhook aceita payload real da Meta.
Webhook valida assinatura.
Webhook usa Redis local.
Webhook grava fila no RDS.
Worker lê fila no RDS.
Worker acessa Redis local.
Admin acessa banco.
Logs aparecem no systemd.
```

---

# Parte 4 - Estimativa de custo

## V1 econômica

```text
EC2 pequena + Redis local + Nginx + worker: baixo custo
RDS pequeno Single-AZ: principal custo fixo
Sem ElastiCache: economia importante
Sem Load Balancer: economia importante
Sem WAF: economia importante
```

Estimativa mensal aproximada:

```text
US$ 15 a US$ 35/mês
R$ 75 a R$ 180/mês, dependendo do câmbio e da classe escolhida
```

## Margem com unidade pagando R$600/mês

Com 1 unidade:

```text
Receita: R$600/mês
Infra V1 econômica: ~R$75 a R$180/mês
Margem bruta técnica aproximada: R$420 a R$525/mês
```

Com 10 unidades:

```text
Receita: R$6.000/mês
Infra não cresce 10x nesse volume
Margem tende a continuar muito boa
```

---

# Parte 5 - Quando migrar para arquitetura mais cara

Migrar para V2 de infraestrutura quando houver motivo real:

```text
Mais tráfego.
Mais unidades pagando.
Necessidade de alta disponibilidade.
Necessidade de múltiplas EC2.
Necessidade de proteção WAF.
Necessidade de Load Balancer.
Necessidade de Redis gerenciado.
Necessidade de deploy sem downtime.
```

Migrações futuras:

```text
Redis local -> ElastiCache
Nginx direto -> Load Balancer
Sem WAF -> AWS WAF
1 worker -> múltiplos workers controlados
EC2 única -> arquitetura com autoscaling
Logs locais/systemd -> CloudWatch estruturado
```

