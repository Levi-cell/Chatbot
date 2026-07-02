# Plano de implementacao - etapa 4 e idade do aluno

## Objetivo

Concluir a etapa 4 preservando regras de turno, idempotencia, locks, retry e o flow_worker enxuto.

## Regras fechadas

- Midia, financeiro e idade invalida enviam o tratamento correto e permanecem na etapa 4.
- Cliente com menos de 18 anos encerra a conversa sem bloqueio de 30 dias.
- Dependente com menos de 5 anos e excluido e a conversa e encerrada sem bloqueio.
- Cliente ou dependente com 100 anos ou mais recebe o numero comercial e encerra a conversa.
- Idade valida persiste no cliente ou dependente, simula a etapa 5 e aplica 4 + idade_valida -> 5.
- Encerramento e status sent da fila pertencem a mesma transacao final.
- Cliente, fila e historico sao preservados nos encerramentos da etapa 4.
- A simulacao da entrada na etapa 4 e removida das etapas 2 e 3; somente a etapa 5 permanece simulada.

## Regra deste documento

Cada passo abaixo corresponde a exatamente um arquivo criado ou alterado e apresenta seu codigo completo. Os blocos sao a fonte de verdade para a futura aplicacao.

## Passo 1 - core/database/deploy/bank_script.py

**Arquivo completo:** `core/database/deploy/bank_script.py`

```python
import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.deploy")


def criar_funcoes_lock():

    conn = None

    try:

        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute("""

        DROP FUNCTION IF EXISTS chatbot.lock_conversa(INT);
        DROP FUNCTION IF EXISTS chatbot.unlock_conversa(INT);
        DROP FUNCTION IF EXISTS chatbot.unlock_conversa(INT, INT);

        CREATE OR REPLACE FUNCTION chatbot.lock_conversa(p_id_conversa INT)
        RETURNS TABLE (
            lock_ok BOOLEAN,
            lock_version_atual INT
        )
        LANGUAGE plpgsql
        AS $$

        DECLARE
            v_lock_version INT;

        BEGIN

            UPDATE chatbot.conversa c
            SET
                processing = TRUE,
                processing_started_at = NOW(),
                lock_version = COALESCE(c.lock_version, 0) + 1
            WHERE
                c.id_conversa = p_id_conversa
                AND (
                    c.processing = FALSE
                    OR c.processing_started_at < NOW() - INTERVAL '110.0 seconds'
                )
            RETURNING c.lock_version INTO v_lock_version;

            IF v_lock_version IS NULL THEN
                RETURN QUERY SELECT FALSE, NULL::INT;
                RETURN;
            END IF;

            RETURN QUERY SELECT TRUE, v_lock_version;

        END;

        $$;

        """)

        cursor.execute("""

        CREATE OR REPLACE FUNCTION chatbot.unlock_conversa(
            p_id_conversa INT,
            p_lock_version INT
        )
        RETURNS BOOLEAN
        LANGUAGE plpgsql
        AS $$

        DECLARE
            updated_rows INTEGER;

        BEGIN

            UPDATE chatbot.conversa
            SET
                processing = FALSE,
                processing_started_at = NULL
            WHERE id_conversa = p_id_conversa
              AND lock_version = p_lock_version;

            GET DIAGNOSTICS updated_rows = ROW_COUNT;

            RETURN updated_rows = 1;

        END;

        $$;

        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_funcoes_lock")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=criar_funcoes_lock erro=%s", erro)

    finally:
        if conn:
            conn.close()


def criar_funcao_dequeue_message():

    conn = None

    try:

        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute("""

        CREATE OR REPLACE FUNCTION chatbot.dequeue_message()
        RETURNS TABLE (
            id_mensagem INT,
            cliente_telefone VARCHAR,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR,
            id_phone_unidade VARCHAR,
            unidade_telefone VARCHAR,
            received_data_hora TIMESTAMPTZ,
            id_hash_msg VARCHAR,
            retry_count INT
        )
        LANGUAGE plpgsql
        AS $$

        BEGIN

            RETURN QUERY

            WITH next_job AS (

                SELECT f.id_mensagem
                FROM chatbot.fila_mensagens f
                WHERE
                    (
                        f.status = 'pending'
                        AND f.next_attempt_at <= NOW()
                    )
                    OR
                    (
                        f.status = 'processing'
                        AND f.processing_started_at < NOW() - INTERVAL '2 minutes'
                    )
                ORDER BY
                    CASE
                        WHEN f.status = 'pending' THEN f.next_attempt_at
                        WHEN f.status = 'processing' THEN f.processing_started_at
                    END NULLS FIRST,
                    f.id_mensagem
                FOR UPDATE SKIP LOCKED
                LIMIT 1

            )

            UPDATE chatbot.fila_mensagens f
            SET
                status = 'processing',
                retry_count = f.retry_count + 1,
                processing_started_at = NOW()
            FROM next_job
            WHERE f.id_mensagem = next_job.id_mensagem

            RETURNING
                f.id_mensagem,
                f.cliente_telefone,
                f.conteudo_texto,
                f.tipo_mensagem,
                f.id_phone_unidade,
                f.unidade_telefone,
                f.received_data_hora,
                f.id_hash_msg,
                f.retry_count;

        END;

        $$;

        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_funcao_dequeue_message")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=criar_funcao_dequeue_message erro=%s", erro)
    finally:
        if conn:
            conn.close()


def criar_tabelas():

    conn = None
    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute("""

        SET TIME ZONE 'America/Sao_Paulo';

        CREATE SCHEMA IF NOT EXISTS chatbot;

        -- CLIENTE
        CREATE TABLE IF NOT EXISTS chatbot.cliente (
            id_cliente SERIAL PRIMARY KEY,
            nome VARCHAR(200),
            waid_telefone VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(200) UNIQUE,
            idade INTEGER
        );

        -- DEPENDENTE
        CREATE TABLE IF NOT EXISTS chatbot.dependente (
            id_dependente SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_conversa INT,
            nome_dependente VARCHAR(200),
            telefone_dependente VARCHAR(50) UNIQUE,
            email_dependente VARCHAR(200) UNIQUE,
            idade INTEGER,

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_dependente_cliente
        ON chatbot.dependente (id_cliente);

        -- UNIDADE
        CREATE TABLE IF NOT EXISTS chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY,
            nome VARCHAR(300) UNIQUE NOT NULL,
            cnpj VARCHAR(50) UNIQUE NOT NULL,
            email_responsavel VARCHAR(255) UNIQUE NOT NULL,
            telefone VARCHAR(20) UNIQUE NOT NULL,
            numero_comercial VARCHAR(30),
            phone_number_id VARCHAR(100) UNIQUE NOT NULL,
            link_agendamento VARCHAR(400) UNIQUE NOT NULL,
            status_pagamento BOOLEAN DEFAULT TRUE
        );

        -- ETAPA
        CREATE TABLE IF NOT EXISTS chatbot.etapa (
            id_etapa SERIAL PRIMARY KEY,
            nome_etapa VARCHAR(100) UNIQUE NOT NULL
        );

        -- CONVERSA
        CREATE TABLE IF NOT EXISTS chatbot.conversa (
            id_conversa SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_unidade INT NOT NULL,
            id_etapa_atual INT,

            status_ativa BOOLEAN NOT NULL DEFAULT TRUE,
            status_dependente BOOLEAN DEFAULT FALSE,

            last_interaction_at TIMESTAMPTZ,

            last_message_from VARCHAR(10)
                CHECK (last_message_from IN ('cliente','bot')),

            followup_stage INTEGER DEFAULT 0,
            followup_last_sent_at TIMESTAMPTZ NULL,

            lead_no_funil BOOLEAN DEFAULT FALSE,

            processing BOOLEAN DEFAULT FALSE,
            processing_started_at TIMESTAMPTZ NULL,
            lock_version INTEGER DEFAULT 0,

            iniciou_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finalizou_em TIMESTAMPTZ,

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE,

            FOREIGN KEY (id_unidade)
                REFERENCES chatbot.unidade(id_unidade)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa_atual)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_conversa_unica_ativa
        ON chatbot.conversa (id_cliente, id_unidade)
        WHERE status_ativa = TRUE;

        CREATE INDEX IF NOT EXISTS idx_conversa_followup
        ON chatbot.conversa (last_message_from, followup_stage, last_interaction_at);

        CREATE INDEX IF NOT EXISTS idx_conversa_processing
        ON chatbot.conversa(processing, processing_started_at);

        CREATE INDEX IF NOT EXISTS idx_conversa_ultima_inativa
        ON chatbot.conversa (id_cliente, id_unidade, finalizou_em DESC)
        INCLUDE (id_conversa, id_etapa_atual)
        WHERE status_ativa = FALSE;

        -- CAMPOS DA TRANSICAO ENTRE AS ETAPAS 2 E 3.
        -- Os ALTERs mantem o setup idempotente tambem em bancos ja existentes.
        ALTER TABLE chatbot.cliente
        ADD COLUMN IF NOT EXISTS idade INTEGER;

        ALTER TABLE chatbot.unidade
        ADD COLUMN IF NOT EXISTS numero_comercial VARCHAR(30);

        ALTER TABLE chatbot.dependente
        ADD COLUMN IF NOT EXISTS id_conversa INT;

        ALTER TABLE chatbot.dependente
        ADD COLUMN IF NOT EXISTS idade INTEGER;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'dependente_id_conversa_fkey'
                  AND conrelid = 'chatbot.dependente'::regclass
            ) THEN
                ALTER TABLE chatbot.dependente
                ADD CONSTRAINT dependente_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE;
            END IF;
        END
        $$;

        CREATE UNIQUE INDEX IF NOT EXISTS uq_dependente_conversa
        ON chatbot.dependente (id_conversa)
        WHERE id_conversa IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_dependente_conversa
        ON chatbot.dependente (id_conversa);

        -- HISTORICO
        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens (
            id_mensagem SERIAL,
            id_conversa INT NOT NULL,
            id_etapa INT,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) NOT NULL,
            id_mensagem_fila INT,
            id_hash_cliente_origem VARCHAR(255),
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,
            quem_enviou VARCHAR(10) NOT NULL,
            status_envio VARCHAR(20),

            PRIMARY KEY (id_mensagem, received_data_hora),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa)
                ON DELETE SET NULL,

            CONSTRAINT chk_historico_quem_enviou
                CHECK (quem_enviou IN ('cliente', 'bot')),

            CONSTRAINT chk_historico_status_envio
                CHECK (
                    (quem_enviou = 'cliente' AND status_envio IS NULL)
                    OR
                    (
                        quem_enviou = 'bot'
                        AND status_envio IS NOT NULL
                        AND status_envio IN ('pending', 'sent', 'failed')
                    )
                )
        )
        PARTITION BY RANGE (received_data_hora);

        CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens_default
        PARTITION OF chatbot.historico_mensagens
        DEFAULT;

        CREATE INDEX IF NOT EXISTS idx_historico_conversa_data
        ON chatbot.historico_mensagens (
            id_conversa,
            received_data_hora DESC,
            id_mensagem DESC
        );

        CREATE INDEX IF NOT EXISTS idx_historico_cliente_mensagem_fila
        ON chatbot.historico_mensagens (
            id_conversa,
            id_mensagem_fila,
            id_hash_msg,
            received_data_hora DESC,
            id_mensagem DESC
        )
        WHERE quem_enviou = 'cliente'
          AND id_mensagem_fila IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_historico_bot_mensagem_fila
        ON chatbot.historico_mensagens (
            id_conversa,
            id_mensagem_fila,
            id_hash_cliente_origem,
            received_data_hora DESC,
            id_mensagem DESC
        )
        WHERE quem_enviou = 'bot'
          AND id_mensagem_fila IS NOT NULL
          AND id_hash_cliente_origem IS NOT NULL;

        -- RESPOSTAS DO DESAFIO
        CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios (
            id_resposta_desafio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL,
            id_etapa INT NOT NULL,
            resposta VARCHAR(10) NOT NULL,
            id_historico_mensagem_cliente INT NULL,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            FOREIGN KEY (id_etapa)
                REFERENCES chatbot.etapa(id_etapa),

            CONSTRAINT uq_respostas_desafios_conversa_etapa
                UNIQUE (id_conversa, id_etapa)
        );

        -- FILA
        CREATE TABLE IF NOT EXISTS chatbot.fila_mensagens (
            id_mensagem SERIAL PRIMARY KEY,
            id_conversa INT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            retry_count INTEGER DEFAULT 0,
            next_attempt_at TIMESTAMPTZ DEFAULT NOW(),
            processing_started_at TIMESTAMPTZ NULL,
            received_data_hora TIMESTAMPTZ NOT NULL,
            cliente_telefone VARCHAR(100) NOT NULL,
            conteudo_texto TEXT,
            tipo_mensagem VARCHAR(20) NOT NULL,
            id_hash_msg VARCHAR(255) UNIQUE NOT NULL,
            id_phone_unidade VARCHAR(100) NOT NULL,
            unidade_telefone VARCHAR(100) NOT NULL,
            last_error TEXT,

            FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE SET NULL,

            CHECK (status IN ('pending','processing','sent','failed'))
        );

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'fk_historico_mensagem_fila'
                  AND conrelid = 'chatbot.historico_mensagens'::regclass
            ) THEN
                ALTER TABLE chatbot.historico_mensagens
                ADD CONSTRAINT fk_historico_mensagem_fila
                FOREIGN KEY (id_mensagem_fila)
                REFERENCES chatbot.fila_mensagens(id_mensagem)
                ON DELETE SET NULL;
            END IF;
        END $$;

        CREATE INDEX IF NOT EXISTS idx_fila_pending_next_attempt
        ON chatbot.fila_mensagens (next_attempt_at, id_mensagem)
        WHERE status = 'pending';

        CREATE INDEX IF NOT EXISTS idx_fila_processing_timeout
        ON chatbot.fila_mensagens (processing_started_at, id_mensagem)
        WHERE status = 'processing';

        CREATE INDEX IF NOT EXISTS idx_fila_conversa_aberta_data
        ON chatbot.fila_mensagens (id_conversa, received_data_hora, id_mensagem)
        WHERE id_conversa IS NOT NULL
          AND status IN ('pending','processing');

        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=criar_tabelas")

    except Exception as erro:

        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=criar_tabelas erro=%s", erro)

    finally:
        if conn:
            conn.close()


def definir_timezone_role():
    conn = None
    try:

        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute("""
            ALTER ROLE fushi
            SET timezone TO 'America/Sao_Paulo';
        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=definir_timezone_role role=fushi")

    except Exception as e:

        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=definir_timezone_role role=fushi erro=%s", e)

    finally:
        if conn:
            conn.close()


def configurar_timeouts_avancados():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute("""
            ALTER ROLE fushi
            SET idle_in_transaction_session_timeout = '30min';
        """)

        cursor.execute("""
            ALTER ROLE fushi
            SET statement_timeout = '10min';
        """)

        cursor.execute("""
            ALTER ROLE fushi
            SET lock_timeout = '15s';
        """)

        conn.commit()
        logger.info("banco_setup_ok | acao=configurar_timeouts_avancados role=fushi")

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception("banco_setup_erro | acao=configurar_timeouts_avancados erro=%s", erro)

    finally:
        if conn:
            conn.close()
```

## Passo 2 - callback/webhook/models.py

**Arquivo completo:** `callback/webhook/models.py`

