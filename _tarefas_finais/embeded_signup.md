# Plano de implementação: Embedded Signup da Meta

## Estado deste documento

Este plano **não está aplicado**.

Ele deve ser revisado imediatamente antes da implementação porque:

- a API Graph da Meta é versionada;
- o `config_id` só existirá depois da configuração no painel da Meta;
- o domínio HTTPS definitivo ainda será escolhido;
- o chatbot ainda está sendo concluído.

Cada passo abaixo contém o código completo do arquivo criado ou alterado. Ao
aplicar o plano, não copiar trechos cegamente: comparar cada arquivo com o
estado mais recente do projeto.

## Objetivo

Criar uma página Django que permita ao cliente autorizar sua Conta do WhatsApp
Business por meio do Embedded Signup oficial da Meta.

Fluxo desejado:

```text
Administrador cria convite de onboarding
-> sistema gera URL HTTPS exclusiva
-> cliente abre a URL
-> cliente clica em "Conectar WhatsApp"
-> Meta abre o Embedded Signup
-> cliente escolhe empresa, WABA e número
-> Meta devolve code, waba_id e phone_number_id
-> backend troca e valida o code sem expor segredo no navegador
-> backend confirma que a WABA foi compartilhada com a ESL
-> backend confirma que o phone_number_id pertence à WABA
-> backend atribui o usuário de sistema ed à WABA
-> backend inscreve o aplicativo no webhook da WABA
-> onboarding fica concluído e aguardando vínculo com uma unidade
-> administrador cadastra/vincula a unidade
-> fluxo atual do Admin registra o número e reconstrói o cache
```

## Decisões arquiteturais

1. O Embedded Signup será uma aplicação Django própria chamada
   `onboarding_meta`.
2. A funcionalidade ficará desligada por padrão.
3. Nenhum token da Meta será enviado ao navegador ou salvo na tabela de
   onboarding.
4. O convite terá um UUID imprevisível, prazo de validade e uso controlado.
5. O frontend receberá somente `META_APP_ID` e
   `META_EMBEDDED_SIGNUP_CONFIG_ID`.
6. O backend validará a WABA e o número usando a API Graph; não confiará
   apenas nos IDs enviados pelo navegador.
7. A assinatura do webhook será feita por WABA. Uma assinatura cobre todos os
   `phone_number_id` pertencentes àquela WABA.
8. O onboarding não criará automaticamente uma unidade incompleta.
9. `waba_id` e `meta_business_id` serão armazenados na unidade quando o
   administrador concluir o cadastro comercial.
10. O Redis continuará usando `phone_number_id -> id_unidade`; portanto, o
    formato atual do cache não mudará.
11. O worker e o webhook não serão alterados.
12. O número não será desregistrado durante onboarding, cancelamento de
    convite ou falha local.
13. Uma falha depois de a WABA ser assinada ficará registrada para
    reconciliação; não haverá compensação automática destrutiva na Meta.

## Pré-requisitos externos

Antes de ativar a funcionalidade:

1. A verificação empresarial da ESL deve estar aprovada.
2. O aplicativo deve ter acesso avançado às permissões exigidas pela Meta:

```text
business_management
whatsapp_business_management
whatsapp_business_messaging
```

3. Criar uma configuração em:

```text
Aplicativo Meta
-> Casos de uso
-> Conectar no WhatsApp
-> Configurador de cadastro incorporado
```

4. Guardar o `config_id` gerado.
5. Configurar o domínio HTTPS nos domínios permitidos do aplicativo.
6. Configurar os URIs OAuth exigidos pela configuração criada.
7. Confirmar que o usuário de sistema `ed` é administrador da ESL e que seu
   token possui as permissões necessárias.
8. Nunca registrar em Git:

```text
META_ACCESS_TOKEN
META_APP_SECRET
META_PHONE_REGISTRATION_PIN
```

9. Redefinir o `META_APP_SECRET` antes da produção, pois a chave usada durante
   o desenvolvimento apareceu em capturas de tela. Atualizar o `.env` depois
   da rotação e nunca exibir novamente o valor.

---

## Passo 1 - Atualizar `.env.example`

Arquivo completo:

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
PUBLIC_BASE_URL=http://127.0.0.1:8000

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
META_APP_ID=
META_BUSINESS_ID=
META_SYSTEM_USER_ID=
META_EMBEDDED_SIGNUP_CONFIG_ID=
META_EMBEDDED_SIGNUP_ENABLED=False
META_EMBEDDED_SIGNUP_INVITE_TTL_HOURS=72
META_GRAPH_API_VERSION=v25.0
META_PHONE_REGISTRATION_PIN=
META_HTTP_CONNECT_TIMEOUT_SECONDS=30
META_HTTP_READ_TIMEOUT_SECONDS=35

WEBHOOK_MAX_BODY_BYTES=262144
```

Produção:

```dotenv
PUBLIC_BASE_URL=https://app.seudominio.com.br
META_EMBEDDED_SIGNUP_ENABLED=True
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
```

---

## Passo 2 - Completar `requirements.txt`

O projeto já usa `requests`, `redis`, `python-dotenv` e `pywa`, mas essas
dependências não estão registradas no arquivo atual. Revalidar as versões no
momento da aplicação.

Arquivo completo:

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
python-dotenv==1.2.2
pywa==3.8.0
redis==7.4.0
requests==2.32.5
```

---

## Passo 3 - Ampliar a configuração da Meta

Arquivo: `core/integrations/whatsapp/tools/config.py`

Código completo:

```python
import re

from core.config_env import env_int, env_optional, env_required


TOKEN_USUARIO_META = env_required("META_ACCESS_TOKEN")
WABA_ID = env_optional("META_WABA_ID")
PHONE_NUMBER_ID_DEV = env_optional("META_PHONE_NUMBER_ID_DEV")
PHONE_REGISTRATION_PIN = env_optional("META_PHONE_REGISTRATION_PIN")
META_APP_ID = env_optional("META_APP_ID")
META_APP_SECRET = env_optional("META_APP_SECRET")
META_BUSINESS_ID = env_optional("META_BUSINESS_ID")
META_SYSTEM_USER_ID = env_optional("META_SYSTEM_USER_ID")
META_EMBEDDED_SIGNUP_CONFIG_ID = env_optional(
    "META_EMBEDDED_SIGNUP_CONFIG_ID"
)
META_GRAPH_API_VERSION = env_optional(
    "META_GRAPH_API_VERSION",
    "v25.0",
)

META_HTTP_TIMEOUT = (
    env_int("META_HTTP_CONNECT_TIMEOUT_SECONDS", 30),
    env_int("META_HTTP_READ_TIMEOUT_SECONDS", 35),
)


def get_token_usuario_meta():
    return TOKEN_USUARIO_META


def get_waba_id():
    return _obrigatorio(WABA_ID, "META_WABA_ID")


def get_phone_registration_pin():
    return _obrigatorio(
        PHONE_REGISTRATION_PIN,
        "META_PHONE_REGISTRATION_PIN",
    )


def get_meta_app_id():
    return _obrigatorio(META_APP_ID, "META_APP_ID")


def get_meta_app_secret():
    return _obrigatorio(META_APP_SECRET, "META_APP_SECRET")


def get_meta_business_id():
    return _obrigatorio(META_BUSINESS_ID, "META_BUSINESS_ID")


def get_meta_system_user_id():
    return _obrigatorio(
        META_SYSTEM_USER_ID,
        "META_SYSTEM_USER_ID",
    )


def get_meta_embedded_signup_config_id():
    return _obrigatorio(
        META_EMBEDDED_SIGNUP_CONFIG_ID,
        "META_EMBEDDED_SIGNUP_CONFIG_ID",
    )


def get_meta_graph_api_version():
    version = META_GRAPH_API_VERSION.strip()

    if not re.fullmatch(r"v\d+\.\d+", version):
        raise RuntimeError(
            "META_GRAPH_API_VERSION deve seguir o formato vNN.N"
        )

    return version


def get_meta_http_timeout():
    return META_HTTP_TIMEOUT


def _obrigatorio(valor, nome):
    if not valor:
        raise RuntimeError(
            f"Variavel de ambiente obrigatoria ausente: {nome}"
        )

    return valor
```

---

## Passo 4 - Tornar a assinatura de WABA robusta

Arquivo: `core/integrations/whatsapp/tools/ativando_waba_id.py`

Código completo:

```python
import logging

import requests

from core.integrations.whatsapp.tools.config import (
    get_meta_graph_api_version,
    get_meta_http_timeout,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.waba")


def ativar_waba_id(waba_id):
    version = get_meta_graph_api_version()
    url = (
        f"https://graph.facebook.com/{version}/"
        f"{waba_id}/subscribed_apps"
    )

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
        "whatsapp_waba_subscribe_resposta | "
        "acao=subscribe_apps waba_id=%s status=%s",
        short_value(waba_id),
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

Arquivo: `core/integrations/whatsapp/tools/desativa_waba_id.py`

Código completo:

```python
import logging

import requests

from core.integrations.whatsapp.tools.config import (
    get_meta_graph_api_version,
    get_meta_http_timeout,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.waba")


def desativar_waba_id(waba_id):
    version = get_meta_graph_api_version()
    url = (
        f"https://graph.facebook.com/{version}/"
        f"{waba_id}/subscribed_apps"
    )

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    response = requests.delete(
        url,
        headers=headers,
        timeout=get_meta_http_timeout(),
    )

    logger.info(
        "whatsapp_waba_unsubscribe_resposta | "
        "acao=unsubscribe_apps waba_id=%s status=%s",
        short_value(waba_id),
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

---

## Passo 5 - Criar o cliente da API Graph para o Embedded Signup

Arquivo novo:
`core/integrations/whatsapp/tools/embedded_signup.py`

Código completo:

```python
import json
import logging

import requests

from core.integrations.whatsapp.tools.config import (
    get_meta_app_id,
    get_meta_app_secret,
    get_meta_business_id,
    get_meta_graph_api_version,
    get_meta_http_timeout,
    get_meta_system_user_id,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.embedded_signup")


class ErroEmbeddedSignupMeta(RuntimeError):
    pass


class MetaEmbeddedSignupClient:
    def __init__(self):
        self.version = get_meta_graph_api_version()
        self.base_url = (
            f"https://graph.facebook.com/{self.version}"
        )
        self.timeout = get_meta_http_timeout()

    def trocar_codigo_por_token_temporario(self, codigo):
        payload = self._request(
            "GET",
            "/oauth/access_token",
            token=None,
            params={
                "client_id": get_meta_app_id(),
                "client_secret": get_meta_app_secret(),
                "code": codigo,
            },
        )
        token = payload.get("access_token")

        if not token:
            raise ErroEmbeddedSignupMeta(
                "A Meta nao devolveu token ao trocar o codigo"
            )

        return token

    def buscar_waba_autorizada(
        self,
        waba_id,
        token_temporario,
    ):
        return self._request(
            "GET",
            f"/{waba_id}",
            token=token_temporario,
            params={
                "fields": "id,name,owner_business_info",
            },
        )

    def buscar_waba_compartilhada(self, waba_id):
        business_id = get_meta_business_id()
        registros = self._listar_paginado(
            f"/{business_id}/client_whatsapp_business_accounts",
            params={
                "fields": "id,name,owner_business_info",
                "limit": 100,
            },
        )

        for registro in registros:
            if str(registro.get("id")) == str(waba_id):
                return registro

        raise ErroEmbeddedSignupMeta(
            "WABA nao encontrada entre as contas compartilhadas com a ESL"
        )

    def buscar_numero_da_waba(
        self,
        waba_id,
        phone_number_id,
        *,
        token=None,
    ):
        registros = self._listar_paginado(
            f"/{waba_id}/phone_numbers",
            params={
                "fields": (
                    "id,display_phone_number,verified_name,status"
                ),
                "limit": 100,
            },
            token=token or "sistema",
        )

        for registro in registros:
            if str(registro.get("id")) == str(phone_number_id):
                return registro

        raise ErroEmbeddedSignupMeta(
            "phone_number_id nao pertence a WABA informada"
        )

    def atribuir_usuario_sistema_se_necessario(self, waba_id):
        system_user_id = get_meta_system_user_id()
        business_id = get_meta_business_id()
        registros = self._listar_paginado(
            f"/{waba_id}/assigned_users",
            params={
                "business": business_id,
                "fields": "id,name",
                "limit": 100,
            },
        )

        if any(
            str(registro.get("id")) == str(system_user_id)
            for registro in registros
        ):
            logger.info(
                "embedded_signup_usuario_ja_atribuido | "
                "acao=manter waba_id=%s",
                short_value(waba_id),
            )
            return {"success": True, "already_assigned": True}

        return self._request(
            "POST",
            f"/{waba_id}/assigned_users",
            params={
                "user": system_user_id,
                "tasks": json.dumps(["MANAGE"]),
            },
        )

    def _listar_paginado(
        self,
        path,
        params,
        *,
        token="sistema",
    ):
        resultados = []
        parametros = dict(params)

        for _ in range(20):
            payload = self._request(
                "GET",
                path,
                token=token,
                params=parametros,
            )
            resultados.extend(payload.get("data") or [])

            after = (
                payload.get("paging", {})
                .get("cursors", {})
                .get("after")
            )

            if not after:
                break

            parametros["after"] = after

        else:
            raise ErroEmbeddedSignupMeta(
                "Paginacao da Meta excedeu o limite de seguranca"
            )

        return resultados

    def _request(
        self,
        method,
        path,
        *,
        token="sistema",
        params=None,
        json_body=None,
    ):
        headers = {
            "Accept": "application/json",
        }

        if token == "sistema":
            headers["Authorization"] = (
                f"Bearer {get_token_usuario_meta()}"
            )
        elif token:
            headers["Authorization"] = f"Bearer {token}"

        response = requests.request(
            method,
            f"{self.base_url}{path}",
            headers=headers,
            params=params,
            json=json_body,
            timeout=self.timeout,
        )

        try:
            payload = response.json()
        except ValueError:
            payload = {
                "success": response.ok,
                "text": response.text[:500],
            }

        if not response.ok or payload.get("error"):
            erro_meta = payload.get("error") or payload
            logger.error(
                "embedded_signup_meta_falhou | "
                "metodo=%s path=%s status=%s erro=%s",
                method,
                path,
                response.status_code,
                erro_meta,
            )
            raise ErroEmbeddedSignupMeta(
                f"Meta respondeu com status {response.status_code}"
            )

        return payload
```

Regras importantes:

- `codigo`, token temporário, token permanente e segredo nunca entram no log.
- O token temporário existe somente na memória do ciclo.
- A paginação tem limite defensivo.
- IDs enviados pelo frontend só são aceitos depois da conferência na Meta.

---

## Passo 6 - Criar o deploy incremental do onboarding

Arquivo novo:
`core/database/deploy/embedded_signup_script.py`

Código completo:

```python
import logging

from core.database.deploy.transacao_deploy import transacao_deploy


logger = logging.getLogger("db.embedded_signup_setup")


def criar_estrutura_embedded_signup():
    with transacao_deploy(
        "criar_estrutura_embedded_signup",
        logger,
    ) as cursor:
        cursor.execute(
            """
            ALTER TABLE chatbot.unidade
                ADD COLUMN IF NOT EXISTS waba_id VARCHAR(100),
                ADD COLUMN IF NOT EXISTS meta_business_id VARCHAR(100);

            CREATE INDEX IF NOT EXISTS idx_unidade_waba_id
            ON chatbot.unidade (waba_id);

            CREATE TABLE IF NOT EXISTS chatbot.meta_onboarding (
                id_onboarding BIGSERIAL PRIMARY KEY,
                token UUID UNIQUE NOT NULL,
                nome_referencia VARCHAR(200) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pendente',
                waba_id VARCHAR(100),
                phone_number_id VARCHAR(100),
                meta_business_id VARCHAR(100),
                waba_nome VARCHAR(255),
                verified_name VARCHAR(255),
                display_phone_number VARCHAR(50),
                id_unidade INTEGER,
                tentativas INTEGER NOT NULL DEFAULT 0,
                processing_token UUID,
                processing_started_at TIMESTAMPTZ,
                expires_at TIMESTAMPTZ NOT NULL,
                concluido_em TIMESTAMPTZ,
                criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                ultimo_erro TEXT,

                CONSTRAINT ck_meta_onboarding_status
                    CHECK (
                        status IN (
                            'pendente',
                            'processando',
                            'concluido',
                            'falhou',
                            'cancelado'
                        )
                    ),

                CONSTRAINT fk_meta_onboarding_unidade
                    FOREIGN KEY (id_unidade)
                    REFERENCES chatbot.unidade(id_unidade)
                    ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_meta_onboarding_status_expira
            ON chatbot.meta_onboarding (status, expires_at);

            CREATE INDEX IF NOT EXISTS idx_meta_onboarding_waba
            ON chatbot.meta_onboarding (waba_id);

            CREATE INDEX IF NOT EXISTS idx_meta_onboarding_phone
            ON chatbot.meta_onboarding (phone_number_id);

            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_meta_onboarding_phone_concluido
            ON chatbot.meta_onboarding (phone_number_id)
            WHERE (
                status = 'concluido'
                AND phone_number_id IS NOT NULL
            );

            CREATE UNIQUE INDEX IF NOT EXISTS
                uq_meta_onboarding_unidade_vinculada
            ON chatbot.meta_onboarding (id_unidade)
            WHERE id_unidade IS NOT NULL;
            """
        )

    logger.info(
        "banco_setup_ok | acao=criar_estrutura_embedded_signup"
    )
```

Esse deploy é idempotente:

- funciona em banco existente;
- funciona depois de um banco criado do zero;
- não apaga registros;
- não altera o formato do cache;
- interrompe o setup se falhar.

O `ALTER TABLE` deste passo é uma migração futura explícita para bancos que já
existirem quando o Embedded Signup for aplicado. Ele não pertence ao DDL final
de criação da V1 e não deve ser copiado para `bank_script.py`.

---

## Passo 7 - Conectar o deploy incremental ao setup

Arquivo: `core/database/deploy/setup_database.py`

Código completo:

```python
import logging

from core.cache.cache_reset import resetar_cache_redis_dev
from core.database.connection_check import connection_teste_psql
from core.database.deploy.bank_script import (
    configurar_role_banco,
    criar_funcao_dequeue_message,
    criar_funcoes_lock,
    criar_tabelas,
)
from core.database.deploy.cache_control_script import criar_cache_controle
from core.database.deploy.embedded_signup_script import (
    criar_estrutura_embedded_signup,
)
from core.database.deploy.etapa_transicao_script import (
    criar_e_povoar_transicoes_etapa,
)
from core.database.deploy.floodscript import criar_tabelas_bloqueio_flood
from core.database.deploy.povoar_etapas import insere_etapa_once
from core.database.deploy.turno_cliente_script import (
    criar_indices_turno_cliente,
)


logger = logging.getLogger("db.deploy")


def setup_database_aws():
    logger.info("banco_setup_iniciado | acao=configurar_banco")

    connection_teste_psql()
    configurar_role_banco()

    criar_tabelas()
    criar_estrutura_embedded_signup()
    criar_cache_controle()
    criar_tabelas_bloqueio_flood()
    criar_indices_turno_cliente()

    criar_funcao_dequeue_message()
    criar_funcoes_lock()

    insere_etapa_once()
    criar_e_povoar_transicoes_etapa()

    resetar_cache_redis_dev()

    logger.info("banco_setup_finalizado | acao=configurar_banco")


if __name__ == "__main__":
    setup_database_aws()
```

---

## Passo 8 - Atualizar o modelo Django de unidade

Arquivo: `callback/webhook/models.py`

Código completo:

```python
from django.db import models


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=200, blank=True, null=True)
    waid_telefone = models.CharField(unique=True, max_length=50)
    email = models.CharField(
        unique=True,
        max_length=200,
        blank=True,
        null=True,
    )
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome or self.waid_telefone

    class Meta:
        managed = False
        db_table = "cliente"


class Dependente(models.Model):
    id_dependente = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.CASCADE,
        db_column="id_cliente",
        related_name="dependentes",
    )
    id_conversa = models.ForeignKey(
        "Conversa",
        models.CASCADE,
        db_column="id_conversa",
        related_name="dependentes_atendidos",
        blank=True,
        null=True,
    )
    nome_dependente = models.CharField(
        max_length=200,
        blank=True,
        null=True,
    )
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome_dependente or str(self.id_dependente)

    class Meta:
        managed = False
        db_table = "dependente"


class Conversa(models.Model):
    id_conversa = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.DO_NOTHING,
        db_column="id_cliente",
    )
    id_unidade = models.ForeignKey(
        "Unidade",
        models.DO_NOTHING,
        db_column="id_unidade",
    )
    id_etapa_atual = models.ForeignKey(
        "Etapa",
        models.DO_NOTHING,
        db_column="id_etapa_atual",
        blank=True,
        null=True,
    )
    status_ativa = models.BooleanField(default=True)
    status_dependente = models.BooleanField(
        blank=True,
        null=True,
        default=False,
    )
    last_interaction_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    last_message_from = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        choices=[
            ("cliente", "cliente"),
            ("bot", "bot"),
        ],
    )
    followup_stage = models.IntegerField(
        blank=True,
        null=True,
        default=0,
    )
    followup_last_sent_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    lead_no_funil = models.BooleanField(
        blank=True,
        null=True,
        default=False,
    )
    processing = models.BooleanField(
        blank=True,
        null=True,
        default=False,
    )
    processing_started_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    lock_version = models.IntegerField(
        blank=True,
        null=True,
        default=0,
    )
    iniciou_em = models.DateTimeField()
    finalizou_em = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "conversa"


class Etapa(models.Model):
    id_etapa = models.AutoField(primary_key=True)
    nome_etapa = models.CharField(unique=True, max_length=100)
    encerra_automaticamente = models.BooleanField(default=False)
    bloqueio_dias = models.PositiveIntegerField(default=0)
    elegivel_funil = models.BooleanField(default=False)

    class Meta:
        managed = False
        db_table = "etapa"


class FilaMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.SET_NULL,
        db_column="id_conversa",
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
    retry_count = models.IntegerField(
        blank=True,
        null=True,
        default=0,
    )
    next_attempt_at = models.DateTimeField(blank=True, null=True)
    processing_started_at = models.DateTimeField(
        blank=True,
        null=True,
    )
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
        db_table = "fila_mensagens"


class HistoricoMensagens(models.Model):
    id_mensagem = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.DO_NOTHING,
        db_column="id_conversa",
    )
    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column="id_etapa",
        blank=True,
        null=True,
    )
    received_data_hora = models.DateTimeField()
    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(max_length=255)
    id_mensagem_fila = models.ForeignKey(
        FilaMensagens,
        models.SET_NULL,
        db_column="id_mensagem_fila",
        blank=True,
        null=True,
        related_name="historicos_originados",
    )
    id_hash_cliente_origem = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    id_phone_unidade = models.CharField(max_length=100)
    unidade_telefone = models.CharField(max_length=100)
    quem_enviou = models.CharField(
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
        db_table = "historico_mensagens"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "id_mensagem",
                    "received_data_hora",
                ],
                name="uq_historico_mensagens_id_data",
            ),
        ]


class RespostasDesafios(models.Model):
    id_resposta_desafio = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.CASCADE,
        db_column="id_conversa",
        related_name="respostas_desafios",
    )
    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column="id_etapa",
        related_name="respostas_desafios",
    )
    resposta = models.CharField(max_length=10)
    id_historico_mensagem_cliente = models.IntegerField(
        blank=True,
        null=True,
    )
    criado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = "respostas_desafios"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "id_conversa",
                    "id_etapa",
                ],
                name="uq_respostas_desafios_conversa_etapa",
            ),
        ]


class Unidade(models.Model):
    id_unidade = models.AutoField(primary_key=True)
    nome = models.CharField(unique=True, max_length=300)
    cnpj = models.CharField(unique=True, max_length=50)
    email_responsavel = models.CharField(unique=True, max_length=255)
    telefone = models.CharField(unique=True, max_length=20)
    numero_comercial = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    waba_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    meta_business_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    phone_number_id = models.CharField(unique=True, max_length=100)
    link_agendamento = models.CharField(unique=True, max_length=400)
    link_instagram = models.CharField(
        max_length=400,
        blank=True,
        null=True,
    )
    status_pagamento = models.BooleanField(
        blank=True,
        null=True,
        default=True,
    )

    def __str__(self):
        return self.nome

    class Meta:
        managed = False
        db_table = "unidade"


class ClienteBloqueadoMeta(models.Model):
    id_bloqueio = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.SET_NULL,
        db_column="id_cliente",
        blank=True,
        null=True,
        related_name="bloqueios_meta",
    )
    wa_id_cliente = models.CharField(max_length=50)
    id_unidade = models.ForeignKey(
        Unidade,
        models.DO_NOTHING,
        db_column="id_unidade",
        related_name="bloqueios_meta",
    )
    phone_id_unidade = models.CharField(max_length=100)

    def __str__(self):
        return (
            f"{self.wa_id_cliente} / "
            f"{self.phone_id_unidade}"
        )

    class Meta:
        managed = False
        db_table = "cliente_bloqueado_meta"
        constraints = [
            models.UniqueConstraint(
                fields=[
                    "wa_id_cliente",
                    "id_unidade",
                ],
                name="uq_cliente_bloqueado_meta_wa_unidade",
            ),
        ]


class WebhookFloodEvento(models.Model):
    id_evento = models.BigAutoField(primary_key=True)
    wa_id_cliente = models.CharField(max_length=50)
    phone_id_unidade = models.CharField(max_length=100)
    id_hash_msg = models.CharField(unique=True, max_length=255)
    received_at = models.DateTimeField()

    def __str__(self):
        return (
            f"{self.wa_id_cliente} / "
            f"{self.phone_id_unidade}"
        )

    class Meta:
        managed = False
        db_table = "webhook_flood_evento"


class CacheControle(models.Model):
    nome = models.CharField(primary_key=True, max_length=100)
    versao = models.BigIntegerField(default=1)
    atualizado_em = models.DateTimeField()

    def __str__(self):
        return self.nome

    class Meta:
        managed = False
        db_table = "cache_controle"
```

---

## Passo 9 - Atualizar as configurações Django

Arquivo: `callback/callback/settings.py`

Código completo:

```python
from pathlib import Path

from core.config_env import (
    env_bool,
    env_csv,
    env_int,
    env_optional,
    env_required,
)


BASE_DIR = Path(__file__).resolve().parent.parent

CSRF_TRUSTED_ORIGINS = env_csv("DJANGO_CSRF_TRUSTED_ORIGINS")

SECRET_KEY = env_required("DJANGO_SECRET_KEY")

DEBUG = env_bool("DJANGO_DEBUG", False)

ALLOWED_HOSTS = env_csv(
    "DJANGO_ALLOWED_HOSTS",
    ["localhost", "127.0.0.1"],
)

WEBHOOK_MAX_BODY_BYTES = env_int(
    "WEBHOOK_MAX_BODY_BYTES",
    256 * 1024,
)

META_APP_SECRET = env_optional("META_APP_SECRET")
META_WEBHOOK_SIGNATURE_REQUIRED = env_bool(
    "META_WEBHOOK_SIGNATURE_REQUIRED",
    False,
)
META_EMBEDDED_SIGNUP_ENABLED = env_bool(
    "META_EMBEDDED_SIGNUP_ENABLED",
    False,
)
META_EMBEDDED_SIGNUP_INVITE_TTL_HOURS = env_int(
    "META_EMBEDDED_SIGNUP_INVITE_TTL_HOURS",
    72,
)
META_EMBEDDED_SIGNUP_MAX_BODY_BYTES = 16 * 1024

PUBLIC_BASE_URL = env_optional(
    "PUBLIC_BASE_URL",
    "http://127.0.0.1:8000",
).rstrip("/")

SECURE_SSL_REDIRECT = env_bool(
    "DJANGO_SECURE_SSL_REDIRECT",
    False,
)
SESSION_COOKIE_SECURE = env_bool(
    "DJANGO_SESSION_COOKIE_SECURE",
    False,
)
CSRF_COOKIE_SECURE = env_bool(
    "DJANGO_CSRF_COOKIE_SECURE",
    False,
)
SECURE_HSTS_SECONDS = env_int(
    "DJANGO_SECURE_HSTS_SECONDS",
    0,
)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "webhook",
    "onboarding_meta",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "callback.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": (
                "%(asctime)s | %(levelname)-7s | %(name)-32s | "
                "%(filename)s:%(lineno)d | %(message)s"
            ),
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

WSGI_APPLICATION = "callback.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_required("DB_NAME"),
        "USER": env_required("DB_USER"),
        "PASSWORD": env_required("DB_PASSWORD"),
        "HOST": env_required("DB_HOST"),
        "PORT": env_int("DB_PORT", 5432),
        "OPTIONS": {
            "options": "-c search_path=chatbot",
        },
    },
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
```

---

## Passo 10 - Conectar as URLs

Arquivo: `callback/callback/urls.py`

Código completo:

```python
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("", include("webhook.urls")),
    path(
        "integracoes/meta/",
        include("onboarding_meta.urls"),
    ),
    path("admin/", admin.site.urls),
]
```

---

## Passo 11 - Criar o pacote Django

Arquivo novo: `callback/onboarding_meta/__init__.py`

Código completo:

```python
```

O arquivo é intencionalmente vazio.

Arquivo novo: `callback/onboarding_meta/apps.py`

Código completo:

```python
from django.apps import AppConfig


class OnboardingMetaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "onboarding_meta"
    verbose_name = "Onboarding Meta"
```

---

## Passo 12 - Criar o modelo de convite

Arquivo novo: `callback/onboarding_meta/models.py`

Código completo:

```python
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


STATUS_PENDENTE = "pendente"
STATUS_PROCESSANDO = "processando"
STATUS_CONCLUIDO = "concluido"
STATUS_FALHOU = "falhou"
STATUS_CANCELADO = "cancelado"

STATUS_CHOICES = [
    (STATUS_PENDENTE, "Pendente"),
    (STATUS_PROCESSANDO, "Processando"),
    (STATUS_CONCLUIDO, "Concluído"),
    (STATUS_FALHOU, "Falhou"),
    (STATUS_CANCELADO, "Cancelado"),
]


def expiracao_padrao():
    horas = settings.META_EMBEDDED_SIGNUP_INVITE_TTL_HOURS
    return timezone.now() + timedelta(hours=horas)


class MetaOnboarding(models.Model):
    id_onboarding = models.BigAutoField(primary_key=True)
    token = models.UUIDField(
        unique=True,
        default=uuid.uuid4,
        editable=False,
    )
    nome_referencia = models.CharField(max_length=200)
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDENTE,
    )
    waba_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    phone_number_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    meta_business_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )
    waba_nome = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    verified_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
    display_phone_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
    )
    id_unidade = models.ForeignKey(
        "webhook.Unidade",
        models.SET_NULL,
        db_column="id_unidade",
        blank=True,
        null=True,
        related_name="onboarding_meta",
    )
    tentativas = models.PositiveIntegerField(default=0)
    processing_token = models.UUIDField(blank=True, null=True)
    processing_started_at = models.DateTimeField(
        blank=True,
        null=True,
    )
    expires_at = models.DateTimeField(default=expiracao_padrao)
    concluido_em = models.DateTimeField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    ultimo_erro = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.nome_referencia} / {self.status}"

    def clean(self):
        if not self.id_unidade_id:
            return

        unidade = self.id_unidade

        if (
            self.phone_number_id
            and unidade.phone_number_id != self.phone_number_id
        ):
            raise ValidationError(
                "O phone_number_id da unidade não corresponde ao "
                "onboarding."
            )

        if unidade.waba_id and unidade.waba_id != self.waba_id:
            raise ValidationError(
                "O waba_id da unidade não corresponde ao onboarding."
            )

    class Meta:
        managed = False
        db_table = "meta_onboarding"
        verbose_name = "Onboarding da Meta"
        verbose_name_plural = "Onboardings da Meta"
```

---

## Passo 13 - Criar o Admin dos convites

Arquivo novo: `callback/onboarding_meta/admin.py`

Código completo:

```python
from django.conf import settings
from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html

from .models import (
    MetaOnboarding,
    STATUS_CANCELADO,
    STATUS_CONCLUIDO,
    STATUS_FALHOU,
    STATUS_PENDENTE,
)


@admin.register(MetaOnboarding)
class MetaOnboardingAdmin(admin.ModelAdmin):
    list_display = (
        "id_onboarding",
        "nome_referencia",
        "status",
        "waba_nome",
        "display_phone_number",
        "id_unidade",
        "expires_at",
        "link_publico",
    )
    list_filter = ("status",)
    search_fields = (
        "nome_referencia",
        "waba_id",
        "phone_number_id",
        "meta_business_id",
        "waba_nome",
        "verified_name",
        "display_phone_number",
    )
    ordering = ("-criado_em",)
    list_per_page = 50
    actions = ("cancelar_convites",)

    readonly_fields = (
        "token",
        "status",
        "waba_id",
        "phone_number_id",
        "meta_business_id",
        "waba_nome",
        "verified_name",
        "display_phone_number",
        "tentativas",
        "processing_token",
        "processing_started_at",
        "concluido_em",
        "criado_em",
        "atualizado_em",
        "ultimo_erro",
        "link_publico",
    )

    fieldsets = (
        (
            "Convite",
            {
                "fields": (
                    "nome_referencia",
                    "expires_at",
                    "link_publico",
                    "token",
                    "status",
                ),
            },
        ),
        (
            "Ativos confirmados pela Meta",
            {
                "fields": (
                    "waba_id",
                    "phone_number_id",
                    "meta_business_id",
                    "waba_nome",
                    "verified_name",
                    "display_phone_number",
                ),
            },
        ),
        (
            "Vínculo local",
            {
                "fields": ("id_unidade",),
            },
        ),
        (
            "Auditoria",
            {
                "fields": (
                    "tentativas",
                    "processing_token",
                    "processing_started_at",
                    "concluido_em",
                    "criado_em",
                    "atualizado_em",
                    "ultimo_erro",
                ),
            },
        ),
    )

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Cancelar convites selecionados")
    def cancelar_convites(self, request, queryset):
        total = queryset.filter(
            status__in=[
                STATUS_PENDENTE,
                STATUS_FALHOU,
            ]
        ).update(
            status=STATUS_CANCELADO,
            atualizado_em=timezone.now(),
        )

        self.message_user(
            request,
            f"{total} convite(s) cancelado(s).",
            level=messages.SUCCESS,
        )

    def link_publico(self, obj):
        if not obj or not obj.token:
            return "-"

        if not settings.META_EMBEDDED_SIGNUP_ENABLED:
            return "Embedded Signup desativado"

        path = reverse(
            "onboarding_meta:conectar",
            kwargs={"token": obj.token},
        )
        url = f"{settings.PUBLIC_BASE_URL}{path}"

        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>',
            url,
            url,
        )

    link_publico.short_description = "Link do cliente"
```

O Admin não apaga convites porque eles são trilha de auditoria.

---

## Passo 14 - Criar o serviço transacional do onboarding

Arquivo novo:
`callback/onboarding_meta/services/__init__.py`

Código completo:

```python
```

O arquivo é intencionalmente vazio.

Arquivo novo:
`callback/onboarding_meta/services/onboarding.py`

Código completo:

```python
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from core.integrations.whatsapp.tools.ativando_waba_id import (
    ativar_waba_id,
)
from core.integrations.whatsapp.tools.embedded_signup import (
    MetaEmbeddedSignupClient,
)
from core.logging_config import short_value
from onboarding_meta.models import (
    MetaOnboarding,
    STATUS_CANCELADO,
    STATUS_CONCLUIDO,
    STATUS_FALHOU,
    STATUS_PROCESSANDO,
)


logger = logging.getLogger("onboarding_meta.servico")

LIMITE_PROCESSAMENTO = timedelta(minutes=5)


class ConviteOnboardingInvalido(RuntimeError):
    pass


class ConviteOnboardingExpirado(RuntimeError):
    pass


class OnboardingEmProcessamento(RuntimeError):
    pass


@dataclass(frozen=True)
class ResultadoOnboarding:
    id_onboarding: int
    waba_id: str
    phone_number_id: str
    concluido_anteriormente: bool = False


def concluir_onboarding(
    *,
    token,
    codigo,
    waba_id,
    phone_number_id,
):
    convite, concluido, processing_token = _reservar_convite(
        token=token,
        waba_id=waba_id,
        phone_number_id=phone_number_id,
    )

    if concluido:
        return ResultadoOnboarding(
            id_onboarding=convite.id_onboarding,
            waba_id=convite.waba_id,
            phone_number_id=convite.phone_number_id,
            concluido_anteriormente=True,
        )

    try:
        cliente_meta = MetaEmbeddedSignupClient()

        # O token temporário vincula o code aos ativos escolhidos no fluxo.
        # Ele não é persistido. As operações permanentes usam o token da ESL.
        token_temporario = (
            cliente_meta.trocar_codigo_por_token_temporario(codigo)
        )

        waba_autorizada = cliente_meta.buscar_waba_autorizada(
            waba_id,
            token_temporario,
        )
        numero = cliente_meta.buscar_numero_da_waba(
            waba_id,
            phone_number_id,
            token=token_temporario,
        )
        waba_compartilhada = (
            cliente_meta.buscar_waba_compartilhada(waba_id)
        )
        del token_temporario

        cliente_meta.atribuir_usuario_sistema_se_necessario(waba_id)

        status, resposta = ativar_waba_id(waba_id)

        if (
            status < 200
            or status >= 300
            or resposta.get("success") is not True
        ):
            raise RuntimeError(
                "A Meta não confirmou a assinatura do webhook da WABA"
            )

        owner = (
            waba_autorizada.get("owner_business_info")
            or waba_compartilhada.get("owner_business_info")
            or {}
        )

        convite = _concluir_convite(
            id_onboarding=convite.id_onboarding,
            waba_id=str(waba_id),
            phone_number_id=str(phone_number_id),
            meta_business_id=str(owner.get("id") or ""),
            waba_nome=(
                waba_autorizada.get("name")
                or waba_compartilhada.get("name")
            ),
            verified_name=numero.get("verified_name"),
            display_phone_number=numero.get(
                "display_phone_number"
            ),
            processing_token=processing_token,
        )

        logger.info(
            "embedded_signup_concluido | "
            "acao=aguardar_vinculo_unidade id_onboarding=%s "
            "waba_id=%s phone_number_id=%s",
            convite.id_onboarding,
            short_value(waba_id),
            short_value(phone_number_id),
        )

        return ResultadoOnboarding(
            id_onboarding=convite.id_onboarding,
            waba_id=convite.waba_id,
            phone_number_id=convite.phone_number_id,
        )

    except Exception as erro:
        _marcar_falha(
            convite.id_onboarding,
            erro,
            processing_token,
        )
        raise


def _reservar_convite(*, token, waba_id, phone_number_id):
    agora = timezone.now()

    with transaction.atomic():
        convite = (
            MetaOnboarding.objects
            .select_for_update()
            .get(token=token)
        )

        if convite.status == STATUS_CANCELADO:
            raise ConviteOnboardingInvalido(
                "Convite cancelado"
            )

        if convite.expires_at <= agora:
            raise ConviteOnboardingExpirado(
                "Convite expirado"
            )

        if convite.status == STATUS_CONCLUIDO:
            mesmos_ids = (
                str(convite.waba_id) == str(waba_id)
                and str(convite.phone_number_id)
                == str(phone_number_id)
            )

            if not mesmos_ids:
                raise ConviteOnboardingInvalido(
                    "Convite já utilizado por outros ativos"
                )

            return convite, True, None

        processamento_recente = (
            convite.status == STATUS_PROCESSANDO
            and convite.processing_started_at
            and convite.processing_started_at
            > agora - LIMITE_PROCESSAMENTO
        )

        if processamento_recente:
            raise OnboardingEmProcessamento(
                "Onboarding já está sendo processado"
            )

        processing_token = uuid.uuid4()
        convite.status = STATUS_PROCESSANDO
        convite.processing_token = processing_token
        convite.processing_started_at = agora
        convite.tentativas += 1
        convite.ultimo_erro = None
        convite.save(
            update_fields=[
                "status",
                "processing_token",
                "processing_started_at",
                "tentativas",
                "ultimo_erro",
                "atualizado_em",
            ]
        )

        return convite, False, processing_token


def _concluir_convite(
    *,
    id_onboarding,
    waba_id,
    phone_number_id,
    meta_business_id,
    waba_nome,
    verified_name,
    display_phone_number,
    processing_token,
):
    with transaction.atomic():
        convite = (
            MetaOnboarding.objects
            .select_for_update()
            .get(id_onboarding=id_onboarding)
        )

        if (
            convite.status != STATUS_PROCESSANDO
            or convite.processing_token != processing_token
        ):
            raise OnboardingEmProcessamento(
                "O ciclo de onboarding foi substituído por outro"
            )

        convite.status = STATUS_CONCLUIDO
        convite.waba_id = waba_id
        convite.phone_number_id = phone_number_id
        convite.meta_business_id = meta_business_id or None
        convite.waba_nome = waba_nome
        convite.verified_name = verified_name
        convite.display_phone_number = display_phone_number
        convite.processing_token = None
        convite.processing_started_at = None
        convite.concluido_em = timezone.now()
        convite.ultimo_erro = None
        convite.save(
            update_fields=[
                "status",
                "waba_id",
                "phone_number_id",
                "meta_business_id",
                "waba_nome",
                "verified_name",
                "display_phone_number",
                "processing_token",
                "processing_started_at",
                "concluido_em",
                "ultimo_erro",
                "atualizado_em",
            ]
        )
        return convite


def _marcar_falha(
    id_onboarding,
    erro,
    processing_token,
):
    mensagem = str(erro)[:2000]

    with transaction.atomic():
        convite = (
            MetaOnboarding.objects
            .select_for_update()
            .get(id_onboarding=id_onboarding)
        )

        if (
            convite.status == STATUS_CONCLUIDO
            or convite.processing_token != processing_token
        ):
            return

        convite.status = STATUS_FALHOU
        convite.processing_token = None
        convite.processing_started_at = None
        convite.ultimo_erro = mensagem
        convite.save(
            update_fields=[
                "status",
                "processing_token",
                "processing_started_at",
                "ultimo_erro",
                "atualizado_em",
            ]
        )

    logger.exception(
        "embedded_signup_falhou | "
        "acao=permitir_nova_tentativa id_onboarding=%s erro=%s",
        id_onboarding,
        mensagem,
    )
```

### Semântica transacional

```text
Transação curta 1:
-> lock no convite
-> valida uso, expiração e concorrência
-> marca processando
-> commit

Fora de transação:
-> chamadas Meta

Transação curta 2:
-> salva conclusão ou falha
-> commit
```

As chamadas HTTP não acontecem segurando lock no PostgreSQL.

---

## Passo 15 - Criar as views

Arquivo novo: `callback/onboarding_meta/views.py`

Código completo:

```python
import json
import logging
import uuid

from django.conf import settings
from django.http import (
    Http404,
    HttpResponse,
    JsonResponse,
)
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from core.integrations.whatsapp.tools.config import (
    get_meta_app_id,
    get_meta_embedded_signup_config_id,
    get_meta_graph_api_version,
)
from onboarding_meta.models import (
    MetaOnboarding,
    STATUS_CANCELADO,
    STATUS_CONCLUIDO,
)
from onboarding_meta.services.onboarding import (
    ConviteOnboardingExpirado,
    ConviteOnboardingInvalido,
    OnboardingEmProcessamento,
    concluir_onboarding,
)


logger = logging.getLogger("onboarding_meta.views")


@never_cache
@ensure_csrf_cookie
@require_GET
def conectar(request, token):
    _garantir_funcionalidade_ativa()

    try:
        convite = MetaOnboarding.objects.get(token=token)
    except MetaOnboarding.DoesNotExist as erro:
        raise Http404("Convite não encontrado") from erro

    expirado = convite.expires_at <= timezone.now()
    indisponivel = (
        expirado
        or convite.status == STATUS_CANCELADO
    )

    try:
        app_id = get_meta_app_id()
        config_id = get_meta_embedded_signup_config_id()
        graph_version = get_meta_graph_api_version()
    except RuntimeError:
        logger.exception(
            "embedded_signup_configuracao_ausente | "
            "acao=indisponibilizar_pagina"
        )
        return HttpResponse(
            "Integração temporariamente indisponível.",
            status=503,
        )

    response = render(
        request,
        "onboarding_meta/conectar.html",
        {
            "convite": convite,
            "expirado": expirado,
            "indisponivel": indisponivel,
            "concluido": convite.status == STATUS_CONCLUIDO,
            "app_id": app_id,
            "config_id": config_id,
            "graph_version": graph_version,
        },
    )
    response["Cache-Control"] = "no-store, private"
    return response


@never_cache
@require_POST
def concluir(request, token):
    _garantir_funcionalidade_ativa()

    if (
        request.content_type != "application/json"
        or len(request.body)
        > settings.META_EMBEDDED_SIGNUP_MAX_BODY_BYTES
    ):
        return JsonResponse(
            {"ok": False, "erro": "requisição inválida"},
            status=400,
        )

    try:
        payload = json.loads(request.body)
    except (TypeError, ValueError):
        return JsonResponse(
            {"ok": False, "erro": "JSON inválido"},
            status=400,
        )

    codigo = _texto_obrigatorio(payload, "code", 4096)
    waba_id = _id_meta_obrigatorio(payload, "waba_id")
    phone_number_id = _id_meta_obrigatorio(
        payload,
        "phone_number_id",
    )

    if not codigo or not waba_id or not phone_number_id:
        return JsonResponse(
            {"ok": False, "erro": "dados incompletos"},
            status=400,
        )

    try:
        token_uuid = uuid.UUID(str(token))
        resultado = concluir_onboarding(
            token=token_uuid,
            codigo=codigo,
            waba_id=waba_id,
            phone_number_id=phone_number_id,
        )

    except ConviteOnboardingExpirado:
        return JsonResponse(
            {"ok": False, "erro": "convite expirado"},
            status=410,
        )

    except ConviteOnboardingInvalido:
        return JsonResponse(
            {"ok": False, "erro": "convite inválido"},
            status=409,
        )

    except OnboardingEmProcessamento:
        return JsonResponse(
            {
                "ok": False,
                "erro": "integração já está sendo processada",
            },
            status=409,
        )

    except Exception:
        logger.exception(
            "embedded_signup_request_falhou | "
            "acao=orientar_nova_tentativa"
        )
        return JsonResponse(
            {
                "ok": False,
                "erro": (
                    "não foi possível concluir; tente novamente"
                ),
            },
            status=502,
        )

    return JsonResponse(
        {
            "ok": True,
            "id_onboarding": resultado.id_onboarding,
            "concluido_anteriormente": (
                resultado.concluido_anteriormente
            ),
        }
    )


def _garantir_funcionalidade_ativa():
    if not settings.META_EMBEDDED_SIGNUP_ENABLED:
        raise Http404("Funcionalidade desativada")


def _texto_obrigatorio(payload, campo, limite):
    valor = payload.get(campo)

    if not isinstance(valor, str):
        return None

    valor = valor.strip()

    if not valor or len(valor) > limite:
        return None

    return valor


def _id_meta_obrigatorio(payload, campo):
    valor = _texto_obrigatorio(payload, campo, 100)

    if not valor or not valor.isdigit():
        return None

    return valor
```

---

## Passo 16 - Criar as URLs do onboarding

Arquivo novo: `callback/onboarding_meta/urls.py`

Código completo:

```python
from django.urls import path

from . import views


app_name = "onboarding_meta"

urlpatterns = [
    path(
        "conectar/<uuid:token>/",
        views.conectar,
        name="conectar",
    ),
    path(
        "conectar/<uuid:token>/concluir/",
        views.concluir,
        name="concluir",
    ),
]
```

---

## Passo 17 - Criar a página

Arquivo novo:
`callback/onboarding_meta/templates/onboarding_meta/conectar.html`

Código completo:

```html
{% load static %}
<!doctype html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <title>Conectar WhatsApp | ESL Soluções Tec</title>
    <link
        rel="stylesheet"
        href="{% static 'onboarding_meta/conectar.css' %}"
    >
</head>
<body>
    <main
        class="onboarding"
        data-app-id="{{ app_id|escape }}"
        data-config-id="{{ config_id|escape }}"
        data-graph-version="{{ graph_version|escape }}"
        data-concluir-url="{% url 'onboarding_meta:concluir' convite.token %}"
    >
        <header class="onboarding__header">
            <p class="onboarding__empresa">ESL Soluções Tec</p>
            <h1>Conectar WhatsApp</h1>
            <p class="onboarding__referencia">
                {{ convite.nome_referencia }}
            </p>
        </header>

        {% if concluido %}
            <section class="estado estado--sucesso">
                <h2>Autorização concluída</h2>
                <p>Os ativos do WhatsApp foram autorizados com sucesso.</p>
            </section>
        {% elif indisponivel %}
            <section class="estado estado--erro">
                <h2>Convite indisponível</h2>
                <p>Solicite um novo link à ESL Soluções Tec.</p>
            </section>
        {% else %}
            <section class="acao">
                <button
                    id="conectar-whatsapp"
                    class="botao"
                    type="button"
                >
                    Conectar WhatsApp
                </button>
                <p
                    id="status-integracao"
                    class="status"
                    role="status"
                    aria-live="polite"
                ></p>
            </section>
        {% endif %}
    </main>

    {% if not concluido and not indisponivel %}
        <script
            src="{% static 'onboarding_meta/conectar.js' %}"
            defer
        ></script>
    {% endif %}
</body>
</html>
```

---

## Passo 18 - Criar o JavaScript do Embedded Signup

Arquivo novo:
`callback/onboarding_meta/static/onboarding_meta/conectar.js`

Código completo:

```javascript
(function () {
    "use strict";

    const root = document.querySelector(".onboarding");
    const button = document.getElementById("conectar-whatsapp");
    const statusElement = document.getElementById("status-integracao");

    if (!root || !button || !statusElement) {
        return;
    }

    const appId = root.dataset.appId;
    const configId = root.dataset.configId;
    const graphVersion = root.dataset.graphVersion;
    const concluirUrl = root.dataset.concluirUrl;

    let authCode = null;
    let sessionInfo = null;
    let enviando = false;

    window.fbAsyncInit = function () {
        window.FB.init({
            appId: appId,
            cookie: true,
            xfbml: false,
            version: graphVersion,
        });

        button.disabled = false;
    };

    window.addEventListener("message", function (event) {
        const origemValida = (
            event.origin === "https://www.facebook.com"
            || event.origin === "https://web.facebook.com"
        );

        if (!origemValida) {
            return;
        }

        let data;

        try {
            data = (
                typeof event.data === "string"
                    ? JSON.parse(event.data)
                    : event.data
            );
        } catch (error) {
            return;
        }

        if (!data || data.type !== "WA_EMBEDDED_SIGNUP") {
            return;
        }

        if (data.event === "FINISH") {
            sessionInfo = data.data || null;
            tentarConcluir();
            return;
        }

        if (data.event === "CANCEL") {
            atualizarStatus(
                "Integração cancelada. Você pode tentar novamente.",
                true
            );
            button.disabled = false;
            return;
        }

        if (data.event === "ERROR") {
            atualizarStatus(
                "A Meta não conseguiu concluir a integração.",
                true
            );
            button.disabled = false;
        }
    });

    button.addEventListener("click", function () {
        if (!window.FB || enviando) {
            return;
        }

        authCode = null;
        sessionInfo = null;
        button.disabled = true;
        atualizarStatus("Abrindo a Meta...", false);

        window.FB.login(
            function (response) {
                authCode = (
                    response
                    && response.authResponse
                    && response.authResponse.code
                ) || null;

                if (!authCode) {
                    atualizarStatus(
                        "Autorização não concluída.",
                        true
                    );
                    button.disabled = false;
                    return;
                }

                tentarConcluir();
            },
            {
                config_id: configId,
                response_type: "code",
                override_default_response_type: true,
                extras: {
                    setup: {},
                    sessionInfoVersion: "3",
                },
            }
        );
    });

    async function tentarConcluir() {
        if (
            enviando
            || !authCode
            || !sessionInfo
            || !sessionInfo.waba_id
            || !sessionInfo.phone_number_id
        ) {
            return;
        }

        enviando = true;
        atualizarStatus("Concluindo integração...", false);

        try {
            const response = await fetch(concluirUrl, {
                method: "POST",
                credentials: "same-origin",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": obterCookie("csrftoken"),
                },
                body: JSON.stringify({
                    code: authCode,
                    waba_id: String(sessionInfo.waba_id),
                    phone_number_id: String(
                        sessionInfo.phone_number_id
                    ),
                }),
            });

            const payload = await response.json();

            if (!response.ok || !payload.ok) {
                throw new Error(
                    payload.erro || "Falha ao concluir integração"
                );
            }

            atualizarStatus(
                "Autorização concluída com sucesso.",
                false
            );
            button.hidden = true;

        } catch (error) {
            atualizarStatus(
                error.message
                || "Não foi possível concluir. Tente novamente.",
                true
            );
            button.disabled = false;

        } finally {
            enviando = false;
        }
    }

    function atualizarStatus(texto, erro) {
        statusElement.textContent = texto;
        statusElement.classList.toggle("status--erro", erro);
    }

    function obterCookie(nome) {
        const cookies = document.cookie
            ? document.cookie.split(";")
            : [];

        for (const item of cookies) {
            const cookie = item.trim();

            if (cookie.startsWith(nome + "=")) {
                return decodeURIComponent(
                    cookie.substring(nome.length + 1)
                );
            }
        }

        return "";
    }

    const script = document.createElement("script");
    script.src = "https://connect.facebook.net/pt_BR/sdk.js";
    script.async = true;
    script.defer = true;
    script.crossOrigin = "anonymous";
    document.head.appendChild(script);
})();
```

Antes de aplicar, conferir na documentação vigente da Meta:

- versão da API no SDK;
- valor de `sessionInfoVersion`;
- formato final de `data.data`;
- parâmetros exigidos em `extras`.

---

## Passo 19 - Criar o CSS da página

Arquivo novo:
`callback/onboarding_meta/static/onboarding_meta/conectar.css`

Código completo:

```css
:root {
    color-scheme: light;
    font-family: Inter, Arial, sans-serif;
    background: #f4f6f8;
    color: #182026;
}

* {
    box-sizing: border-box;
}

body {
    min-height: 100vh;
    margin: 0;
    display: grid;
    place-items: center;
    padding: 24px;
}

.onboarding {
    width: min(100%, 520px);
    background: #ffffff;
    border: 1px solid #d8dee4;
    border-radius: 8px;
    padding: 32px;
    box-shadow: 0 12px 32px rgb(20 30 40 / 8%);
}

.onboarding__header {
    margin-bottom: 28px;
}

.onboarding__empresa {
    margin: 0 0 8px;
    color: #4b5563;
    font-size: 14px;
    font-weight: 700;
}

h1,
h2,
p {
    margin-top: 0;
}

h1 {
    margin-bottom: 12px;
    font-size: 30px;
    line-height: 1.2;
}

h2 {
    font-size: 20px;
}

.onboarding__referencia {
    margin-bottom: 0;
    color: #4b5563;
}

.acao {
    display: grid;
    gap: 16px;
}

.botao {
    min-height: 48px;
    border: 0;
    border-radius: 6px;
    background: #147a4d;
    color: #ffffff;
    cursor: pointer;
    font: inherit;
    font-weight: 700;
}

.botao:hover {
    background: #0e633e;
}

.botao:disabled {
    cursor: wait;
    opacity: 0.65;
}

.status {
    min-height: 24px;
    margin: 0;
    color: #245b3f;
}

.status--erro,
.estado--erro {
    color: #a32626;
}

.estado--sucesso {
    color: #245b3f;
}

@media (max-width: 560px) {
    body {
        padding: 16px;
    }

    .onboarding {
        padding: 24px;
    }
}
```

---

## Passo 20 - Testar o cliente da Meta

Arquivo novo:
`tests/unit/test_embedded_signup_meta.py`

Código completo:

```python
import unittest
from unittest.mock import Mock, patch

from core.integrations.whatsapp.tools import embedded_signup


class MetaEmbeddedSignupClientTests(unittest.TestCase):
    def setUp(self):
        self.patches = [
            patch.object(
                embedded_signup,
                "get_meta_graph_api_version",
                return_value="v25.0",
            ),
            patch.object(
                embedded_signup,
                "get_meta_http_timeout",
                return_value=(30, 35),
            ),
            patch.object(
                embedded_signup,
                "get_token_usuario_meta",
                return_value="token-sistema",
            ),
            patch.object(
                embedded_signup,
                "get_meta_business_id",
                return_value="business-1",
            ),
            patch.object(
                embedded_signup,
                "get_meta_system_user_id",
                return_value="user-1",
            ),
        ]

        for patcher in self.patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.client = embedded_signup.MetaEmbeddedSignupClient()

    def test_confirma_waba_compartilhada(self):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "data": [
                {
                    "id": "waba-1",
                    "name": "Cliente",
                }
            ]
        }

        with patch.object(
            embedded_signup.requests,
            "request",
            return_value=response,
        ):
            resultado = self.client.buscar_waba_compartilhada(
                "waba-1"
            )

        self.assertEqual(resultado["name"], "Cliente")

    def test_rejeita_phone_que_nao_pertence_a_waba(self):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "data": [{"id": "phone-outro"}]
        }

        with patch.object(
            embedded_signup.requests,
            "request",
            return_value=response,
        ):
            with self.assertRaises(
                embedded_signup.ErroEmbeddedSignupMeta
            ):
                self.client.buscar_numero_da_waba(
                    "waba-1",
                    "phone-1",
                )

    def test_nao_atribui_usuario_ja_atribuido(self):
        response = Mock(status_code=200, ok=True)
        response.json.return_value = {
            "data": [{"id": "user-1"}]
        }

        with patch.object(
            embedded_signup.requests,
            "request",
            return_value=response,
        ) as request:
            resultado = (
                self.client
                .atribuir_usuario_sistema_se_necessario("waba-1")
            )

        self.assertTrue(resultado["already_assigned"])
        self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
```

---

## Passo 21 - Testar o serviço de conclusão

Arquivo novo:
`tests/unit/test_embedded_signup_service.py`

Código completo:

```python
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from onboarding_meta.services import onboarding


class ConcluirOnboardingTests(unittest.TestCase):
    def test_conclui_sem_persistir_token_temporario(self):
        convite = SimpleNamespace(
            id_onboarding=10,
            waba_id=None,
            phone_number_id=None,
        )
        convite_concluido = SimpleNamespace(
            id_onboarding=10,
            waba_id="waba-1",
            phone_number_id="phone-1",
        )
        client = Mock()
        client.trocar_codigo_por_token_temporario.return_value = (
            "token-temporario"
        )
        client.buscar_waba_autorizada.return_value = {
            "id": "waba-1",
            "name": "Cliente",
            "owner_business_info": {
                "id": "business-cliente",
            },
        }
        client.buscar_waba_compartilhada.return_value = {
            "id": "waba-1",
            "name": "Cliente",
            "owner_business_info": {
                "id": "business-cliente",
            },
        }
        client.buscar_numero_da_waba.return_value = {
            "id": "phone-1",
            "verified_name": "Cliente",
            "display_phone_number": "+55 75 99999-9999",
        }

        with patch.object(
            onboarding,
            "_reservar_convite",
            return_value=(
                convite,
                False,
                "processing-token",
            ),
        ), patch.object(
            onboarding,
            "MetaEmbeddedSignupClient",
            return_value=client,
        ), patch.object(
            onboarding,
            "ativar_waba_id",
            return_value=(200, {"success": True}),
        ), patch.object(
            onboarding,
            "_concluir_convite",
            return_value=convite_concluido,
        ) as concluir:
            resultado = onboarding.concluir_onboarding(
                token="token-convite",
                codigo="codigo-unico",
                waba_id="waba-1",
                phone_number_id="phone-1",
            )

        client.buscar_waba_autorizada.assert_called_once_with(
            "waba-1",
            "token-temporario",
        )
        client.buscar_numero_da_waba.assert_called_once_with(
            "waba-1",
            "phone-1",
            token="token-temporario",
        )
        client.atribuir_usuario_sistema_se_necessario.assert_called_once_with(
            "waba-1"
        )
        concluir.assert_called_once()
        self.assertEqual(resultado.waba_id, "waba-1")
        self.assertEqual(resultado.phone_number_id, "phone-1")

    def test_retorna_resultado_idempotente(self):
        convite = SimpleNamespace(
            id_onboarding=10,
            waba_id="waba-1",
            phone_number_id="phone-1",
        )

        with patch.object(
            onboarding,
            "_reservar_convite",
            return_value=(convite, True, None),
        ), patch.object(
            onboarding,
            "MetaEmbeddedSignupClient",
        ) as client:
            resultado = onboarding.concluir_onboarding(
                token="token-convite",
                codigo="codigo-nao-reutilizado",
                waba_id="waba-1",
                phone_number_id="phone-1",
            )

        client.assert_not_called()
        self.assertTrue(resultado.concluido_anteriormente)


if __name__ == "__main__":
    unittest.main()
```

Esses testes precisarão rodar com `callback` no `PYTHONPATH`, como já ocorre
ao executar pelo ambiente Django do projeto.

---

## Passo 22 - Testes obrigatórios antes de ativar

Executar:

```powershell
python callback/manage.py check
python -m unittest discover -s tests -p "test_*.py"
```

Testar manualmente:

```text
1. Funcionalidade desativada retorna 404.
2. Convite inexistente retorna 404.
3. Convite expirado não abre o fluxo.
4. Convite cancelado não abre o fluxo.
5. Origem postMessage diferente da Meta é ignorada.
6. POST sem CSRF é rejeitado.
7. JSON acima de 16 KiB é rejeitado.
8. waba_id não compartilhado é rejeitado.
9. phone_number_id de outra WABA é rejeitado.
10. Duplo clique não cria dois processamentos.
11. Retry durante processamento recente retorna 409.
12. Processamento abandonado por mais de cinco minutos pode ser retomado.
13. Convite concluído com os mesmos IDs é idempotente.
14. Convite concluído não aceita outros IDs.
15. Token temporário e code não aparecem nos logs.
16. WABA aparece em client_whatsapp_business_accounts.
17. Usuário de sistema ed aparece em assigned_users.
18. Aplicativo aparece em subscribed_apps.
19. Webhook recebe evento do novo phone_number_id.
20. Unidade sem status_pagamento ativo não entra na fila.
21. Unidade ativa entra na fila usando o cache atual.
22. Worker continua resolvendo unidade por phone_number_id.
```

---

## Passo 23 - Operação no Admin depois do onboarding

Depois que o convite ficar `concluido`:

```text
1. Abrir o onboarding no Admin.
2. Conferir waba_id, phone_number_id e empresa proprietária.
3. Criar a unidade no Admin.
4. Copiar waba_id e meta_business_id.
5. Copiar phone_number_id.
6. Preencher dados comerciais, Instagram e agendamento.
7. Salvar.
8. O fluxo atual registra o número na Meta.
9. O fluxo atual incrementa a versão do cache.
10. O fluxo atual reconstrói o Redis.
11. Vincular a unidade criada ao registro de onboarding.
12. Enviar uma mensagem de teste ao número.
```

O onboarding não substitui o cadastro comercial da unidade.

---

## Passo 24 - Regra de cancelamento e inadimplência

### Atraso temporário

```text
status_pagamento = FALSE
-> versão do cache é incrementada
-> Redis é reconstruído
-> webhook ignora novas mensagens da unidade
```

Opcionalmente:

```text
desativar_waba_id(waba_id)
-> Meta deixa de enviar webhooks de toda a WABA
```

Não usar `deregister` por atraso temporário.

### Reativação

```text
ativar_waba_id(waba_id)
-> confirmar success da Meta
-> status_pagamento = TRUE
-> reconstruir cache
```

### Cancelamento definitivo

```text
status_pagamento = FALSE
-> desativar_waba_id(waba_id)
-> cliente remove o acesso da ESL no Meta Business Suite
```

Não desregistrar o número sem solicitação expressa e coordenação de migração.

---

## Passo 25 - Reconciliação obrigatória

Ampliar futuramente o relatório manual existente para comparar:

```text
WABAs concluídas no onboarding
WABAs compartilhadas com a ESL
WABAs com usuário ed atribuído
WABAs com aplicativo inscrito
Unidades locais vinculadas
phone_number_id da unidade
phone_number_id realmente pertencente à WABA
```

O relatório deve detectar:

```text
onboarding concluído sem unidade
unidade sem waba_id
waba_id local sem compartilhamento atual
WABA compartilhada sem usuário ed
WABA compartilhada sem subscribed_apps
phone_number_id local pertencente a outra WABA
unidade ativa com assinatura Meta ausente
unidade inativa ainda assinada
```

Essa reconciliação será manual na V1. Nenhuma correção destrutiva deverá ser
executada automaticamente.

---

## Definition of Done

O Embedded Signup estará pronto somente quando:

- o aplicativo estiver aprovado para as permissões necessárias;
- o domínio HTTPS estiver configurado;
- o fluxo funcionar com uma WABA de teste que não seja a principal;
- a WABA aparecer entre as contas compartilhadas com a ESL;
- o usuário de sistema `ed` estiver atribuído;
- o aplicativo estiver em `subscribed_apps`;
- o webhook receber mensagens e status do novo número;
- a unidade for resolvida corretamente pelo `phone_number_id`;
- os testes de concorrência, repetição e falha passarem;
- nenhum token ou segredo aparecer no navegador, banco ou logs;
- o webhook e o worker continuarem inalterados;
- a funcionalidade puder ser desligada por variável de ambiente.

## Resultado esperado

```text
Um aplicativo Meta
Um webhook
Um token permanente de usuário de sistema
Várias WABAs compartilhadas
Vários phone_number_id
Uma unidade local para cada número atendido
Roteamento pelo phone_number_id já existente
```

## Referências oficiais para a revisão futura

- Embedded Signup:
  <https://www.postman.com/meta/whatsapp-business-platform/documentation/du6gzjv/embedded-signup>
- WABAs compartilhadas:
  <https://www.postman.com/meta/whatsapp-business-platform/request/63s87ze/shared-wabas>
- Assinar uma WABA:
  <https://www.postman.com/meta/whatsapp-business-platform/request/2jov46g/subscribe-to-a-waba>
- Remover a assinatura de uma WABA:
  <https://www.postman.com/meta/whatsapp-business-platform/request/orrmkyr/unsubscribe-from-a-waba>