```python
from django.db import models


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=200, blank=True, null=True)
    waid_telefone = models.CharField(unique=True, max_length=50)
    email = models.CharField(unique=True, max_length=200, blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome or self.waid_telefone

    class Meta:
        managed = False
        db_table = 'cliente'


class Dependente(models.Model):
    id_dependente = models.AutoField(primary_key=True)
    id_cliente = models.ForeignKey(
        Cliente,
        models.CASCADE,
        db_column='id_cliente',
        related_name='dependentes',
    )
    id_conversa = models.ForeignKey(
        'Conversa',
        models.CASCADE,
        db_column='id_conversa',
        related_name='dependentes_atendidos',
        blank=True,
        null=True,
    )
    nome_dependente = models.CharField(max_length=200, blank=True, null=True)
    telefone_dependente = models.CharField(
        unique=True,
        max_length=50,
        blank=True,
        null=True,
    )
    email_dependente = models.CharField(
        unique=True,
        max_length=200,
        blank=True,
        null=True,
    )
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome_dependente or self.telefone_dependente or str(self.id_dependente)

    class Meta:
        managed = False
        db_table = 'dependente'


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
        db_column='id_conversa'
    )

    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        blank=True,
        null=True
    )

    received_data_hora = models.DateTimeField()

    cliente_telefone = models.CharField(max_length=100)
    conteudo_texto = models.TextField(blank=True, null=True)
    tipo_mensagem = models.CharField(max_length=20)
    id_hash_msg = models.CharField(max_length=255)
    id_mensagem_fila = models.ForeignKey(
        FilaMensagens,
        models.SET_NULL,
        db_column='id_mensagem_fila',
        blank=True,
        null=True,
        related_name='historicos_originados',
    )
    id_hash_cliente_origem = models.CharField(max_length=255, blank=True, null=True)
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
        db_table = 'historico_mensagens'
        constraints = [
            models.UniqueConstraint(
                fields=["id_mensagem", "received_data_hora"],
                name="uq_historico_mensagens_id_data",
            ),
        ]


class RespostasDesafios(models.Model):
    id_resposta_desafio = models.AutoField(primary_key=True)
    id_conversa = models.ForeignKey(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='respostas_desafios',
    )
    id_etapa = models.ForeignKey(
        Etapa,
        models.DO_NOTHING,
        db_column='id_etapa',
        related_name='respostas_desafios',
    )
    resposta = models.CharField(max_length=10)
    id_historico_mensagem_cliente = models.IntegerField(blank=True, null=True)
    criado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'respostas_desafios'
        constraints = [
            models.UniqueConstraint(
                fields=["id_conversa", "id_etapa"],
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
    phone_number_id = models.CharField(unique=True, max_length=100)
    link_agendamento = models.CharField(unique=True, max_length=400)
    status_pagamento = models.BooleanField(blank=True, null=True, default=True)

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
        constraints = [
            models.UniqueConstraint(
                fields=["wa_id_cliente", "id_unidade"],
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
        return f"{self.wa_id_cliente} / {self.phone_id_unidade}"

    class Meta:
        managed = False
        db_table = 'webhook_flood_evento'


class CacheControle(models.Model):
    nome = models.CharField(primary_key=True, max_length=100)
    versao = models.BigIntegerField(default=1)
    atualizado_em = models.DateTimeField()

    def __str__(self):
        return self.nome

    class Meta:
        managed = False
        db_table = 'cache_controle'
```

## Passo 3 - callback/webhook/admin.py

**Arquivo completo:** `callback/webhook/admin.py`

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
from core.integrations.whatsapp.tools.ativando_numero import registrar_numero_whatsapp
from core.integrations.whatsapp.tools.desativando_numero import desregistrar_numero_whatsapp
from core.integrations.whatsapp.tools.usuarios import (
    desbloquear_usuario_meta,
)
from core.logging_config import short_value
from core.repositories.cache_control import incrementar_versao_cache_unidades

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
        "numero_comercial",
        "email_responsavel",
        "link_agendamento_clickable",
        "status_pagamento",
    )

    search_fields = (
        "nome",
        "cnpj",
        "telefone",
        "numero_comercial",
        "email_responsavel",
        "link_agendamento",
    )

    list_filter = ("status_pagamento",)
    ordering = ("nome",)

    list_per_page = 50
    empty_value_display = "-"

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
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
        base_form = super().get_form(request, obj, change=change, **kwargs)
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

                phone_number_id = self.cleaned_data.get("phone_number_id")

                if not phone_number_id:
                    return

                if not model_admin._registrar_meta_antes_de_salvar(
                    request,
                    phone_number_id,
                ):
                    self.add_error(
                        "phone_number_id",
                        "A Meta falhou ao registrar este numero. Unidade nao foi salva.",
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
        if not self._meta_desregistrada_nesta_requisicao(request, obj):
            if not self._desregistrar_meta_antes_de_excluir(request, obj):
                return

        if not self._cache_validado_nesta_requisicao(request, obj):
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
            "Exclusao em massa de unidade nao permitida. Exclua uma unidade por vez.",
            level=messages.ERROR,
        )

    def delete_view(self, request, object_id, extra_context=None):
        try:
            if request.method == "POST":
                obj = self.get_object(request, object_id)

                if obj and not self._desregistrar_meta_antes_de_excluir(request, obj):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj and not self._validar_cache_unidades_antes_de_alterar(
                    request,
                    "excluir",
                    meta_validada=True,
                ):
                    return HttpResponseRedirect(
                        reverse(
                            "admin:webhook_unidade_change",
                            args=[object_id],
                        )
                    )

                if obj:
                    self._marcar_meta_desregistrada_na_requisicao(request, obj)
                    self._marcar_cache_validado_na_requisicao(request, obj)

            return super().delete_view(request, object_id, extra_context)

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
            total_unidades = recarregar_cache_unidades_ou_erro(cursor)

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

    def _registrar_meta_antes_de_salvar(self, request, phone_number_id):
        try:
            status, resposta = registrar_numero_whatsapp(phone_number_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_registrar_falhou | acao=bloquear_save phone_number_id=%s status=%s resposta=%s",
                    short_value(phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    f"Erro ao registrar numero no WhatsApp. Unidade nao foi salva: {resposta}",
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
                f"Erro inesperado ao registrar numero. Unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _desregistrar_meta_antes_de_excluir(self, request, obj):
        try:
            status, resposta = desregistrar_numero_whatsapp(obj.phone_number_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_numero_desregistrar_falhou | acao=bloquear_delete phone_number_id=%s status=%s resposta=%s",
                    short_value(obj.phone_number_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    f"Erro ao remover registro do numero na Meta. Unidade mantida no banco: {resposta}",
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
                f"Erro inesperado ao remover registro do numero na Meta. Unidade mantida no banco: {exc}",
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

    def _marcar_meta_desregistrada_na_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_meta_desregistradas", set())
        ids.add(obj.id_unidade)
        request._unidades_meta_desregistradas = ids

    def _meta_desregistrada_nesta_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_meta_desregistradas", set())
        return obj.id_unidade in ids

    def _marcar_cache_validado_na_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_cache_validadas", set())
        ids.add(obj.id_unidade)
        request._unidades_cache_validadas = ids

    def _cache_validado_nesta_requisicao(self, request, obj):
        ids = getattr(request, "_unidades_cache_validadas", set())
        return obj.id_unidade in ids

    def _validar_cache_unidades_form(self, form, request, meta_validada):
        if self._validar_cache_unidades_antes_de_alterar(
            request,
            "salvar",
            meta_validada=meta_validada,
        ):
            return

        form.add_error(
            None,
            self._mensagem_cache_unidades_falhou(meta_validada),
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
                    self._mensagem_cache_unidades_falhou(meta_validada),
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

        if isinstance(resposta, dict) and resposta.get("success") is False:
            return False

        return True


@admin.register(Cliente)
class ClienteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_cliente",
        "nome",
        "waid_telefone",
        "email",
        "idade",
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
class DependenteAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_dependente",
        "id_cliente",
        "id_conversa",
        "nome_dependente",
        "telefone_dependente",
        "email_dependente",
        "idade",
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
            "id_cliente",
            "id_conversa",
        )


@admin.register(Etapa)
class EtapaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_etapa",
        "nome_etapa",
    )

    search_fields = ("nome_etapa",)
    ordering = ("id_etapa",)

    list_per_page = 50
    empty_value_display = "-"


@admin.register(Conversa)
class ConversaAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

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
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"


@admin.register(FilaMensagens)
class FilaMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

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
        return super().get_queryset(request).select_related("id_conversa")

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
class HistoricoMensagensAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

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
class RespostasDesafiosAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_resposta_desafio",
        "id_conversa",
        "id_etapa",
        "resposta",
        "id_historico_mensagem_cliente",
        "criado_em",
    )

    search_fields = (
        "resposta",
    )

    list_filter = (
        "id_etapa",
    )

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
class WebhookFloodEventoAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

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
class CacheControleAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

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

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST":
            obj = self.get_object(request, object_id)

            if obj and not self._desbloquear_meta_antes_de_excluir(request, obj):
                return HttpResponseRedirect(
                    reverse(
                        "admin:webhook_clientebloqueadometa_change",
                        args=[object_id],
                    )
                )

        return super().delete_view(request, object_id, extra_context)

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
            "Exclusao em massa desativada. Desbloqueie um cliente por unidade de cada vez.",
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
                obj.id_cliente.nome or obj.id_cliente.waid_telefone,
            )
        except NoReverseMatch as exc:
            logger.exception(
                "admin_cliente_link_falhou | acao=retornar_texto_sem_link erro=%s",
                exc,
            )
            return obj.id_cliente.nome or obj.id_cliente.waid_telefone

    cliente_link.short_description = "Cliente"

    def _desbloquear_meta_antes_de_excluir(self, request, obj):
        try:
            desbloquear_usuario_meta(obj.wa_id_cliente, obj.phone_id_unidade)

            logger.warning(
                "admin_cliente_desbloqueado_meta | acao=desbloquear_meta_antes_excluir usuario=%s wa_id_cliente=%s phone_id_unidade=%s",
                request.user,
                short_value(obj.wa_id_cliente),
                short_value(obj.phone_id_unidade),
            )

            self.message_user(
                request,
                f"Cliente {obj.wa_id_cliente} desbloqueado na Meta. Registro removido do banco.",
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
                f"Falha ao desbloquear na Meta. Registro mantido no banco: {exc}",
                level=messages.ERROR,
            )
            return False
```

## Passo 4 - core/database/deploy/etapa_transicao_script.py

**Arquivo completo:** `core/database/deploy/etapa_transicao_script.py`

```python
import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.etapa_transicao")


TRANSICOES_INICIAIS = (
    (1, "nome_cliente_valido", 2),
    (2, "para_mim", 4),
    (2, "para_outra_pessoa", 3),
    (3, "nome_dependente_valido", 4),
    (4, "idade_valida", 5),
)

# Novas arestas só entram quando resolver, sender, efeitos transacionais
# e testes estiverem prontos no mesmo conjunto de mudanças.


def criar_e_povoar_transicoes_etapa():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS chatbot.etapa_transicao (
                id_transicao SERIAL PRIMARY KEY,
                id_etapa_origem INT NOT NULL,
                evento VARCHAR(100) NOT NULL,
                id_etapa_destino INT NOT NULL,

                CONSTRAINT etapa_transicao_origem_fkey
                    FOREIGN KEY (id_etapa_origem)
                    REFERENCES chatbot.etapa(id_etapa)
                    ON DELETE RESTRICT,

                CONSTRAINT etapa_transicao_destino_fkey
                    FOREIGN KEY (id_etapa_destino)
                    REFERENCES chatbot.etapa(id_etapa)
                    ON DELETE RESTRICT,

                CONSTRAINT etapa_transicao_sem_auto_salto
                    CHECK (id_etapa_origem <> id_etapa_destino),

                CONSTRAINT etapa_transicao_origem_evento_unique
                    UNIQUE (id_etapa_origem, evento),

                CONSTRAINT etapa_transicao_origem_destino_unique
                    UNIQUE (id_etapa_origem, id_etapa_destino)
            );
            """
        )

        # O deploy mantém uma whitelist exata. Transições antigas ou manuais
        # não sobrevivem silenciosamente a uma nova versão da aplicação.
        cursor.execute("DELETE FROM chatbot.etapa_transicao;")

        cursor.executemany(
            """
            INSERT INTO chatbot.etapa_transicao (
                id_etapa_origem,
                evento,
                id_etapa_destino
            )
            VALUES (%s, %s, %s);
            """,
            TRANSICOES_INICIAIS,
        )

        conn.commit()
        logger.info(
            "etapa_transicao_setup_ok | acao=sincronizar_mapa quantidade=%s",
            len(TRANSICOES_INICIAIS),
        )

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "etapa_transicao_setup_erro | acao=sincronizar_mapa erro=%s",
            erro,
        )
        raise

    finally:
        if conn:
            conn.close()
```

## Passo 5 - workers/worker_flow/response_flow/transicoes/eventos.py

**Arquivo completo:** `workers/worker_flow/response_flow/transicoes/eventos.py`

```python
ETAPA_1_NOME_CLIENTE = 1
ETAPA_2_DESTINO_ATENDIMENTO = 2
ETAPA_3_NOME_DEPENDENTE = 3
ETAPA_4_IDADE_ALUNO = 4
ETAPA_5_OFERTA_AULA = 5

EVENTO_NOME_CLIENTE_VALIDO = "nome_cliente_valido"
EVENTO_NOME_DEPENDENTE_VALIDO = "nome_dependente_valido"
EVENTO_PARA_MIM = "para_mim"
EVENTO_PARA_OUTRA_PESSOA = "para_outra_pessoa"
EVENTO_IDADE_VALIDA = "idade_valida"
```

## Passo 6 - workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa4.py

**Arquivo completo:** `workers/worker_flow/response_flow/etapas/validadores_contexto/valida_etapa4.py`

```python
import re
import unicodedata
from dataclasses import dataclass


STATUS_IDADE_VALIDA = "idade_valida"
STATUS_IDADE_INVALIDA = "idade_invalida"
STATUS_IDADE_ACIMA_LIMITE = "idade_acima_limite"

MOTIVO_SEM_IDADE = "sem_idade"
MOTIVO_MULTIPLAS_IDADES = "multiplas_idades"
MOTIVO_FORA_INTERVALO = "fora_intervalo"
MOTIVO_FORMATO_INVALIDO = "formato_invalido"

UNIDADES = {
    "um": 1,
    "uma": 1,
    "dois": 2,
    "duas": 2,
    "tres": 3,
    "quatro": 4,
    "cinco": 5,
    "seis": 6,
    "sete": 7,
    "oito": 8,
    "nove": 9,
}

ATE_DEZENOVE = {
    **UNIDADES,
    "dez": 10,
    "onze": 11,
    "doze": 12,
    "treze": 13,
    "quatorze": 14,
    "catorze": 14,
    "quinze": 15,
    "dezesseis": 16,
    "dezasseis": 16,
    "dezessete": 17,
    "dezassete": 17,
    "dezoito": 18,
    "dezenove": 19,
}

DEZENAS = {
    "vinte": 20,
    "trinta": 30,
    "quarenta": 40,
    "cinquenta": 50,
    "sessenta": 60,
    "setenta": 70,
    "oitenta": 80,
    "noventa": 90,
}

CENTENAS = {
    "cem": 100,
    "cento": 100,
    "duzentos": 200,
    "duzentas": 200,
    "trezentos": 300,
    "trezentas": 300,
    "quatrocentos": 400,
    "quatrocentas": 400,
    "quinhentos": 500,
    "quinhentas": 500,
    "seiscentos": 600,
    "seiscentas": 600,
    "setecentos": 700,
    "setecentas": 700,
    "oitocentos": 800,
    "oitocentas": 800,
    "novecentos": 900,
    "novecentas": 900,
    "mil": 1000,
}

PADRAO_NUMERO = re.compile(r"\d+")
PADRAO_TOKEN = re.compile(r"[a-z]+", re.IGNORECASE)


@dataclass(frozen=True)
class ResultadoValidacaoIdade:
    status: str
    idade: int | None = None
    motivo: str | None = None

    @property
    def valida(self):
        return self.status == STATUS_IDADE_VALIDA

    @property
    def acima_limite(self):
        return self.status == STATUS_IDADE_ACIMA_LIMITE


def validar_idade(texto):
    texto_original = str(texto or "").strip()

    if not texto_original:
        return _resultado_invalido(MOTIVO_SEM_IDADE)

    texto_normalizado = _normalizar_texto(texto_original)

    if _tem_formato_numerico_invalido(texto_normalizado):
        return _resultado_invalido(MOTIVO_FORMATO_INVALIDO)

    candidatos = [
        int(valor)
        for valor in PADRAO_NUMERO.findall(texto_normalizado)
    ]
    candidatos.extend(_extrair_numeros_por_extenso(texto_normalizado))

    if not candidatos:
        return _resultado_invalido(MOTIVO_SEM_IDADE)

    if len(candidatos) != 1:
        return _resultado_invalido(MOTIVO_MULTIPLAS_IDADES)

    idade = candidatos[0]

    if idade <= 0:
        return _resultado_invalido(MOTIVO_FORA_INTERVALO)

    if idade >= 100:
        return ResultadoValidacaoIdade(
            status=STATUS_IDADE_ACIMA_LIMITE,
            idade=idade,
        )

    return ResultadoValidacaoIdade(
        status=STATUS_IDADE_VALIDA,
        idade=idade,
    )


def _tem_formato_numerico_invalido(texto):
    if re.search(
        r"(?:^|\s)(?:-|menos(?:\s+de)?)\s*\d",
        texto,
    ):
        return True

    if re.search(r"\d+\s*[,\.]\s*\d+", texto):
        return True

    return False


def _extrair_numeros_por_extenso(texto):
    tokens = PADRAO_TOKEN.findall(texto)
    resultados = []
    indice = 0

    while indice < len(tokens):
        valor, consumidos = _ler_numero_por_extenso(tokens, indice)

        if consumidos:
            resultados.append(valor)
            indice += consumidos
            continue

        indice += 1

    return resultados


def _ler_numero_por_extenso(tokens, indice):
    token = tokens[indice]

    if token in CENTENAS:
        valor = CENTENAS[token]
        consumidos = 1

        if _token_em(tokens, indice + 1) == "e":
            restante, usados = _ler_ate_noventa_e_nove(
                tokens,
                indice + 2,
            )
            if usados:
                valor += restante
                consumidos += usados + 1

        return valor, consumidos

    return _ler_ate_noventa_e_nove(tokens, indice)


def _ler_ate_noventa_e_nove(tokens, indice):
    token = _token_em(tokens, indice)

    if token in ATE_DEZENOVE:
        return ATE_DEZENOVE[token], 1

    if token not in DEZENAS:
        return None, 0

    valor = DEZENAS[token]

    if (
        _token_em(tokens, indice + 1) == "e"
        and _token_em(tokens, indice + 2) in UNIDADES
    ):
        return valor + UNIDADES[tokens[indice + 2]], 3

    return valor, 1


def _token_em(tokens, indice):
    if indice < 0 or indice >= len(tokens):
        return None

    return tokens[indice]


def _normalizar_texto(texto):
    texto_decomposto = unicodedata.normalize("NFD", texto.lower())
    return "".join(
        caractere
        for caractere in texto_decomposto
        if unicodedata.category(caractere) != "Mn"
    )


def _resultado_invalido(motivo):
    return ResultadoValidacaoIdade(
        status=STATUS_IDADE_INVALIDA,
        motivo=motivo,
    )
```

## Passo 7 - core/integrations/whatsapp/messages/etapa4_messages.py

**Arquivo completo:** `core/integrations/whatsapp/messages/etapa4_messages.py`

```python
### ENTRADA NA ETAPA 4 - CLIENTE

MENSAGEM_IDADE_ETAPA4 = (
    "Certo, agora me fala, qual é a sua idade?"
)


def montar_mensagem_idade_etapa4():
    return MENSAGEM_IDADE_ETAPA4


### ENTRADA NA ETAPA 4 - DEPENDENTE

MENSAGEM_IDADE_DEPENDENTE_ETAPA4 = (
    "Certo, agora me fala, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa4(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA4.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM MÍDIA

MENSAGEM_IDADE_ETAPA4_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa4_midia():
    return MENSAGEM_IDADE_ETAPA4_MIDIA


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MÍDIA

MENSAGEM_IDADE_DEPENDENTE_ETAPA4_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa4_midia(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA4_MIDIA.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_ETAPA4_FINANCEIRO = (
    "Olha, demais informações como valores são apresentadas no atendimento "
    "presencial após a aula gratuita.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa4_financeiro():
    return MENSAGEM_IDADE_ETAPA4_FINANCEIRO


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_DEPENDENTE_ETAPA4_FINANCEIRO = (
    "Olha, demais informações como valores são apresentadas no atendimento "
    "presencial após a aula gratuita.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa4_financeiro(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA4_FINANCEIRO.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA4 = (
    "Não consegui entender a sua idade. Digite apenas o número, exemplo: 25.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_contexto_idade_invalida_etapa4():
    return MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA4


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA4 = (
    "Não consegui entender a idade de {nome}. Digite apenas o número, "
    "exemplo: 10.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_contexto_idade_dependente_invalida_etapa4(nome):
    return MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA4.format(
        nome=nome,
    )


### CLIENTE COM MENOS DE 18 ANOS

MENSAGEM_CLIENTE_MENOR_18_ETAPA4 = (
    "Como você tem menos de 18 anos, este atendimento precisa ser realizado "
    "por um adulto responsável.\n\n"
    "Peça a um adulto para retornar nosso atendimento.\n"
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_cliente_menor_18_etapa4():
    return MENSAGEM_CLIENTE_MENOR_18_ETAPA4


### DEPENDENTE COM MENOS DE 5 ANOS

MENSAGEM_DEPENDENTE_MENOR_5_ETAPA4 = (
    "No momento, o Supera realiza treinamentos com crianças a partir de 5 "
    "anos. Quando {nome} completar 5 anos, você poderá entrar em contato "
    "novamente.\n\n"
    "Um abraço e até logo! 👋☺️"

)


def montar_mensagem_dependente_menor_5_etapa4(nome):
    return MENSAGEM_DEPENDENTE_MENOR_5_ETAPA4.format(nome=nome)


### CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS

MENSAGEM_IDADE_ACIMA_99_ETAPA4 = (
    "Entre em contato com o número {numero_comercial} para continuar "
    "seu atendimento personalizado."
)


def montar_mensagem_idade_acima_99_etapa4(numero_comercial):
    numero = str(numero_comercial or "").strip()

    if not numero:
        raise ValueError("Número comercial da unidade não configurado")

    return MENSAGEM_IDADE_ACIMA_99_ETAPA4.format(
        numero_comercial=numero,
    )
```

## Passo 8 - core/integrations/whatsapp/pywa_functions/pywa_senders/etapa4.py

**Arquivo completo:** `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa4.py`

```python
import logging

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_cliente_menor_18_etapa4,
    montar_mensagem_contexto_idade_dependente_invalida_etapa4,
    montar_mensagem_contexto_idade_invalida_etapa4,
    montar_mensagem_dependente_menor_5_etapa4,
    montar_mensagem_idade_acima_99_etapa4,
    montar_mensagem_idade_dependente_etapa4,
    montar_mensagem_idade_dependente_etapa4_financeiro,
    montar_mensagem_idade_dependente_etapa4_midia,
    montar_mensagem_idade_etapa4,
    montar_mensagem_idade_etapa4_financeiro,
    montar_mensagem_idade_etapa4_midia,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa4")

ID_ETAPA4 = 4

TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_IDADE_INVALIDA = "idade_invalida"


# CENARIO NORMAL: PERGUNTAR A IDADE DO PROPRIO CLIENTE
def enviar_etapa4_cliente(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_idade_etapa4()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente",
    )


# CENARIO NORMAL: PERGUNTAR A IDADE DO DEPENDENTE
def enviar_etapa4_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa4(
        nome_dependente
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente",
    )


# CLIENTE RESPONDE A ETAPA 4 COM MIDIA
def enviar_etapa4_cliente_midia(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_idade_etapa4_midia()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM MIDIA
def enviar_etapa4_dependente_midia(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa4_midia(
        nome_dependente
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A IDADE COM PERGUNTA FINANCEIRA
def enviar_etapa4_cliente_financeiro(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_idade_etapa4_financeiro()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA
def enviar_etapa4_dependente_financeiro(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa4_financeiro(
        nome_dependente
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A ETAPA 4 COM IDADE INVALIDA
def enviar_etapa4_cliente_contexto_idade_invalida(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_contexto_idade_invalida_etapa4()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente_contexto_idade_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_IDADE_INVALIDA,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM IDADE INVALIDA
def enviar_etapa4_dependente_contexto_idade_invalida(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = (
        montar_mensagem_contexto_idade_dependente_invalida_etapa4(
            nome_dependente
        )
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente_contexto_idade_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_IDADE_INVALIDA,
    )


# CLIENTE COM MENOS DE 18 ANOS
def enviar_etapa4_cliente_menor_18(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_cliente_menor_18_etapa4()

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_cliente_menor_18",
    )


# DEPENDENTE COM MENOS DE 5 ANOS
def enviar_etapa4_dependente_menor_5(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_dependente_menor_5_etapa4(
        nome_dependente
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_dependente_menor_5",
    )


# CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS
def enviar_etapa4_idade_acima_99(
    cliente_telefone,
    phone_id_unidade,
    numero_comercial,
):
    mensagem_bot = montar_mensagem_idade_acima_99_etapa4(
        numero_comercial
    )

    return _enviar_texto_etapa4(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa4_idade_acima_99",
    )


# CONSTRUTOR DE ENVIO DE TEXTO DA ETAPA 4
def _enviar_texto_etapa4(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
    tipo_tratamento=None,
):
    try:
        cliente_wa = conta_wa(phone_id_unidade)
        sent_message = cliente_wa.send_message(
            to=cliente_telefone,
            text=mensagem_bot,
        )
        id_hash_msg_bot = _extrair_id_hash_msg_bot(sent_message)

        logger.info(
            "%s_ok | acao=enviar_meta cliente=%s phone_number_id=%s id_hash_msg_bot=%s tratamento=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            id_hash_msg_bot,
            tipo_tratamento,
        )

        contexto_envio = {
            "enviou": True,
            "resposta_ja_existia": False,
            "mensagem_bot": mensagem_bot,
            "id_hash_msg_bot": id_hash_msg_bot,
            "id_etapa_resultante": ID_ETAPA4,
            "tipo_mensagem": "text",
            "canal": "meta_whatsapp",
            "atualizar_conversa": True,
            "atualizar_last_from_bot": True,
        }

        if tipo_tratamento:
            contexto_envio["tratamento"] = True
            contexto_envio["tipo_tratamento"] = tipo_tratamento

        return contexto_envio

    except Exception as erro:
        logger.exception(
            "%s_erro | motivo=meta_falhou acao=levantar_erro cliente=%s phone_number_id=%s erro=%s",
            evento,
            short_value(cliente_telefone),
            short_value(phone_id_unidade),
            erro,
        )
        raise ErroEnvioMeta(
            "Meta falhou ao enviar mensagem da etapa 4",
            id_etapa=ID_ETAPA4,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro


def _extrair_id_hash_msg_bot(sent_message):
    id_hash = getattr(sent_message, "id", None)
    if id_hash:
        return id_hash

    if isinstance(sent_message, dict):
        mensagens = sent_message.get("messages") or []
        if mensagens:
            id_hash = mensagens[0].get("id")
            if id_hash:
                return id_hash

    raise ValueError("Meta confirmou envio, mas nao retornou id da mensagem")
```

## Passo 9 - core/repositories/contexto_etapa4.py

**Arquivo completo:** `core/repositories/contexto_etapa4.py`

```python
import logging


logger = logging.getLogger("db.contexto_etapa4")


def buscar_contexto_etapa4(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            u.numero_comercial,
            d.nome_dependente
        FROM chatbot.unidade u
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = %s
        WHERE u.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 4 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    numero_comercial, nome_dependente = resultado

    logger.debug(
        "contexto_etapa4_consultado | id_conversa=%s id_unidade=%s "
        "numero_comercial_configurado=%s dependente_nomeado=%s",
        id_conversa,
        id_unidade,
        bool(numero_comercial),
        bool(nome_dependente),
    )

    return {
        "numero_comercial_unidade": numero_comercial,
        "nome_dependente": nome_dependente,
    }
```

## Passo 10 - workers/worker_flow/valida_historico.py

**Arquivo completo:** `workers/worker_flow/valida_historico.py`

```python
import logging

from core.logging_config import short_value
from core.repositories.contexto_etapa4 import buscar_contexto_etapa4
from core.repositories.inserts import inserir_historico_mensagem_cliente
from core.repositories.querys import buscar_resposta_bot_por_mensagem_cliente
from core.repositories.transicoes_etapa import listar_transicoes_permitidas
from core.repositories.updates import (
    atualizar_conversa_mensagem_cliente,
    atualizar_conversa_resposta_bot_sem_avancar,
)
from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    montar_contexto_transicao,
    prever_etapa_resposta,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_4_IDADE_ALUNO,
)


logger = logging.getLogger("worker.valida_historico")

ETAPA_INICIAL = 1


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

    transicoes_permitidas = listar_transicoes_permitidas(
        id_etapa_cliente,
        cursor,
    )
    contexto_transicao = montar_contexto_transicao(
        id_etapa_cliente,
        transicoes_permitidas,
    )
    contexto_especifico_etapa = {}

    if id_etapa_cliente == ETAPA_4_IDADE_ALUNO:
        contexto_especifico_etapa = buscar_contexto_etapa4(
            id_conversa,
            contexto_banco["id_unidade"],
            cursor,
        )

        if (
            contexto_conversa.get("status_dependente")
            and not contexto_especifico_etapa["nome_dependente"]
        ):
            raise ValueError(
                "Etapa 4 de dependente sem nome persistido"
            )

    if resposta_bot_para_mensagem_atual:
        id_etapa_resposta = resposta_bot_para_mensagem_atual["id_etapa"]

        if last_message_from_entrada != "bot":
            atualizar_conversa_resposta_bot_sem_avancar(
                id_conversa,
                resposta_bot_para_mensagem_atual["received_data_hora"],
                cursor,
            )

        last_message_from_saida = "bot"
    else:
        id_etapa_resposta = prever_etapa_resposta(
            contexto_conversa.get("id_etapa_atual"),
            contexto_transicao["transicoes_permitidas"],
            etapa_inicial=ETAPA_INICIAL,
        )
        atualizar_conversa_mensagem_cliente(
            id_conversa,
            data_historico_cliente,
            cursor,
        )
        last_message_from_saida = "cliente"

    logger.info(
        "historico_validado | acao=registrar_cliente id_mensagem=%s id_historico=%s inserido=%s id_conversa=%s etapa_cliente=%s etapa_resposta_previa=%s eventos_transicao=%s last_from_entrada=%s last_from_saida=%s retry=%s resposta_bot_existente=%s cliente=%s phone_number_id=%s",
        mensagem["id_mensagem"],
        id_historico_cliente,
        cliente_inserido_no_historico,
        id_conversa,
        id_etapa_cliente,
        id_etapa_resposta,
        sorted(transicoes_permitidas),
        last_message_from_entrada,
        last_message_from_saida,
        mensagem["retry_count"],
        bool(resposta_bot_para_mensagem_atual),
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
    )

    contexto_historico = {
        "id_conversa": id_conversa,
        "id_cliente": contexto_banco["id_cliente"],
        "id_unidade": contexto_banco["id_unidade"],
        "id_etapa_atual": contexto_conversa.get("id_etapa_atual"),
        "id_etapa_cliente": id_etapa_cliente,
        # Compatibilidade apenas para logs existentes. Este campo nunca decide
        # uma transição e pode ser None quando há mais de um destino.
        "id_etapa_resposta": id_etapa_resposta,
        "id_etapa_origem_transicao": contexto_transicao[
            "id_etapa_origem_transicao"
        ],
        "transicoes_permitidas": contexto_transicao[
            "transicoes_permitidas"
        ],
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
    contexto_historico.update(contexto_especifico_etapa)
    return contexto_historico


def _resolver_etapa_cliente(contexto_conversa):
    id_etapa_atual = contexto_conversa.get("id_etapa_atual")

    if id_etapa_atual is None:
        return ETAPA_INICIAL

    return id_etapa_atual


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

## Passo 11 - workers/worker_flow/response_flow/etapas/etapa2_worker.py

**Arquivo completo:** `workers/worker_flow/response_flow/etapas/etapa2_worker.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa2 import (
    enviar_etapa2_contexto_opcao_invalida,
    enviar_etapa2_financeiro,
    enviar_etapa2_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import (
    enviar_etapa3,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import (
    enviar_etapa4_cliente,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    OPCAO_PARA_MIM,
    OPCAO_PARA_OUTRA_PESSOA,
    TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
    validar_etapa2,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_3_NOME_DEPENDENTE,
    ETAPA_4_IDADE_ALUNO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A SEGUNDA ETAPA
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA, QUE É a 3 ou 4
"""


logger = logging.getLogger("worker.etapa2")


def resolve_etapa2(contexto_historico):
    """
    Mídia, financeiro e contexto inválido recebem tratamento sem avançar.

    para_mim resolve 2 -> 4.
    para_outra_pessoa resolve 2 -> 3.

    As etapas 3 e 4 possuem senders reais.
    """
    id_conversa = contexto_historico["id_conversa"]
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    ## CAMPOS QUE VALIDAM MIDIA NA ETAPA 2

    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        return enviar_etapa2_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    ## CAMPOS QUE VALIDAM FINANCEIRO NA ETAPA 2

    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_etapa2_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )


    ### VALIDANDO OPCOES
    evento_transicao = validar_etapa2(texto_cliente)

    if evento_transicao is None:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_CONTEXTO_INVALIDO,
        )

        return enviar_etapa2_contexto_opcao_invalida(
            cliente_telefone,
            phone_id_unidade,
        )

    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.

    destinos_esperados = _destinos_esperados_por_evento(evento_transicao)
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        evento_transicao,
        destinos_esperados=destinos_esperados,
    )
    status_dependente = (
        evento_transicao == OPCAO_PARA_OUTRA_PESSOA
    )

    # O mapa autoriza o destino antes de qualquer envio externo.
    if evento_transicao == OPCAO_PARA_OUTRA_PESSOA:
        contexto_envio = enviar_etapa3(
            cliente_telefone,
            phone_id_unidade,
        )
        contexto_envio["opcao_atendimento"] = evento_transicao
        contexto_envio["status_dependente"] = status_dependente
    else:
        contexto_envio = enviar_etapa4_cliente(
            cliente_telefone,
            phone_id_unidade,
        )
        contexto_envio["opcao_atendimento"] = evento_transicao
        contexto_envio["status_dependente"] = status_dependente

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        evento_transicao,
        etapa_destino,
    )















def _destinos_esperados_por_evento(evento_transicao):
    if evento_transicao == OPCAO_PARA_MIM:
        return {ETAPA_4_IDADE_ALUNO}

    if evento_transicao == OPCAO_PARA_OUTRA_PESSOA:
        return {ETAPA_3_NOME_DEPENDENTE}

    return set()


def _logar_tipo_nao_suportado(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(contexto_historico, motivo):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        None,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
```

## Passo 12 - workers/worker_flow/response_flow/etapas/etapa3_worker.py

**Arquivo completo:** `workers/worker_flow/response_flow/etapas/etapa3_worker.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa3 import (
    enviar_etapa3_contexto_nome_invalido,
    enviar_etapa3_financeiro,
    enviar_etapa3_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import (
    enviar_etapa4_dependente,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    TIPO_TRATAMENTO_NOME_INVALIDO,
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_4_IDADE_ALUNO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


"""
ESSE ARQUIVO TEM DUAS RESPONSABILIDADES

- VALIDAR A ETAPA 3
- ENCAMINHAR PARA A ETAPA AUTORIZADA PELO MAPA
"""


logger = logging.getLogger("worker.etapa3")


def resolve_etapa3(contexto_historico):
    """
    Mídia, financeiro e nome inválido recebem tratamento sem avançar.

    Nome válido resolve 3 -> 4, envia a etapa 4 e carrega o primeiro nome do
    dependente para a persistência transacional.
    """
    id_conversa = contexto_historico["id_conversa"]
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente_atual["cliente_telefone"]
    phone_id_unidade = mensagem_cliente_atual["id_phone_unidade"]

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tipo_nao_suportado(contexto_historico)

        return enviar_etapa3_midia(
            cliente_telefone,
            phone_id_unidade,
        )

    # Pergunta financeira tem prioridade sobre a validação de nome.
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )

        return enviar_etapa3_financeiro(
            cliente_telefone,
            phone_id_unidade,
        )

    ### VALIDACAO DE NOME

    resultado_nome = validar_nome_cliente(texto_cliente)

    if not resultado_nome.valido:
        _logar_tratamento_texto(
            contexto_historico,
            TIPO_TRATAMENTO_NOME_INVALIDO,
            motivo_detalhado=resultado_nome.motivo,
        )

        return enviar_etapa3_contexto_nome_invalido(
            cliente_telefone,
            phone_id_unidade,
        )


    # VALIDANDO DESTINO(S)
    # A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.

    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_NOME_DEPENDENTE_VALIDO,
        destinos_esperados={ETAPA_4_IDADE_ALUNO},
    )

    logger.info(
        "etapa3_nome_dependente_validado | acao=enviar_etapa4 id_conversa=%s id_mensagem_fila=%s evento=%s etapa_destino=%s primeiro_nome=%s",
        id_conversa,
        mensagem_cliente_atual["id_mensagem_fila"],
        EVENTO_NOME_DEPENDENTE_VALIDO,
        etapa_destino,
        short_value(resultado_nome.primeiro_nome),
    )

    contexto_envio = enviar_etapa4_dependente(
        cliente_telefone,
        phone_id_unidade,
        resultado_nome.primeiro_nome,
    )
    contexto_envio["primeiro_nome_dependente"] = resultado_nome.primeiro_nome

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_NOME_DEPENDENTE_VALIDO,
        etapa_destino,
    )














def _logar_tipo_nao_suportado(contexto_historico):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_invalida | motivo=tipo_mensagem_nao_suportado acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s tipo=%s etapa_cliente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico.get("tipo_mensagem_atual"),
        contexto_historico["id_etapa_cliente"],
    )


def _logar_tratamento_texto(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem_cliente_atual["id_mensagem_fila"],
        short_value(mensagem_cliente_atual["cliente_telefone"]),
        short_value(mensagem_cliente_atual["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
```

## Passo 13 - workers/worker_flow/response_flow/etapas/etapa4_worker.py

**Arquivo completo:** `workers/worker_flow/response_flow/etapas/etapa4_worker.py`

```python
import logging

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa4 import (
    enviar_etapa4_cliente_contexto_idade_invalida,
    enviar_etapa4_cliente_financeiro,
    enviar_etapa4_cliente_menor_18,
    enviar_etapa4_cliente_midia,
    enviar_etapa4_dependente_contexto_idade_invalida,
    enviar_etapa4_dependente_financeiro,
    enviar_etapa4_dependente_menor_5,
    enviar_etapa4_dependente_midia,
    enviar_etapa4_idade_acima_99,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_5_OFERTA_AULA,
    EVENTO_IDADE_VALIDA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa4")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"


def resolve_etapa4(contexto_historico):
    """
    Valida a idade do aluno e decide tratamento, encerramento ou 4 -> 5.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )
    nome_dependente = contexto_historico.get("nome_dependente")
    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]
    phone_id_unidade = mensagem_cliente["id_phone_unidade"]

    # Mídia tem prioridade sobre todas as validações de texto.
    if validar_midia(tipo_mensagem):
        _logar_tratamento(
            contexto_historico,
            "tipo_mensagem_nao_suportado",
        )
        return _enviar_tratamento_midia(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    # Pergunta financeira tem prioridade sobre a validação da idade.
    if validar_pergunta_financeira(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_FINANCEIRO,
        )
        return _enviar_tratamento_financeiro(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    resultado_idade = validar_idade(texto_cliente)

    if not resultado_idade.valida and not resultado_idade.acima_limite:
        _logar_tratamento(
            contexto_historico,
            "idade_invalida",
            motivo_detalhado=resultado_idade.motivo,
        )
        return _enviar_tratamento_idade_invalida(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    if resultado_idade.acima_limite:
        contexto_envio = enviar_etapa4_idade_acima_99(
            cliente_telefone,
            phone_id_unidade,
            contexto_historico.get("numero_comercial_unidade"),
        )
        return _anexar_encerramento(
            contexto_envio,
            resultado_idade.idade,
            MOTIVO_IDADE_ACIMA_99,
        )

    idade = resultado_idade.idade

    if not status_dependente and idade < 18:
        contexto_envio = enviar_etapa4_cliente_menor_18(
            cliente_telefone,
            phone_id_unidade,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_CLIENTE_MENOR_18,
        )

    if status_dependente and idade < 5:
        contexto_envio = enviar_etapa4_dependente_menor_5(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_DEPENDENTE_MENOR_5,
            excluir_dependente=True,
        )

    # VALIDANDO DESTINO(S)
    # A resposta passou pelos tratamentos; agora o mapa autoriza 4 -> 5.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_IDADE_VALIDA,
        destinos_esperados={ETAPA_5_OFERTA_AULA},
    )

    logger.info(
        "etapa4_idade_validada | acao=simular_envio_etapa5 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s idade=%s status_dependente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_IDADE_VALIDA,
        etapa_destino,
        idade,
        status_dependente,
    )

    contexto_envio = _montar_contexto_etapa5_simulada(
        contexto_historico,
        etapa_destino,
        idade,
    )

    return anexar_transicao_ao_contexto_envio(
        contexto_historico,
        contexto_envio,
        EVENTO_IDADE_VALIDA,
        etapa_destino,
    )


def _enviar_tratamento_midia(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa4_dependente_midia(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa4_cliente_midia(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_financeiro(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa4_dependente_financeiro(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa4_cliente_financeiro(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_idade_invalida(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa4_dependente_contexto_idade_invalida(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa4_cliente_contexto_idade_invalida(
        cliente_telefone,
        phone_id_unidade,
    )


def _anexar_encerramento(
    contexto_envio,
    idade,
    motivo,
    *,
    excluir_dependente=False,
):
    contexto_envio.update(
        {
            "idade_aluno": idade,
            "encerrar_atendimento": True,
            "motivo_encerramento": motivo,
            "excluir_dependente": excluir_dependente,
        }
    )
    return contexto_envio


def _montar_contexto_etapa5_simulada(
    contexto_historico,
    etapa_destino,
    idade,
):
    # TEMPORÁRIO: remover quando o sender real da etapa 5 existir.
    id_mensagem_fila = contexto_historico[
        "mensagem_cliente_atual"
    ]["id_mensagem_fila"]

    return {
        "enviou": True,
        "envio_simulado": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "Nesse momento a futura etapa 5 foi enviada.",
        "id_hash_msg_bot": (
            f"simulacao.etapa{etapa_destino}.fila.{id_mensagem_fila}"
        ),
        "id_etapa_resultante": etapa_destino,
        "tipo_mensagem": "simulacao",
        "canal": "simulacao_worker",
        "atualizar_conversa": True,
        "atualizar_last_from_bot": True,
        "idade_aluno": idade,
    }


def _logar_tratamento(
    contexto_historico,
    motivo,
    *,
    motivo_detalhado=None,
):
    mensagem = contexto_historico["mensagem_cliente_atual"]

    logger.info(
        "resposta_cliente_tratamento | motivo=%s motivo_detalhado=%s "
        "acao=tratar_sem_avancar id_conversa=%s id_mensagem_fila=%s "
        "cliente=%s phone_number_id=%s etapa_cliente=%s",
        motivo,
        motivo_detalhado,
        contexto_historico["id_conversa"],
        mensagem["id_mensagem_fila"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_historico["id_etapa_cliente"],
    )
```

## Passo 14 - workers/worker_flow/response_flow/flow_sender.py

**Arquivo completo:** `workers/worker_flow/response_flow/flow_sender.py`

```python
import logging

from workers.worker_flow.response_flow.etapas.etapa1_worker import (
    resolve_etapa1,
)
from workers.worker_flow.response_flow.etapas.etapa2_worker import (
    resolve_etapa2,
)
from workers.worker_flow.response_flow.etapas.etapa3_worker import (
    resolve_etapa3,
)
from workers.worker_flow.response_flow.etapas.etapa4_worker import (
    resolve_etapa4,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    identificar_evento_por_destino,
)


logger = logging.getLogger("worker.sender")


def flow_sender(contexto_historico):
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_atual = contexto_historico.get("id_etapa_atual")
    retry_count = contexto_historico["retry_count"]

    mensagem_cliente_atual = contexto_historico["mensagem_cliente_atual"]
    cliente_atual_id_mensagem_fila = mensagem_cliente_atual["id_mensagem_fila"]
    cliente_atual_id_hash_msg = mensagem_cliente_atual["id_hash_msg"]

    resposta_bot_atual = (
        contexto_historico["resposta_bot_para_mensagem_atual"] or {}
    )

    # Esta barreira continua antes de qualquer resolver ou sender.
    if resposta_bot_atual:
        id_etapa_resposta = resposta_bot_atual.get("id_etapa")
        evento_transicao = identificar_evento_por_destino(
            contexto_historico,
            id_etapa_resposta,
        )

        logger.info(
            "flow_sender_idempotencia_ok | motivo=resposta_bot_ja_registrada acao=nao_enviar id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s id_resposta_bot=%s etapa_resposta=%s evento_transicao=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            resposta_bot_atual.get("id_mensagem"),
            id_etapa_resposta,
            evento_transicao,
            retry_count,
        )

        contexto_envio = {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta_bot_atual.get("id_hash_msg"),
            "id_etapa_resultante": id_etapa_resposta,
            "id_etapa_origem_transicao": contexto_historico.get(
                "id_etapa_origem_transicao"
            ),
        }

        if evento_transicao:
            contexto_envio["evento_transicao"] = evento_transicao

        return contexto_envio

    if retry_count > 1:
        logger.info(
            "flow_sender_reprocessamento | motivo=retry_maior_que_um acao=continuar_sem_resposta_previa id_conversa=%s id_mensagem_fila=%s id_hash_cliente=%s retry=%s",
            id_conversa,
            cliente_atual_id_mensagem_fila,
            cliente_atual_id_hash_msg,
            retry_count,
        )

    if id_etapa_atual is None or id_etapa_atual == 1:
        return resolve_etapa1(contexto_historico)

    if id_etapa_atual == 2:
        return resolve_etapa2(contexto_historico)

    if id_etapa_atual == 3:
        return resolve_etapa3(contexto_historico)

    if id_etapa_atual == 4:
        return resolve_etapa4(contexto_historico)

    logger.warning(
        "flow_sender_etapa_pendente | acao=nao_enviar id_conversa=%s etapa=%s",
        id_conversa,
        id_etapa_atual,
    )
    raise NotImplementedError(
        f"Sender da etapa atual {id_etapa_atual} ainda nao implementado"
    )
```

## Passo 15 - core/repositories/idade_aluno.py

**Arquivo completo:** `core/repositories/idade_aluno.py`

```python
def atualizar_idade_cliente(id_cliente, idade, cursor):
    cursor.execute(
        """
        UPDATE chatbot.cliente
        SET idade = %s
        WHERE id_cliente = %s;
        """,
        (idade, id_cliente),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Cliente não atualizado com idade "
            f"(id_cliente={id_cliente}, linhas={cursor.rowcount})"
        )


def atualizar_idade_dependente(id_conversa, idade, cursor):
    cursor.execute(
        """
        UPDATE chatbot.dependente
        SET idade = %s
        WHERE id_conversa = %s;
        """,
        (idade, id_conversa),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Dependente não atualizado com idade "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )
```

## Passo 16 - workers/worker_flow/transacoes/efeitos_transicao.py

**Arquivo completo:** `workers/worker_flow/transacoes/efeitos_transicao.py`

```python
import logging

from core.logging_config import short_value
from core.repositories.idade_aluno import (
    atualizar_idade_cliente,
    atualizar_idade_dependente,
)
from core.repositories.inserts import inserir_dependente_para_conversa
from core.repositories.updates import (
    atualizar_nome_cliente_por_telefone,
    atualizar_nome_dependente_por_conversa,
    atualizar_status_dependente_conversa,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    validar_idade,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
    ETAPA_2_DESTINO_ATENDIMENTO,
    ETAPA_3_NOME_DEPENDENTE,
    ETAPA_4_IDADE_ALUNO,
    ETAPA_5_OFERTA_AULA,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


logger = logging.getLogger("worker.support")


def atualizar_banco_conforme_transicao_de_etapa(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Aplica somente os efeitos de negócio da aresta já autorizada.

    A navegação é definida pelo mapa etapa_transicao e persistida antes desta
    função. Os ifs abaixo tornam explícito o efeito de cada origem + evento.
    """
    etapa_origem = contexto_historico.get(
        "id_etapa_origem_transicao"
    )
    evento = contexto_envio.get("evento_transicao")
    etapa_destino = contexto_envio.get("id_etapa_resultante")

    # Sem evento não existe transição nem efeito específico de etapa.
    if not evento:
        return None

    # ETAPA 1
    if etapa_origem == ETAPA_1_NOME_CLIENTE:
        # 1 -> 2: o cliente informou o próprio nome.
        if evento == EVENTO_NOME_CLIENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_2_DESTINO_ATENDIMENTO,
            )
            return _persistir_nome_cliente_capturado_na_etapa1(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 2
    if etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO:
        # 2 -> 4: o atendimento será para o próprio cliente.
        if evento == EVENTO_PARA_MIM:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_4_IDADE_ALUNO,
            )
            return _persistir_destino_atendimento_da_etapa2(
                contexto_historico,
                evento,
                etapa_destino,
                status_dependente=False,
                cursor=cursor,
            )

        # 2 -> 3: o atendimento será para um dependente.
        if evento == EVENTO_PARA_OUTRA_PESSOA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_3_NOME_DEPENDENTE,
            )
            return _persistir_destino_atendimento_da_etapa2(
                contexto_historico,
                evento,
                etapa_destino,
                status_dependente=True,
                cursor=cursor,
            )

    # ETAPA 3
    if etapa_origem == ETAPA_3_NOME_DEPENDENTE:
        # 3 -> 4: o cliente informou o nome do dependente.
        if evento == EVENTO_NOME_DEPENDENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_4_IDADE_ALUNO,
            )
            return _persistir_nome_dependente_capturado_na_etapa3(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 4
    if etapa_origem == ETAPA_4_IDADE_ALUNO:
        # 4 -> 5: a idade do aluno foi validada.
        if evento == EVENTO_IDADE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_5_OFERTA_AULA,
            )
            return _persistir_idade_capturada_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    raise ValueError(
        "Transicao sem efeitos conhecidos "
        f"(origem={etapa_origem}, evento={evento}, "
        f"destino={etapa_destino})"
    )


def _exigir_destino(
    etapa_origem,
    evento,
    etapa_destino,
    destino_esperado,
):
    if etapa_destino != destino_esperado:
        raise ValueError(
            "Efeito de transicao recebeu destino incompativel "
            f"(origem={etapa_origem}, evento={evento}, "
            f"destino={etapa_destino}, "
            f"destino_esperado={destino_esperado})"
        )


def _persistir_nome_cliente_capturado_na_etapa1(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_capturado(
        contexto_historico,
        contexto_envio,
        "primeiro_nome_cliente",
    )

    if not primeiro_nome:
        print(
            "\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
            "!!! NOME VAZIO NA TRANSICAO 1 -> 2: ANOMALIA RARA E CRITICA !!!\n"
            "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!\n"
        )
        logger.critical(
            "cliente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_1_2 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do cliente nao foi resolvido na transicao 1 -> 2"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    cliente_telefone = mensagem_cliente["cliente_telefone"]

    atualizar_nome_cliente_por_telefone(
        cliente_telefone,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "cliente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s cliente=%s",
        EVENTO_NOME_CLIENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        contexto_historico["id_conversa"],
        short_value(cliente_telefone),
    )

    return {
        "cliente_nome_atualizado": True,
        "primeiro_nome_cliente": primeiro_nome,
    }


def _persistir_destino_atendimento_da_etapa2(
    contexto_historico,
    evento,
    etapa_destino,
    *,
    status_dependente,
    cursor,
):
    id_conversa = contexto_historico["id_conversa"]

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente,
        cursor,
    )

    contexto_persistido = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente,
        "opcao_atendimento": evento,
        "dependente_criado": False,
    }

    if status_dependente:
        dependente = inserir_dependente_para_conversa(
            id_conversa,
            cursor,
        )
        contexto_persistido.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )

    logger.info(
        "destino_atendimento_persistido | acao=salvar_efeitos_transicao evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s status_dependente=%s dependente_criado=%s",
        evento,
        contexto_historico.get("id_etapa_origem_transicao"),
        etapa_destino,
        id_conversa,
        status_dependente,
        contexto_persistido["dependente_criado"],
    )

    return contexto_persistido


def _persistir_nome_dependente_capturado_na_etapa3(
    contexto_historico,
    contexto_envio,
    cursor,
):
    primeiro_nome = _resolver_primeiro_nome_capturado(
        contexto_historico,
        contexto_envio,
        "primeiro_nome_dependente",
    )

    if not primeiro_nome:
        logger.critical(
            "dependente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_3_4 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do dependente nao foi resolvido na transicao 3 -> 4"
        )

    id_conversa = contexto_historico["id_conversa"]
    atualizar_nome_dependente_por_conversa(
        id_conversa,
        primeiro_nome,
        cursor,
    )

    logger.info(
        "dependente_nome_persistido | acao=salvar_nome evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        EVENTO_NOME_DEPENDENTE_VALIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
    )

    return {
        "dependente_nome_atualizado": True,
        "primeiro_nome_dependente": primeiro_nome,
    }


def _resolver_primeiro_nome_capturado(
    contexto_historico,
    contexto_envio,
    chave_contexto,
):
    primeiro_nome = contexto_envio.get(chave_contexto)

    if primeiro_nome:
        return primeiro_nome

    resultado_nome = validar_nome_cliente(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado_nome.valido:
        return resultado_nome.primeiro_nome

    return None


def _persistir_idade_capturada_na_etapa4(
    contexto_historico,
    contexto_envio,
    cursor,
):
    idade = contexto_envio.get("idade_aluno")

    if idade is None:
        resultado = validar_idade(
            contexto_historico.get("texto_cliente_atual") or ""
        )
        if resultado.valida:
            idade = resultado.idade

    if idade is None:
        raise ValueError(
            "Idade não reconstruída na transição 4 -> 5"
        )

    if contexto_historico.get("status_dependente"):
        atualizar_idade_dependente(
            contexto_historico["id_conversa"],
            idade,
            cursor,
        )
        destino_dado = "dependente"
    else:
        atualizar_idade_cliente(
            contexto_historico["id_cliente"],
            idade,
            cursor,
        )
        destino_dado = "cliente"

    logger.info(
        "idade_aluno_persistida | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s idade=%s destino_dado=%s",
        EVENTO_IDADE_VALIDA,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        idade,
        destino_dado,
    )

    return {
        "idade_aluno_atualizada": True,
        "idade_aluno": idade,
        "destino_dado": destino_dado,
    }
```

## Passo 17 - core/repositories/encerramento_atendimento.py

**Arquivo completo:** `core/repositories/encerramento_atendimento.py`

```python
def excluir_dependente_da_conversa(id_conversa, cursor):
    cursor.execute(
        """
        DELETE FROM chatbot.dependente
        WHERE id_conversa = %s;
        """,
        (id_conversa,),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Dependente não excluído no encerramento "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )


def encerrar_conversa(id_conversa, cursor):
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET
            status_ativa = FALSE,
            finalizou_em = NOW(),
            processing = FALSE,
            processing_started_at = NULL
        WHERE id_conversa = %s
          AND status_ativa = TRUE;
        """,
        (id_conversa,),
    )

    if cursor.rowcount != 1:
        raise RuntimeError(
            "Conversa não encerrada "
            f"(id_conversa={id_conversa}, linhas={cursor.rowcount})"
        )
```

## Passo 18 - workers/worker_flow/transacoes/encerramento_atendimento.py

**Arquivo completo:** `workers/worker_flow/transacoes/encerramento_atendimento.py`

```python
import logging

from core.repositories.encerramento_atendimento import (
    encerrar_conversa,
    excluir_dependente_da_conversa,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    validar_idade,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_4_IDADE_ALUNO,
)


logger = logging.getLogger("worker.support")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"


def resolver_intencao_encerramento(
    contexto_historico,
    contexto_envio,
):
    if contexto_envio.get("evento_transicao"):
        return None

    if contexto_envio.get("encerrar_atendimento"):
        return {
            "motivo": contexto_envio["motivo_encerramento"],
            "excluir_dependente": bool(
                contexto_envio.get("excluir_dependente")
            ),
        }

    # No retry, a resposta já existe e a decisão é reconstruída pela mesma
    # mensagem original da etapa 4, sem consultar conversas anteriores.
    if not contexto_envio.get("resposta_ja_existia"):
        return None

    if (
        contexto_historico.get("id_etapa_origem_transicao")
        != ETAPA_4_IDADE_ALUNO
    ):
        return None

    resultado = validar_idade(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado.acima_limite:
        return {
            "motivo": MOTIVO_IDADE_ACIMA_99,
            "excluir_dependente": False,
        }

    if not resultado.valida:
        return None

    if contexto_historico.get("status_dependente"):
        if resultado.idade < 5:
            return {
                "motivo": MOTIVO_DEPENDENTE_MENOR_5,
                "excluir_dependente": True,
            }
        return None

    if resultado.idade < 18:
        return {
            "motivo": MOTIVO_CLIENTE_MENOR_18,
            "excluir_dependente": False,
        }

    return None


def aplicar_encerramento_se_necessario(
    id_conversa,
    intencao_encerramento,
    cursor,
):
    if not intencao_encerramento:
        return False

    if intencao_encerramento["excluir_dependente"]:
        excluir_dependente_da_conversa(id_conversa, cursor)

    encerrar_conversa(id_conversa, cursor)

    logger.info(
        "atendimento_encerrado | acao=encerrar_sem_bloqueio "
        "id_conversa=%s motivo=%s dependente_excluido=%s",
        id_conversa,
        intencao_encerramento["motivo"],
        intencao_encerramento["excluir_dependente"],
    )
    return True
```

## Passo 19 - workers/worker_flow/transacoes/persistencia_resposta.py

**Arquivo completo:** `workers/worker_flow/transacoes/persistencia_resposta.py`

```python
import logging

from core.repositories.inserts import inserir_historico_mensagem_bot
from workers.worker_flow.transacoes.encerramento_atendimento import (
    resolver_intencao_encerramento,
)
from workers.worker_flow.transacoes.efeitos_transicao import (
    atualizar_banco_conforme_transicao_de_etapa,
)
from workers.worker_flow.transacoes.movimento_conversa import (
    MOVIMENTO_SEM_AVANCO,
    persistir_movimento_conversa,
)


logger = logging.getLogger("worker.support")


def _obter_data_interacao_bot_existente(contexto_historico):
    resposta_bot = (
        contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    )
    data_interacao = resposta_bot.get("received_data_hora")

    if data_interacao is None:
        raise ValueError(
            "Resposta do bot existente sem received_data_hora persistido"
        )

    return data_interacao


def atualizar_banco_com_contexto_final(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste o resultado completo do ciclo em uma única transação.

    Ordem preservada:
    1. registrar ou recuperar a resposta do bot;
    2. persistir inicialização, transição ou permanência;
    3. aplicar os efeitos específicos da aresta;
    4. devolver o contexto final para a finalização da fila.
    """
    id_conversa = contexto_historico["id_conversa"]
    id_etapa_resultante = contexto_envio.get("id_etapa_resultante")
    resposta_ja_existia = bool(
        contexto_envio.get("resposta_ja_existia")
    )

    (
        id_historico_bot,
        data_interacao_bot,
        historico_bot_inserido,
    ) = _persistir_ou_recuperar_resposta_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )

    movimento = persistir_movimento_conversa(
        contexto_historico,
        contexto_envio,
        data_interacao_bot,
        cursor,
    )

    efeitos_transicao = atualizar_banco_conforme_transicao_de_etapa(
        contexto_historico,
        contexto_envio,
        cursor,
    )
    intencao_encerramento = resolver_intencao_encerramento(
        contexto_historico,
        contexto_envio,
    )

    logger.info(
        "resposta_bot_persistida | acao=registrar_historico_e_contexto id_conversa=%s id_historico_bot=%s inserido=%s resposta_ja_existia=%s movimento=%s etapa=%s evento=%s id_hash_msg_bot=%s",
        id_conversa,
        id_historico_bot,
        historico_bot_inserido,
        resposta_ja_existia,
        movimento,
        id_etapa_resultante,
        contexto_envio.get("evento_transicao"),
        contexto_envio.get("id_hash_msg_bot"),
    )

    contexto_final = {
        "historico_bot_inserido": historico_bot_inserido,
        "resposta_ja_existia": resposta_ja_existia,
        "id_hash_msg_bot": contexto_envio.get("id_hash_msg_bot"),
        "id_etapa_resultante": id_etapa_resultante,
        "movimento_conversa": movimento,
        "atualizar_conversa": movimento != MOVIMENTO_SEM_AVANCO,
        "atualizar_last_from_bot": True,
        "intencao_encerramento": intencao_encerramento,
    }

    if id_historico_bot is not None:
        contexto_final.update(
            {
                "id_historico_bot": id_historico_bot,
                "data_historico_bot": data_interacao_bot,
            }
        )

    if efeitos_transicao:
        contexto_final["efeitos_transicao"] = efeitos_transicao

    return contexto_final


def _persistir_ou_recuperar_resposta_bot(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("resposta_ja_existia"):
        return (
            None,
            _obter_data_interacao_bot_existente(contexto_historico),
            False,
        )

    if not contexto_envio.get("enviou"):
        raise ValueError(
            "Contexto de envio sem resposta enviada e sem resposta existente"
        )

    return inserir_historico_mensagem_bot(
        contexto_historico,
        contexto_envio,
        cursor,
    )
```

## Passo 20 - workers/worker_flow/transacoes/finalizacao_fila.py

**Arquivo completo:** `workers/worker_flow/transacoes/finalizacao_fila.py`

```python
import logging

from core.logging_config import short_value
from core.repositories.updates import marcar_mensagem_como_enviada
from workers.worker_flow.transacoes.encerramento_atendimento import (
    aplicar_encerramento_se_necessario,
)


logger = logging.getLogger("worker.support")


def finalizar_mensagem_processada(
    mensagem,
    contexto_banco,
    contexto_final,
    lock_version,
    cursor,
):
    contexto_conversa = contexto_banco["conversa"]
    id_conversa = contexto_conversa["id_conversa"]

    atendimento_encerrado = aplicar_encerramento_se_necessario(
        id_conversa,
        contexto_final.get("intencao_encerramento"),
        cursor,
    )

    marcar_mensagem_como_enviada(mensagem["id_mensagem"], cursor)

    logger.info(
        "mensagem_processada | acao=marcar_sent id_mensagem=%s cliente=%s phone_number_id=%s id_unidade=%s id_conversa=%s estado=%s lock_version=%s atendimento_encerrado=%s",
        mensagem["id_mensagem"],
        short_value(mensagem["cliente_telefone"]),
        short_value(mensagem["id_phone_unidade"]),
        contexto_banco["id_unidade"],
        id_conversa,
        contexto_conversa["estado"],
        lock_version,
        atendimento_encerrado,
    )
```

## Passo 21 - workers/worker_flow/response_flow/flow_worker.py

**Arquivo completo:** `workers/worker_flow/response_flow/flow_worker.py`

```python
import logging

import psycopg2
from core.cache.cache_unidade import UnidadeNaoEncontrada
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.logging_config import short_value
from core.repositories.querys import pegar_mensagens_da_fila, tentar_lock_conversa
from core.repositories.updates import vincular_mensagem_fila_a_conversa
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.tratamento_erros_externos.erro_generico import handle_erro_generico
from workers.tratamento_erros_externos.exceptions import BancoFalhouAposEnvioMeta
from workers.tratamento_erros_externos.unidade_nao_encontrada import handle_unidade_nao_encontrada
from workers.worker_flow.response_flow.flow_sender import flow_sender
from workers.worker_flow.suporte.cache_repair import (
    confirmar_cache_cliente_se_pendente,
    reparar_cache_cliente_stale_se_fk_invalida,
    reparar_cache_unidade_stale_se_fk_invalida,
)
from workers.worker_flow.suporte.estado_ciclo import (
    aguardar_fila_vazia,
    atualizar_estado_com_contexto,
    atualizar_estado_com_mensagem,
    atualizar_estado_lock,
    criar_estado_ciclo,
    montar_mensagem_fila,
)
from workers.worker_flow.transacoes.finalizacao_fila import (
    finalizar_mensagem_processada,
)
from workers.worker_flow.transacoes.lock_conversa import (
    liberar_lock_conversa_se_necessario,
)
from workers.worker_flow.transacoes.ordem_turno import (
    logar_lock_recusado,
    reagendar_se_houver_mensagem_anterior,
)
from workers.worker_flow.transacoes.persistencia_resposta import (
    atualizar_banco_com_contexto_final,
)
from workers.worker_flow.tratar_bloqueio import tratar_conversa_bloqueada
from workers.worker_flow.valida_banco import validar_banco_mensagem
from workers.worker_flow.valida_historico import valida_historico

logger = logging.getLogger("worker.response_flow")


def worker_flow():
    logger.info("worker_iniciado")

    max_retry = 3
    retry_delay = 5

    while True:
        print("\n\n\n---------------------NOVO CICLO---------------------\n\n\n")
        logger.info("---------- ciclo_worker_inicio ----------")

        conn_ciclo = None
        cursor_ciclo = None
        estado_ciclo = criar_estado_ciclo()
        contexto_envio = {}

        try:
            conn_ciclo = get_conn(application_name="worker_chatbot")
            cursor_ciclo = conn_ciclo.cursor()
            retry_delay = 5
            logger.debug("ciclo_conexao_banco_ok | acao=dequeue")

            registro = pegar_mensagens_da_fila(cursor_ciclo)
            conn_ciclo.commit()

            if not registro:
                conn_ciclo.close()
                conn_ciclo = None
                cursor_ciclo = None
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
                # TEMPORARIO: envio_simulado existe apenas enquanto a etapa 5
                # nao possui sender Meta. Remover esta excecao junto com a
                # simulacao quando o sender real for implementado.
                if (
                    contexto_envio.get("enviou")
                    and not contexto_envio.get("envio_simulado")
                ):
                    raise BancoFalhouAposEnvioMeta(
                        "Banco falhou depois da Meta confirmar envio",
                        id_mensagem=mensagem["id_mensagem"],
                        id_conversa=id_conversa,
                        id_hash_msg_bot=contexto_envio.get("id_hash_msg_bot"),
                        id_etapa=contexto_envio.get("id_etapa_resultante"),
                    ) from erro

                raise

            logger.debug(
                "resposta_bot_contexto_final_ok | acao=commit id_mensagem=%s id_conversa=%s etapa=%s resposta_ja_existia=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_final["id_etapa_resultante"],
                contexto_final["resposta_ja_existia"],
                contexto_final["id_hash_msg_bot"],
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
            )

            finalizar_mensagem_processada(
                mensagem,
                contexto_banco,
                contexto_final,
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
                "banco_falhou_apos_envio_meta | risco=resposta_duplicada acao=reagendar_sem_sent id_mensagem=%s id_conversa=%s etapa=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s erro=%s",
                erro.id_mensagem,
                erro.id_conversa,
                erro.id_etapa,
                erro.id_hash_msg_bot,
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
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

            reparar_cache_cliente_stale_se_fk_invalida(erro, estado_ciclo)
            reparar_cache_unidade_stale_se_fk_invalida(erro, estado_ciclo)

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

                except Exception as erro:
                    logger.exception(
                        "finalizacao_ciclo_falhou | acao=continuar_para_close erro=%s",
                        erro,
                    )

                finally:
                    try:
                        conn_ciclo.close()

                    except Exception as erro:
                        logger.exception(
                            "conexao_ciclo_close_falhou | acao=registrar_e_continuar erro=%s",
                            erro,
                        )
```

## Passo 22 - tests/unit/test_valida_etapa4.py

**Arquivo completo:** `tests/unit/test_valida_etapa4.py`

```python
import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    MOTIVO_FORMATO_INVALIDO,
    MOTIVO_FORA_INTERVALO,
    MOTIVO_MULTIPLAS_IDADES,
    MOTIVO_SEM_IDADE,
    STATUS_IDADE_ACIMA_LIMITE,
    STATUS_IDADE_INVALIDA,
    STATUS_IDADE_VALIDA,
    validar_idade,
)


class ValidaEtapa4Tests(unittest.TestCase):
    def test_extrai_uma_idade_numerica(self):
        casos = {
            "25": 25,
            "Eu tenho 25 anos de idade": 25,
            "Minha idade é 25 anos": 25,
            "Eu tenho 25": 25,
            "Ela tem 7": 7,
            "Alice tem 7 anos": 7,
        }

        for texto, idade in casos.items():
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertEqual(resultado.status, STATUS_IDADE_VALIDA)
                self.assertEqual(resultado.idade, idade)

    def test_extrai_uma_idade_por_extenso(self):
        casos = {
            "um ano de idade": 1,
            "dezoito": 18,
            "eu tenho trinta e nove anos": 39,
            "noventa e nove": 99,
        }

        for texto, idade in casos.items():
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertTrue(resultado.valida)
                self.assertEqual(resultado.idade, idade)

    def test_idade_acima_de_99_recebe_classificacao_propria(self):
        casos = {
            "100": 100,
            "105 anos": 105,
            "cem anos": 100,
            "cento e cinco": 105,
        }

        for texto, idade in casos.items():
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertEqual(
                    resultado.status,
                    STATUS_IDADE_ACIMA_LIMITE,
                )
                self.assertEqual(resultado.idade, idade)

    def test_duas_idades_sao_invalidas(self):
        casos = (
            "eu tenho 39 anos e meu filho tem 7",
            "trinta e nove e onze",
            "39 e onze",
            "39 e trinta e nove",
        )

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertEqual(resultado.status, STATUS_IDADE_INVALIDA)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_MULTIPLAS_IDADES,
                )

    def test_ausente_zero_negativa_e_decimal_sao_invalidas(self):
        casos = {
            "": MOTIVO_SEM_IDADE,
            "não sei": MOTIVO_SEM_IDADE,
            "0": MOTIVO_FORA_INTERVALO,
            "-1": MOTIVO_FORMATO_INVALIDO,
            "menos de 18": MOTIVO_FORMATO_INVALIDO,
            "18,5": MOTIVO_FORMATO_INVALIDO,
        }

        for texto, motivo in casos.items():
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertEqual(resultado.status, STATUS_IDADE_INVALIDA)
                self.assertEqual(resultado.motivo, motivo)


if __name__ == "__main__":
    unittest.main()
```

## Passo 23 - tests/unit/test_etapa4.py

**Arquivo completo:** `tests/unit/test_etapa4.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    etapa4_worker as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_IDADE_VALIDA,
)


def contexto_historico(
    texto,
    *,
    tipo_mensagem="text",
    status_dependente=False,
):
    return {
        "id_conversa": 10,
        "id_cliente": 20,
        "id_unidade": 30,
        "id_etapa_atual": 4,
        "id_etapa_cliente": 4,
        "id_etapa_origem_transicao": 4,
        "transicoes_permitidas": {EVENTO_IDADE_VALIDA: 5},
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
        "nome_dependente": "Alice" if status_dependente else None,
        "numero_comercial_unidade": "557536321234",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 40,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno_etapa4(**extra):
    resultado = {
        "enviou": True,
        "id_hash_msg_bot": "wamid.etapa4",
        "id_etapa_resultante": 4,
    }
    resultado.update(extra)
    return resultado


class Etapa4WorkerTests(unittest.TestCase):
    def test_idade_invalida_cliente_trata_sem_avancar(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_cliente_contexto_idade_invalida",
            return_value=retorno_etapa4(tratamento=True),
        ) as sender:
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("não sei")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertNotIn("evento_transicao", resultado)

    def test_idade_invalida_dependente_usa_mensagem_especifica(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_dependente_contexto_idade_invalida",
            return_value=retorno_etapa4(tratamento=True),
        ) as sender:
            resultado = etapa_module.resolve_etapa4(
                contexto_historico(
                    "39 e 7",
                    status_dependente=True,
                )
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "Alice",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertNotIn("evento_transicao", resultado)

    def test_cliente_menor_de_18_encerra(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_cliente_menor_18",
            return_value=retorno_etapa4(),
        ):
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("17")
            )

        self.assertTrue(resultado["encerrar_atendimento"])
        self.assertEqual(
            resultado["motivo_encerramento"],
            etapa_module.MOTIVO_CLIENTE_MENOR_18,
        )
        self.assertFalse(resultado["excluir_dependente"])

    def test_dependente_menor_de_5_encerra_e_exclui_dependente(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_dependente_menor_5",
            return_value=retorno_etapa4(),
        ):
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("4", status_dependente=True)
            )

        self.assertTrue(resultado["encerrar_atendimento"])
        self.assertTrue(resultado["excluir_dependente"])

    def test_idade_acima_de_99_usa_numero_comercial_e_encerra(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_idade_acima_99",
            return_value=retorno_etapa4(),
        ) as sender:
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("100")
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "557536321234",
        )
        self.assertTrue(resultado["encerrar_atendimento"])

    def test_cliente_18_avanca_para_etapa5(self):
        resultado = etapa_module.resolve_etapa4(
            contexto_historico("18")
        )

        self.assertTrue(resultado["envio_simulado"])
        self.assertEqual(resultado["id_etapa_resultante"], 5)
        self.assertEqual(resultado["evento_transicao"], EVENTO_IDADE_VALIDA)
        self.assertEqual(resultado["idade_aluno"], 18)

    def test_dependente_5_avanca_para_etapa5(self):
        resultado = etapa_module.resolve_etapa4(
            contexto_historico("5", status_dependente=True)
        )

        self.assertEqual(resultado["id_etapa_resultante"], 5)
        self.assertEqual(resultado["idade_aluno"], 5)


if __name__ == "__main__":
    unittest.main()
```

## Passo 24 - tests/unit/test_encerramento_etapa4.py

**Arquivo completo:** `tests/unit/test_encerramento_etapa4.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.transacoes import (
    encerramento_atendimento as encerramento,
)
from workers.worker_flow.transacoes import finalizacao_fila


def contexto_historico(texto, *, status_dependente=False):
    return {
        "id_conversa": 10,
        "id_etapa_origem_transicao": 4,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
    }


class EncerramentoEtapa4Tests(unittest.TestCase):
    def test_retry_reconstroi_encerramento_de_cliente_menor(self):
        resultado = encerramento.resolver_intencao_encerramento(
            contexto_historico("17"),
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 4,
            },
        )

        self.assertEqual(
            resultado,
            {
                "motivo": encerramento.MOTIVO_CLIENTE_MENOR_18,
                "excluir_dependente": False,
            },
        )

    def test_retry_reconstroi_exclusao_de_dependente_menor(self):
        resultado = encerramento.resolver_intencao_encerramento(
            contexto_historico("4", status_dependente=True),
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 4,
            },
        )

        self.assertEqual(
            resultado,
            {
                "motivo": encerramento.MOTIVO_DEPENDENTE_MENOR_5,
                "excluir_dependente": True,
            },
        )

    def test_idade_invalida_nao_inventa_encerramento_no_retry(self):
        resultado = encerramento.resolver_intencao_encerramento(
            contexto_historico("não sei"),
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 4,
            },
        )

        self.assertIsNone(resultado)

    def test_aplicacao_exclui_dependente_antes_de_encerrar(self):
        chamadas = []

        with patch.object(
            encerramento,
            "excluir_dependente_da_conversa",
            side_effect=lambda *_args: chamadas.append("excluir"),
        ), patch.object(
            encerramento,
            "encerrar_conversa",
            side_effect=lambda *_args: chamadas.append("encerrar"),
        ):
            aplicado = encerramento.aplicar_encerramento_se_necessario(
                10,
                {
                    "motivo": encerramento.MOTIVO_DEPENDENTE_MENOR_5,
                    "excluir_dependente": True,
                },
                object(),
            )

        self.assertTrue(aplicado)
        self.assertEqual(chamadas, ["excluir", "encerrar"])

    def test_finalizacao_aplica_encerramento_antes_do_sent(self):
        chamadas = []
        mensagem = {
            "id_mensagem": 20,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        }
        contexto_banco = {
            "id_unidade": 30,
            "conversa": {
                "id_conversa": 10,
                "estado": "ativa",
            },
        }
        contexto_final = {
            "intencao_encerramento": {
                "motivo": encerramento.MOTIVO_CLIENTE_MENOR_18,
                "excluir_dependente": False,
            }
        }

        with patch.object(
            finalizacao_fila,
            "aplicar_encerramento_se_necessario",
            side_effect=lambda *_args: chamadas.append("encerrar") or True,
        ), patch.object(
            finalizacao_fila,
            "marcar_mensagem_como_enviada",
            side_effect=lambda *_args: chamadas.append("sent"),
        ):
            finalizacao_fila.finalizar_mensagem_processada(
                mensagem,
                contexto_banco,
                contexto_final,
                lock_version=7,
                cursor=object(),
            )

        self.assertEqual(chamadas, ["encerrar", "sent"])


if __name__ == "__main__":
    unittest.main()
```

## Passo 25 - tests/unit/test_efeitos_etapa4.py

**Arquivo completo:** `tests/unit/test_efeitos_etapa4.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.transacoes import efeitos_transicao as efeitos
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_IDADE_VALIDA,
)


def contexto_historico(texto, *, status_dependente=False):
    return {
        "id_conversa": 10,
        "id_cliente": 20,
        "id_etapa_origem_transicao": 4,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
    }


def contexto_envio(**extra):
    resultado = {
        "id_etapa_resultante": 5,
        "evento_transicao": EVENTO_IDADE_VALIDA,
    }
    resultado.update(extra)
    return resultado


class EfeitosEtapa4Tests(unittest.TestCase):
    def test_transicao_quatro_para_cinco_salva_idade_do_cliente(self):
        with patch.object(
            efeitos,
            "atualizar_idade_cliente",
        ) as atualizar_cliente, patch.object(
            efeitos,
            "atualizar_idade_dependente",
        ) as atualizar_dependente:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico("18"),
                contexto_envio(idade_aluno=18),
                object(),
            )

        atualizar_cliente.assert_called_once()
        atualizar_dependente.assert_not_called()
        self.assertEqual(resultado["idade_aluno"], 18)
        self.assertEqual(resultado["destino_dado"], "cliente")

    def test_transicao_quatro_para_cinco_salva_idade_do_dependente(self):
        with patch.object(
            efeitos,
            "atualizar_idade_cliente",
        ) as atualizar_cliente, patch.object(
            efeitos,
            "atualizar_idade_dependente",
        ) as atualizar_dependente:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico("5", status_dependente=True),
                contexto_envio(idade_aluno=5),
                object(),
            )

        atualizar_cliente.assert_not_called()
        atualizar_dependente.assert_called_once()
        self.assertEqual(resultado["destino_dado"], "dependente")

    def test_retry_reconstroi_idade_da_mensagem_original(self):
        with patch.object(
            efeitos,
            "atualizar_idade_cliente",
        ) as atualizar_cliente:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico("Minha idade é trinta e nove"),
                contexto_envio(resposta_ja_existia=True),
                object(),
            )

        atualizar_cliente.assert_called_once()
        self.assertEqual(resultado["idade_aluno"], 39)


if __name__ == "__main__":
    unittest.main()
```

## Passo 26 - tests/unit/test_etapa2.py

**Arquivo completo:** `tests/unit/test_etapa2.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    etapa2_worker as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


def contexto_historico(
    *,
    tipo_mensagem="text",
    texto="Para mim",
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": 2,
        "id_etapa_cliente": 2,
        "id_etapa_resposta": None,
        "id_etapa_origem_transicao": 2,
        "transicoes_permitidas": {
            EVENTO_PARA_MIM: 4,
            EVENTO_PARA_OUTRA_PESSOA: 3,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno(nome):
    return {
        "nome": nome,
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.{nome}",
        "id_etapa_resultante": 2,
        "tratamento": True,
    }


class Etapa2WorkerTests(unittest.TestCase):
    def test_etapa2_com_midia_reenvia_etapa_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2_midia",
            return_value=retorno("midia_etapa2"),
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(tipo_mensagem="image", texto="")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_etapa2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_etapa2_com_financeiro_reenvia_etapa_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2_financeiro",
            return_value=retorno("financeiro_etapa2"),
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_etapa2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_midia_tem_prioridade_sobre_texto_financeiro(self):
        with (
            patch.object(
                etapa_module,
                "enviar_etapa2_midia",
                return_value=retorno("midia_etapa2"),
            ) as sender_midia,
            patch.object(
                etapa_module,
                "enviar_etapa2_financeiro",
            ) as sender_financeiro,
        ):
            etapa_module.resolve_etapa2(
                contexto_historico(
                    tipo_mensagem="image",
                    texto="quanto custa?",
                )
            )

        sender_midia.assert_called_once_with("5571999999999", "123456")
        sender_financeiro.assert_not_called()

    def test_opcao_para_mim_envia_etapa4_sem_dependente(self):
        contexto_sender = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.etapa4",
            "id_etapa_resultante": 4,
        }

        with patch.object(
            etapa_module,
            "enviar_etapa4_cliente",
            return_value=contexto_sender,
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(texto="Para mim")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertEqual(resultado["opcao_atendimento"], "para_mim")
        self.assertEqual(resultado["evento_transicao"], EVENTO_PARA_MIM)
        self.assertFalse(resultado["status_dependente"])

    def test_opcao_para_outra_pessoa_interativa_envia_etapa3(self):
        contexto_sender = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.etapa3",
            "id_etapa_resultante": 3,
        }

        with patch.object(
            etapa_module,
            "enviar_etapa3",
            return_value=contexto_sender,
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(
                    tipo_mensagem="interactive",
                    texto="Para outra pessoa",
                )
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(
            resultado["opcao_atendimento"],
            "para_outra_pessoa",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_PARA_OUTRA_PESSOA,
        )
        self.assertTrue(resultado["status_dependente"])

    def test_opcao_invalida_reenvia_etapa2_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2_contexto_opcao_invalida",
            return_value=retorno("contexto_etapa2"),
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(texto="eu quero para meu primo")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "contexto_etapa2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)


if __name__ == "__main__":
    unittest.main()
```

## Passo 27 - tests/unit/test_etapa3.py

**Arquivo completo:** `tests/unit/test_etapa3.py`

```python
import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    etapa3_worker as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_DEPENDENTE_VALIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    TransicaoEtapaInvalida,
)


def contexto_historico(
    *,
    tipo_mensagem="text",
    texto="Alice",
    transicoes=None,
):
    if transicoes is None:
        transicoes = {
            EVENTO_NOME_DEPENDENTE_VALIDO: 4,
        }

    return {
        "id_conversa": 10,
        "id_etapa_atual": 3,
        "id_etapa_cliente": 3,
        "id_etapa_resposta": 4,
        "id_etapa_origem_transicao": 3,
        "transicoes_permitidas": transicoes,
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno_tratamento(nome):
    return {
        "nome": nome,
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.{nome}",
        "id_etapa_resultante": 3,
        "tratamento": True,
    }


class Etapa3WorkerTests(unittest.TestCase):
    def test_midia_reenvia_etapa3_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa3_midia",
            return_value=retorno_tratamento("midia_etapa3"),
        ) as sender:
            resultado = etapa_module.resolve_etapa3(
                contexto_historico(tipo_mensagem="image", texto="")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertTrue(resultado["tratamento"])

    def test_financeiro_reenvia_etapa3_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa3_financeiro",
            return_value=retorno_tratamento("financeiro_etapa3"),
        ) as sender:
            resultado = etapa_module.resolve_etapa3(
                contexto_historico(texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertTrue(resultado["tratamento"])

    def test_midia_tem_prioridade_sobre_financeiro(self):
        with (
            patch.object(
                etapa_module,
                "enviar_etapa3_midia",
                return_value=retorno_tratamento("midia_etapa3"),
            ) as sender_midia,
            patch.object(
                etapa_module,
                "enviar_etapa3_financeiro",
            ) as sender_financeiro,
        ):
            etapa_module.resolve_etapa3(
                contexto_historico(
                    tipo_mensagem="image",
                    texto="quanto custa?",
                )
            )

        sender_midia.assert_called_once_with("5571999999999", "123456")
        sender_financeiro.assert_not_called()

    def test_nome_invalido_reenvia_etapa3_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa3_contexto_nome_invalido",
            return_value=retorno_tratamento("nome_invalido_etapa3"),
        ) as sender:
            resultado = etapa_module.resolve_etapa3(
                contexto_historico(texto="Alice99")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertTrue(resultado["tratamento"])

    def test_nome_valido_transiciona_para_etapa4(self):
        contexto_sender = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.etapa4",
            "id_etapa_resultante": 4,
        }

        with patch.object(
            etapa_module,
            "enviar_etapa4_dependente",
            return_value=contexto_sender,
        ) as sender:
            resultado = etapa_module.resolve_etapa3(
                contexto_historico(
                    texto="O nome da minha filha é Aline Braga"
                )
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            "Aline",
        )
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_NOME_DEPENDENTE_VALIDO,
        )
        self.assertEqual(resultado["primeiro_nome_dependente"], "Aline")

    def test_mapa_sem_aresta_recusa_avanco(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            etapa_module.resolve_etapa3(
                contexto_historico(
                    texto="Alice",
                    transicoes={},
                )
            )


if __name__ == "__main__":
    unittest.main()
```

## Passo 28 - tests/unit/test_flow_sender.py

**Arquivo completo:** `tests/unit/test_flow_sender.py`

```python
import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.flow_sender as flow_sender_module
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_IDADE_VALIDA,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


def contexto_historico_base(
    resposta_bot=None,
    etapa_atual=None,
    etapa_resposta=1,
    etapa_cliente=1,
    retry=1,
    transicoes=None,
):
    if transicoes is None:
        transicoes = {
            EVENTO_NOME_CLIENTE_VALIDO: 2,
        }

    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": etapa_cliente,
        "id_etapa_resposta": etapa_resposta,
        "id_etapa_origem_transicao": etapa_cliente,
        "transicoes_permitidas": transicoes,
        "retry_count": retry,
        "texto_cliente_atual": "Ola",
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


class FlowSenderTests(unittest.TestCase):
    def test_idempotente_nao_chama_etapa1_quando_resposta_ja_existe(self):
        def falhar_se_chamar(*_args, **_kwargs):
            raise AssertionError("primeira etapa nao deveria ser chamada")

        with patch.object(
            flow_sender_module,
            "resolve_etapa1",
            falhar_se_chamar,
        ):
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    resposta_bot={
                        "id_mensagem": 99,
                        "id_hash_msg": "wamid.bot.existente",
                        "id_etapa": 1,
                    }
                )
            )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.existente")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_retry_para_mim_reconstroi_evento_dois_para_quatro(self):
        resultado = flow_sender_module.flow_sender(
            contexto_historico_base(
                resposta_bot={
                    "id_mensagem": 100,
                    "id_hash_msg": "wamid.bot.idade",
                    "id_etapa": 4,
                },
                etapa_atual=4,
                etapa_cliente=2,
                retry=2,
                transicoes={
                    EVENTO_PARA_MIM: 4,
                    EVENTO_PARA_OUTRA_PESSOA: 3,
                },
            )
        )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["evento_transicao"], EVENTO_PARA_MIM)
        self.assertEqual(resultado["id_etapa_resultante"], 4)

    def test_retry_reconstroi_evento_nome_dependente_tres_para_quatro(self):
        resultado = flow_sender_module.flow_sender(
            contexto_historico_base(
                resposta_bot={
                    "id_mensagem": 101,
                    "id_hash_msg": "simulacao.etapa4",
                    "id_etapa": 4,
                },
                etapa_atual=4,
                etapa_cliente=3,
                retry=2,
                transicoes={
                    EVENTO_NOME_DEPENDENTE_VALIDO: 4,
                },
            )
        )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_NOME_DEPENDENTE_VALIDO,
        )
        self.assertEqual(resultado["id_etapa_resultante"], 4)

    def test_conversa_sem_etapa_vai_para_etapa1(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa1",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=None)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa1_vai_para_etapa1(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa1",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=1, etapa_resposta=2)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa2_vai_para_etapa2(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 2,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa2",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=2, etapa_resposta=3)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa3_vai_para_etapa3(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "simulacao.etapa4",
            "id_etapa_resultante": 4,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa3",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    etapa_atual=3,
                    etapa_resposta=4,
                )
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa4_vai_para_etapa4(self):
        esperado = {
            "enviou": True,
            "envio_simulado": True,
            "id_hash_msg_bot": "simulacao.etapa5",
            "id_etapa_resultante": 5,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa4",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    etapa_atual=4,
                    etapa_resposta=5,
                    etapa_cliente=4,
                    transicoes={EVENTO_IDADE_VALIDA: 5},
                )
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_nao_implementada_nao_finge_sucesso(self):
        with self.assertRaises(NotImplementedError):
            flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=5, etapa_resposta=6)
            )


if __name__ == "__main__":
    unittest.main()
```

## Passo 29 - tests/unit/test_messages_etapa4.py

**Arquivo completo:** `tests/unit/test_messages_etapa4.py`

```python
import unittest

from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_cliente_menor_18_etapa4,
    montar_mensagem_contexto_idade_dependente_invalida_etapa4,
    montar_mensagem_contexto_idade_invalida_etapa4,
    montar_mensagem_dependente_menor_5_etapa4,
    montar_mensagem_idade_dependente_etapa4,
    montar_mensagem_idade_dependente_etapa4_financeiro,
    montar_mensagem_idade_dependente_etapa4_midia,
    montar_mensagem_idade_etapa4,
    montar_mensagem_idade_etapa4_financeiro,
    montar_mensagem_idade_etapa4_midia,
    montar_mensagem_idade_acima_99_etapa4,
)


class MessagesEtapa4Tests(unittest.TestCase):
    def test_mensagem_acima_de_99_exibe_numero_comercial(self):
        mensagem = montar_mensagem_idade_acima_99_etapa4(
            "557536321234"
        )

        self.assertIn("557536321234", mensagem)

    def test_mensagem_acima_de_99_exige_numero_comercial(self):
        with self.assertRaises(ValueError):
            montar_mensagem_idade_acima_99_etapa4("")

    def test_mensagens_do_cliente_perguntam_a_propria_idade(self):
        mensagens = (
            montar_mensagem_idade_etapa4(),
            montar_mensagem_idade_etapa4_midia(),
            montar_mensagem_idade_etapa4_financeiro(),
            montar_mensagem_contexto_idade_invalida_etapa4(),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertIn("sua idade", mensagem)
                self.assertNotIn("{nome}", mensagem)

    def test_mensagens_do_dependente_interpolam_o_nome(self):
        mensagens = (
            montar_mensagem_idade_dependente_etapa4("Alice"),
            montar_mensagem_idade_dependente_etapa4_midia("Alice"),
            montar_mensagem_idade_dependente_etapa4_financeiro("Alice"),
            montar_mensagem_contexto_idade_dependente_invalida_etapa4(
                "Alice"
            ),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertIn("idade de Alice", mensagem)
                self.assertNotIn("{nome}", mensagem)

    def test_tratamento_de_contexto_orienta_resposta_numerica(self):
        self.assertIn(
            "Digite apenas o número",
            montar_mensagem_contexto_idade_invalida_etapa4(),
        )
        self.assertIn(
            "Digite apenas o número",
            montar_mensagem_contexto_idade_dependente_invalida_etapa4(
                "Alice"
            ),
        )

    def test_cliente_menor_de_idade_e_orientado_a_retornar_com_adulto(self):
        mensagem = montar_mensagem_cliente_menor_18_etapa4()

        self.assertIn("menos de 18 anos", mensagem)
        self.assertIn("adulto responsável", mensagem)
        self.assertIn("adulto", mensagem)
        self.assertNotIn("botão", mensagem)

    def test_dependente_menor_de_cinco_anos_recebe_orientacao(self):
        mensagem = montar_mensagem_dependente_menor_5_etapa4("Alice")

        self.assertIn("a partir de 5 anos", mensagem)
        self.assertIn("Quando Alice completar 5 anos", mensagem)
        self.assertNotIn("{nome}", mensagem)
        self.assertNotIn("botão", mensagem)


if __name__ == "__main__":
    unittest.main()
```

## Passo 30 - tests/unit/test_pywa_sender_etapa4.py

**Arquivo completo:** `tests/unit/test_pywa_sender_etapa4.py`

```python
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_cliente_menor_18_etapa4,
    montar_mensagem_contexto_idade_dependente_invalida_etapa4,
    montar_mensagem_contexto_idade_invalida_etapa4,
    montar_mensagem_dependente_menor_5_etapa4,
    montar_mensagem_idade_dependente_etapa4,
    montar_mensagem_idade_dependente_etapa4_financeiro,
    montar_mensagem_idade_dependente_etapa4_midia,
    montar_mensagem_idade_etapa4,
    montar_mensagem_idade_etapa4_financeiro,
    montar_mensagem_idade_etapa4_midia,
    montar_mensagem_idade_acima_99_etapa4,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa4 as sender_module,
)


class FakeClienteWa:
    def __init__(self, erro=None):
        self.calls = []
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return SimpleNamespace(id="wamid.bot.4")


class PywaSenderEtapa4Tests(unittest.TestCase):
    def _executar_sender(self, funcao, *args):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = funcao(
                "5571999999999",
                "123456",
                *args,
            )

        return cliente_wa, resultado

    def test_envios_normais_perguntam_idade_e_preservam_etapa4(self):
        casos = (
            (
                sender_module.enviar_etapa4_cliente,
                (),
                montar_mensagem_idade_etapa4(),
            ),
            (
                sender_module.enviar_etapa4_dependente,
                ("Alice",),
                montar_mensagem_idade_dependente_etapa4("Alice"),
            ),
        )

        for funcao, args, mensagem in casos:
            with self.subTest(funcao=funcao.__name__):
                cliente_wa, resultado = self._executar_sender(
                    funcao,
                    *args,
                )

                self.assertEqual(cliente_wa.calls[0]["text"], mensagem)
                self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.4")
                self.assertEqual(resultado["id_etapa_resultante"], 4)
                self.assertNotIn("tratamento", resultado)

    def test_tratamentos_preservam_etapa4(self):
        casos = (
            (
                sender_module.enviar_etapa4_cliente_midia,
                (),
                montar_mensagem_idade_etapa4_midia(),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa4_dependente_midia,
                ("Alice",),
                montar_mensagem_idade_dependente_etapa4_midia("Alice"),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa4_cliente_financeiro,
                (),
                montar_mensagem_idade_etapa4_financeiro(),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa4_dependente_financeiro,
                ("Alice",),
                montar_mensagem_idade_dependente_etapa4_financeiro(
                    "Alice"
                ),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa4_cliente_contexto_idade_invalida,
                (),
                montar_mensagem_contexto_idade_invalida_etapa4(),
                sender_module.TIPO_TRATAMENTO_IDADE_INVALIDA,
            ),
            (
                sender_module.enviar_etapa4_dependente_contexto_idade_invalida,
                ("Alice",),
                montar_mensagem_contexto_idade_dependente_invalida_etapa4(
                    "Alice"
                ),
                sender_module.TIPO_TRATAMENTO_IDADE_INVALIDA,
            ),
        )

        for funcao, args, mensagem, tipo_tratamento in casos:
            with self.subTest(funcao=funcao.__name__):
                cliente_wa, resultado = self._executar_sender(
                    funcao,
                    *args,
                )

                self.assertEqual(cliente_wa.calls[0]["text"], mensagem)
                self.assertEqual(resultado["id_etapa_resultante"], 4)
                self.assertTrue(resultado["tratamento"])
                self.assertEqual(
                    resultado["tipo_tratamento"],
                    tipo_tratamento,
                )

    def test_encerramentos_por_idade_nao_usam_botao_nem_tratamento(self):
        casos = (
            (
                sender_module.enviar_etapa4_cliente_menor_18,
                (),
                montar_mensagem_cliente_menor_18_etapa4(),
            ),
            (
                sender_module.enviar_etapa4_dependente_menor_5,
                ("Alice",),
                montar_mensagem_dependente_menor_5_etapa4("Alice"),
            ),
        )

        for funcao, args, mensagem in casos:
            with self.subTest(funcao=funcao.__name__):
                cliente_wa, resultado = self._executar_sender(
                    funcao,
                    *args,
                )

                self.assertEqual(
                    cliente_wa.calls[0],
                    {
                        "to": "5571999999999",
                        "text": mensagem,
                    },
                )
                self.assertNotIn("tratamento", resultado)
                self.assertEqual(resultado["id_etapa_resultante"], 4)

    def test_acima_de_99_envia_numero_comercial_sem_tratamento(self):
        cliente_wa, resultado = self._executar_sender(
            sender_module.enviar_etapa4_idade_acima_99,
            "557536321234",
        )

        self.assertEqual(
            cliente_wa.calls[0]["text"],
            montar_mensagem_idade_acima_99_etapa4("557536321234"),
        )
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertNotIn("tratamento", resultado)

    def test_meta_falhou_levanta_exception_controlada(self):
        cliente_wa = FakeClienteWa(
            erro=RuntimeError("meta indisponivel")
        )

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.enviar_etapa4_cliente(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(ctx.exception.id_etapa, 4)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
```

## Passo 31 - tests/unit/test_transicoes_etapa.py

**Arquivo completo:** `tests/unit/test_transicoes_etapa.py`

```python
import unittest

from core.repositories import transicoes_etapa
from tests.helpers import FakeCursor
from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    montar_contexto_transicao,
    prever_etapa_resposta,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_3_NOME_DEPENDENTE,
    ETAPA_4_IDADE_ALUNO,
    ETAPA_5_OFERTA_AULA,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    TransicaoEtapaInvalida,
    anexar_transicao_ao_contexto_envio,
    identificar_evento_por_destino,
    resolver_destino_transicao,
)


def contexto_transicoes():
    return {
        "id_etapa_origem_transicao": 2,
        "transicoes_permitidas": {
            EVENTO_PARA_MIM: ETAPA_4_IDADE_ALUNO,
            EVENTO_PARA_OUTRA_PESSOA: ETAPA_3_NOME_DEPENDENTE,
        },
    }


def contexto_transicao_etapa3():
    return {
        "id_etapa_origem_transicao": ETAPA_3_NOME_DEPENDENTE,
        "transicoes_permitidas": {
            EVENTO_NOME_DEPENDENTE_VALIDO: ETAPA_4_IDADE_ALUNO,
        },
    }


def contexto_transicao_etapa4():
    return {
        "id_etapa_origem_transicao": ETAPA_4_IDADE_ALUNO,
        "transicoes_permitidas": {
            EVENTO_IDADE_VALIDA: ETAPA_5_OFERTA_AULA,
        },
    }


class TransicoesEtapaTests(unittest.TestCase):
    def test_resultado_da_consulta_vira_contexto_explicito(self):
        transicoes = {
            EVENTO_PARA_MIM: ETAPA_4_IDADE_ALUNO,
            EVENTO_PARA_OUTRA_PESSOA: ETAPA_3_NOME_DEPENDENTE,
        }

        resultado = montar_contexto_transicao(2, transicoes)

        self.assertEqual(
            resultado,
            {
                "id_etapa_origem_transicao": 2,
                "transicoes_permitidas": transicoes,
            },
        )
        self.assertIsNot(
            resultado["transicoes_permitidas"],
            transicoes,
        )

    def test_previsao_nao_escolhe_entre_multiplos_destinos(self):
        resultado = prever_etapa_resposta(
            2,
            {
                EVENTO_PARA_MIM: ETAPA_4_IDADE_ALUNO,
                EVENTO_PARA_OUTRA_PESSOA: ETAPA_3_NOME_DEPENDENTE,
            },
            etapa_inicial=1,
        )

        self.assertIsNone(resultado)

    def test_repositorio_carrega_eventos_e_destinos(self):
        cursor = FakeCursor(
            fetchall_result=[
                (EVENTO_PARA_MIM, ETAPA_4_IDADE_ALUNO),
                (
                    EVENTO_PARA_OUTRA_PESSOA,
                    ETAPA_3_NOME_DEPENDENTE,
                ),
            ]
        )

        resultado = transicoes_etapa.listar_transicoes_permitidas(
            2,
            cursor,
        )

        self.assertEqual(
            resultado,
            {
                EVENTO_PARA_MIM: ETAPA_4_IDADE_ALUNO,
                EVENTO_PARA_OUTRA_PESSOA: ETAPA_3_NOME_DEPENDENTE,
            },
        )
        sql, params = cursor.calls[0]
        self.assertIn("FROM chatbot.etapa_transicao", sql)
        self.assertIn("WHERE id_etapa_origem = %s", sql)
        self.assertEqual(params, (2,))

    def test_para_mim_resolve_etapa4(self):
        destino = resolver_destino_transicao(
            contexto_transicoes(),
            EVENTO_PARA_MIM,
            destinos_esperados={ETAPA_4_IDADE_ALUNO},
        )

        self.assertEqual(destino, ETAPA_4_IDADE_ALUNO)

    def test_para_outra_pessoa_resolve_etapa3(self):
        destino = resolver_destino_transicao(
            contexto_transicoes(),
            EVENTO_PARA_OUTRA_PESSOA,
            destinos_esperados={ETAPA_3_NOME_DEPENDENTE},
        )

        self.assertEqual(destino, ETAPA_3_NOME_DEPENDENTE)

    def test_nome_dependente_valido_resolve_etapa4(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa3(),
            EVENTO_NOME_DEPENDENTE_VALIDO,
            destinos_esperados={ETAPA_4_IDADE_ALUNO},
        )

        self.assertEqual(destino, ETAPA_4_IDADE_ALUNO)

    def test_idade_valida_resolve_etapa5(self):
        destino = resolver_destino_transicao(
            contexto_transicao_etapa4(),
            EVENTO_IDADE_VALIDA,
            destinos_esperados={ETAPA_5_OFERTA_AULA},
        )

        self.assertEqual(destino, ETAPA_5_OFERTA_AULA)

    def test_evento_ausente_e_recusado_antes_do_envio(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            resolver_destino_transicao(
                contexto_transicoes(),
                "evento_inventado",
            )

    def test_destino_trocado_no_seed_e_recusado(self):
        contexto = contexto_transicoes()
        contexto["transicoes_permitidas"][EVENTO_PARA_MIM] = 3

        with self.assertRaises(TransicaoEtapaInvalida):
            resolver_destino_transicao(
                contexto,
                EVENTO_PARA_MIM,
                destinos_esperados={ETAPA_4_IDADE_ALUNO},
            )

    def test_sender_nao_pode_retornar_destino_diferente(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            anexar_transicao_ao_contexto_envio(
                contexto_transicoes(),
                {
                    "id_etapa_resultante": 3,
                    "enviou": True,
                },
                EVENTO_PARA_MIM,
                ETAPA_4_IDADE_ALUNO,
            )

    def test_tratamento_nao_pode_carregar_evento(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            anexar_transicao_ao_contexto_envio(
                contexto_transicoes(),
                {
                    "id_etapa_resultante": ETAPA_4_IDADE_ALUNO,
                    "enviou": True,
                    "tratamento": True,
                },
                EVENTO_PARA_MIM,
                ETAPA_4_IDADE_ALUNO,
            )

    def test_retry_reconstroi_evento_pelo_destino(self):
        evento = identificar_evento_por_destino(
            contexto_transicoes(),
            ETAPA_4_IDADE_ALUNO,
        )

        self.assertEqual(evento, EVENTO_PARA_MIM)

    def test_resposta_na_mesma_etapa_nao_inventa_transicao(self):
        evento = identificar_evento_por_destino(
            contexto_transicoes(),
            2,
        )

        self.assertIsNone(evento)


if __name__ == "__main__":
    unittest.main()
```

## Passo 32 - tests/unit/test_deploy_contract.py

**Arquivo completo:** `tests/unit/test_deploy_contract.py`

```python
import inspect
import unittest

from core.database.deploy import (
    bank_script,
    etapa_transicao_script,
    setup_database,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


class DeployContractTests(unittest.TestCase):
    def test_banco_novo_nasce_com_last_error_sem_alterar_banco(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("last_error TEXT", source)
        self.assertFalse(hasattr(bank_script, "alterar_banco"))

    def test_setup_nao_chama_migracao_historica_alterar_banco(self):
        source = inspect.getsource(setup_database.setup_database_aws)

        self.assertNotIn("alterar_banco", source)
        self.assertIn("criar_tabelas()", source)

    def test_respostas_desafios_existe_no_ddl_com_unique_turno(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios", source)
        self.assertIn("UNIQUE (id_conversa, id_etapa)", source)
        self.assertIn("id_historico_mensagem_cliente INT NULL", source)

    def test_cliente_e_dependente_possuem_idade_e_conversa_vinculada(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("ADD COLUMN IF NOT EXISTS idade INTEGER", source)
        self.assertIn("ADD COLUMN IF NOT EXISTS id_conversa INT", source)
        self.assertIn("dependente_id_conversa_fkey", source)
        self.assertIn("uq_dependente_conversa", source)

    def test_tabela_transicao_possui_restricoes_de_seguranca(self):
        source = inspect.getsource(
            etapa_transicao_script.criar_e_povoar_transicoes_etapa
        )

        self.assertIn("CHECK (id_etapa_origem <> id_etapa_destino)", source)
        self.assertIn("UNIQUE (id_etapa_origem, evento)", source)
        self.assertIn(
            "UNIQUE (id_etapa_origem, id_etapa_destino)",
            source,
        )
        self.assertIn("DELETE FROM chatbot.etapa_transicao", source)

    def test_seed_de_transicoes_reflete_o_mapa_da_v1(self):
        self.assertEqual(
            etapa_transicao_script.TRANSICOES_INICIAIS,
            (
                (1, EVENTO_NOME_CLIENTE_VALIDO, 2),
                (2, EVENTO_PARA_MIM, 4),
                (2, EVENTO_PARA_OUTRA_PESSOA, 3),
                (3, EVENTO_NOME_DEPENDENTE_VALIDO, 4),
                (4, EVENTO_IDADE_VALIDA, 5),
            ),
        )


if __name__ == "__main__":
    unittest.main()
```

## Validacao obrigatoria apos a futura aplicacao

```powershell
python -m compileall callback core workers tests
python callback/manage.py check
python -m unittest discover -s tests -p "test_*.py"
```

A previa isolada usada para gerar este plano passou por compileall e por 93 testes focados em etapas 2, 3, 4, transicoes, persistencia, encerramento, worker, mensagens e senders.

## Fora do escopo

- Sender e mensagem definitivos da etapa 5.
- Mudanca no bloqueio de 30 dias da etapa 7.
- Exclusao do cliente, da fila ou do historico.
- Cache para numero_comercial.
- Mudanca no numero de workers ou na politica geral de retry.
