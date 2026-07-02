# Plano de implementação: políticas escaláveis de etapa

## Objetivo

Substituir decisões fixadas no número da etapa final por propriedades declaradas em `chatbot.etapa`, mantendo o comportamento atual:

- a etapa 7 continua sendo a etapa final atual;
- chegar à etapa final encerra a conversa;
- uma conversa encerrada na etapa final continua bloqueada por 30 dias;
- somente conversas finalizadas em etapa elegível entram na seleção do funil;
- encerramentos antecipados da etapa 4 não entram no funil e não bloqueiam nova conversa;
- tratamentos de idade inválida continuam ativos na etapa 4 e não encerram a conversa;
- mídia, financeiro, idade ausente, dupla, zero, negativa ou decimal continuam usando os tratamentos existentes;
- cliente menor de 18, dependente menor de 5 e idade acima de 99 continuam encerrando antecipadamente;
- idempotência, retries, regra de turno, locks, commits e ordem da fila permanecem inalterados.

## Modelo proposto

A tabela `etapa` passa a declarar:

```text
encerra_automaticamente BOOLEAN
bloqueio_dias INTEGER
elegivel_funil BOOLEAN
```

A etapa 7 atual será semeada como:

```text
encerra_automaticamente = TRUE
bloqueio_dias = 30
elegivel_funil = TRUE
```

As etapas 1 a 6 serão semeadas com `FALSE`, `0`, `FALSE`.

A etapa 4 continua comum no catálogo. Seus encerramentos por idade permanecem decisões explícitas de `etapa4_worker.py`; por isso, quando encerrada antecipadamente, ela possui `bloqueio_dias = 0` e `elegivel_funil = FALSE`.

## Separação de responsabilidades

- `povoar_etapas.py`: fonte declarativa das políticas de cada etapa.
- `politicas_etapa.py`: consultas SQL exclusivas das políticas e bloqueios.
- `encerramento_atendimento.py`: interpreta se a etapa de destino encerra automaticamente.
- `funil.py`: seleciona e confirma somente conversas encerradas em etapas elegíveis.
- `cache_conversas_bloqueadas.py`: replica no Redis o prazo retornado pelo PostgreSQL; não inventa prazo próprio.
- `flow_worker.py`: não será alterado.
- `post_flow.py`: não será alterado.

## Compatibilidade e falhas

- O cache continua sendo consultado primeiro.
- Em Redis indisponível, o PostgreSQL continua sendo o fallback existente.
- O Redis armazena `bloqueio_dias` e calcula o TTL a partir de `finalizou_em`.
- Uma política de etapa inexistente gera erro e retry; o sistema não presume silenciosamente uma finalização.
- Encerramento da conversa e marcação da fila como `sent` continuam na mesma transação final.
- A consulta do funil usa índice parcial e `lead_no_funil IS NOT TRUE`.
- O update do funil revalida conversa inativa, finalizada e etapa elegível.
- O envio externo ao funil e o job periódico continuam fora deste plano.
- O DDL preserva a política atual da etapa 7 antes do seed, evitando abertura indevida se um deploy parcial falhar.

## Matriz de equivalência dos fluxos

### Fluxo normal

```text
mensagem válida
-> webhook enfileira
-> worker processa
-> sender envia
-> banco persiste resposta e transição
-> política da etapa de destino é consultada
-> se não final: fluxo permanece igual
-> se final: conversa é encerrada
-> fila vira sent
```

### Meta falha antes do envio

Permanece `ErroEnvioMeta`: rollback, mensagem sem `sent` e retry. Nenhuma política de etapa altera esse caminho.

### Meta envia e o banco falha

Permanece `BancoFalhouAposEnvioMeta`: rollback da transação final, fila sem `sent` e retry. O risco raro de duplicidade continua o mesmo já documentado na V1.

### Banco confirma resposta e o worker cai antes do `sent`

No retry, o histórico reutiliza a etapa original da mensagem do cliente, `resposta_bot_atual` impede novo envio e o evento é reconstruído pelo mesmo mapa origem/destino. Se o destino for final, a intenção de encerramento também é reconstruída antes de marcar `sent`.

### Fila A/B/C

O plano não altera webhook, regra de turno, `ordem_turno.py`, advisory lock, dequeue nem vínculo fila/conversa:

```text
A sem resposta -> B não entra
A respondida -> B pode entrar
A ainda aberta -> B aguarda no worker
A vira sent -> B pode processar
B sem resposta -> C não entra
```

### Etapa 4

```text
mídia/financeiro/idade incompreensível
-> tratamento
-> permanece na etapa 4
-> conversa continua ativa

cliente < 18
dependente < 5
idade > 99
-> mensagem específica
-> conversa inativa na etapa 4
-> bloqueio_dias = 0
-> nova mensagem inicia nova conversa
```

### Etapa final

```text
sender final confirmado
-> conversa recebe etapa final
-> encerra_automaticamente = true
-> status_ativa = false
-> finalizou_em preenchido
-> bloqueio_dias = 30
-> elegível ao funil
```

### Redis e funções periódicas

As funções periódicas e jobs existentes não são alterados. O futuro job do funil ainda não será criado. As chaves Redis existentes continuam com o mesmo prefixo; para a política atual de 30 dias, chaves antigas e novas mantêm comportamento equivalente.

## Arquivos completos
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
            nome_etapa VARCHAR(100) UNIQUE NOT NULL,
            encerra_automaticamente BOOLEAN NOT NULL DEFAULT FALSE,
            bloqueio_dias INTEGER NOT NULL DEFAULT 0,
            elegivel_funil BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT ck_etapa_bloqueio_dias
                CHECK (bloqueio_dias >= 0)
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

        CREATE INDEX IF NOT EXISTS idx_conversa_funil_pendente
        ON chatbot.conversa (id_etapa_atual, finalizou_em)
        WHERE status_ativa = FALSE
          AND lead_no_funil IS NOT TRUE;

        -- CAMPOS DA TRANSICAO ENTRE AS ETAPAS 2 E 3.
        -- Os ALTERs mantem o setup idempotente tambem em bancos ja existentes.
        ALTER TABLE chatbot.cliente
        ADD COLUMN IF NOT EXISTS idade INTEGER;

        ALTER TABLE chatbot.unidade
        ADD COLUMN IF NOT EXISTS numero_comercial VARCHAR(30);

        -- POLITICAS DE COMPORTAMENTO DAS ETAPAS.
        -- Os defaults reproduzem uma etapa comum: não encerra, não bloqueia
        -- e não envia ao funil até o seed declarar expressamente o contrário.
        ALTER TABLE chatbot.etapa
        ADD COLUMN IF NOT EXISTS encerra_automaticamente
            BOOLEAN NOT NULL DEFAULT FALSE;

        ALTER TABLE chatbot.etapa
        ADD COLUMN IF NOT EXISTS bloqueio_dias
            INTEGER NOT NULL DEFAULT 0;

        ALTER TABLE chatbot.etapa
        ADD COLUMN IF NOT EXISTS elegivel_funil
            BOOLEAN NOT NULL DEFAULT FALSE;

        UPDATE chatbot.etapa
        SET
            encerra_automaticamente = COALESCE(
                encerra_automaticamente,
                FALSE
            ),
            bloqueio_dias = COALESCE(bloqueio_dias, 0),
            elegivel_funil = COALESCE(elegivel_funil, FALSE);

        ALTER TABLE chatbot.etapa
        ALTER COLUMN encerra_automaticamente SET NOT NULL,
        ALTER COLUMN bloqueio_dias SET NOT NULL,
        ALTER COLUMN elegivel_funil SET NOT NULL;

        -- Proteção para deploy parcial: a regra atual da etapa 7 já fica
        -- preservada nesta mesma transação, antes mesmo da execução do seed.
        UPDATE chatbot.etapa
        SET
            encerra_automaticamente = TRUE,
            bloqueio_dias = 30,
            elegivel_funil = TRUE
        WHERE id_etapa = 7;

        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'ck_etapa_bloqueio_dias'
                  AND conrelid = 'chatbot.etapa'::regclass
            ) THEN
                ALTER TABLE chatbot.etapa
                ADD CONSTRAINT ck_etapa_bloqueio_dias
                CHECK (bloqueio_dias >= 0);
            END IF;
        END
        $$;

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

## Passo 2 - core/database/deploy/povoar_etapas.py

**Arquivo completo:** `core/database/deploy/povoar_etapas.py`

```python
import logging

from core.database.connection_aws import get_conn


logger = logging.getLogger("db.seed")


ETAPAS = (
    (1, "Saudação e nome do cliente", False, 0, False),
    (2, "Destino do atendimento", False, 0, False),
    (3, "Nome do dependente", False, 0, False),
    (4, "Idade do aluno", False, 0, False),
    (
        5,
        "Oferta de aula experimental e avaliação cognitiva",
        False,
        0,
        False,
    ),
    (6, "Email", False, 0, False),
    (
        7,
        "Link de agendamento e entrada no funil",
        True,
        30,
        True,
    ),
)


def insere_etapa_once():
    conn = None

    try:
        conn = get_conn(application_name="script_chatbot")
        cursor = conn.cursor()

        cursor.executemany(
            """
            INSERT INTO chatbot.etapa (
                id_etapa,
                nome_etapa,
                encerra_automaticamente,
                bloqueio_dias,
                elegivel_funil
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (id_etapa)
            DO UPDATE SET
                nome_etapa = EXCLUDED.nome_etapa,
                encerra_automaticamente =
                    EXCLUDED.encerra_automaticamente,
                bloqueio_dias = EXCLUDED.bloqueio_dias,
                elegivel_funil = EXCLUDED.elegivel_funil;
            """,
            ETAPAS,
        )

        cursor.execute(
            """
            SELECT setval(
                pg_get_serial_sequence('chatbot.etapa', 'id_etapa'),
                (SELECT MAX(id_etapa) FROM chatbot.etapa),
                TRUE
            );
            """
        )

        conn.commit()
        logger.info(
            "banco_seed_ok | acao=sincronizar_etapas quantidade=%s",
            len(ETAPAS),
        )

    except Exception as erro:
        if conn:
            conn.rollback()
        logger.exception(
            "banco_seed_erro | acao=sincronizar_etapas erro=%s",
            erro,
        )
        raise

    finally:
        if conn:
            conn.close()
```

## Passo 3 - callback/webhook/models.py

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
    encerra_automaticamente = models.BooleanField(default=False)
    bloqueio_dias = models.PositiveIntegerField(default=0)
    elegivel_funil = models.BooleanField(default=False)

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

## Passo 4 - callback/webhook/admin.py

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
        "encerra_automaticamente",
        "bloqueio_dias",
        "elegivel_funil",
    )

    search_fields = ("nome_etapa",)
    list_filter = (
        "encerra_automaticamente",
        "elegivel_funil",
    )
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

## Passo 5 - core/repositories/politicas_etapa.py

**Arquivo completo:** `core/repositories/politicas_etapa.py`

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class PoliticaEtapa:
    id_etapa: int
    encerra_automaticamente: bool
    bloqueio_dias: int
    elegivel_funil: bool


@dataclass(frozen=True)
class BloqueioConversa:
    finalizou_em: datetime
    bloqueio_dias: int


def buscar_politica_etapa(id_etapa, cursor):
    cursor.execute(
        """
        SELECT
            id_etapa,
            encerra_automaticamente,
            bloqueio_dias,
            elegivel_funil
        FROM chatbot.etapa
        WHERE id_etapa = %s
        LIMIT 1;
        """,
        (id_etapa,),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            f"Política da etapa {id_etapa} não encontrada"
        )

    return PoliticaEtapa(
        id_etapa=resultado[0],
        encerra_automaticamente=bool(resultado[1]),
        bloqueio_dias=int(resultado[2] or 0),
        elegivel_funil=bool(resultado[3]),
    )


def buscar_bloqueio_conversa_por_id(id_conversa, cursor):
    cursor.execute(
        """
        SELECT
            c.finalizou_em,
            e.bloqueio_dias
        FROM chatbot.conversa c
        JOIN chatbot.etapa e
          ON e.id_etapa = c.id_etapa_atual
        WHERE c.id_conversa = %s
          AND c.status_ativa = FALSE
          AND c.finalizou_em IS NOT NULL
          AND e.bloqueio_dias > 0
        LIMIT 1;
        """,
        (id_conversa,),
    )

    return _montar_bloqueio(cursor.fetchone())


def buscar_bloqueio_ativo_por_cliente_unidade(
    cliente_telefone,
    id_phone_unidade,
    cursor,
):
    cursor.execute(
        """
        SELECT
            c.finalizou_em,
            e.bloqueio_dias
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u
          ON u.id_unidade = c.id_unidade
        JOIN chatbot.etapa e
          ON e.id_etapa = c.id_etapa_atual
        WHERE cl.waid_telefone = %s
          AND u.phone_number_id = %s
          AND u.status_pagamento = TRUE
          AND c.status_ativa = FALSE
          AND c.finalizou_em IS NOT NULL
          AND e.bloqueio_dias > 0
          AND c.finalizou_em
              > NOW() - (e.bloqueio_dias * INTERVAL '1 day')
        ORDER BY c.finalizou_em DESC
        LIMIT 1;
        """,
        (cliente_telefone, id_phone_unidade),
    )

    return _montar_bloqueio(cursor.fetchone())


def _montar_bloqueio(resultado):
    if not resultado:
        return None

    return BloqueioConversa(
        finalizou_em=resultado[0],
        bloqueio_dias=int(resultado[1]),
    )
```

## Passo 6 - core/repositories/querys.py

**Arquivo completo:** `core/repositories/querys.py`

```python
import logging


logger = logging.getLogger("db.querys")

"""Aqui nao so existe querys de consulta mas tambem querys que
chama funcoes SQL, na duvida consulte Bankscript.py"""


def pegar_unidades(cursor):
    cursor.execute("""
        SELECT phone_number_id, id_unidade
        FROM chatbot.unidade
        WHERE status_pagamento = TRUE
    """)

    resultado = {row[0]: row[1] for row in cursor.fetchall()}

    logger.debug("unidades_consultadas | total=%s", len(resultado))

    return resultado


def buscar_unidades_para_listagem_bloqueios(cursor):
    cursor.execute("""
        SELECT id_unidade, nome, phone_number_id
        FROM chatbot.unidade
        WHERE phone_number_id IS NOT NULL
          AND phone_number_id <> ''
        ORDER BY id_unidade;
    """)

    return cursor.fetchall()


def pegar_mensagens_da_fila(cursor):
    cursor.execute("SELECT * FROM chatbot.dequeue_message();")
    registro = cursor.fetchone()
    if registro:
        logger.debug("fila_dequeue | acao=reservar id_mensagem=%s", registro[0])
    return registro


def buscar_id_unidade_por_phone_id(phone_number_id, cursor):
    cursor.execute("""
        SELECT id_unidade
        FROM chatbot.unidade
        WHERE phone_number_id = %s
          AND status_pagamento = TRUE
    """, (phone_number_id,))

    result = cursor.fetchone()
    logger.debug(
        "unidade_consulta | acao=buscar_por_phone phone_number_id=%s encontrada=%s",
        phone_number_id,
        bool(result),
    )
    return result[0] if result else None


def buscar_last_message_from_conversa(cliente_telefone, id_phone_unidade, cursor):
    cursor.execute("""
        SELECT c.last_message_from
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
        WHERE cl.waid_telefone = %s
          AND u.phone_number_id = %s
          AND c.status_ativa = TRUE
        LIMIT 1;
    """, (cliente_telefone, id_phone_unidade))

    resultado = cursor.fetchone()
    logger.debug(
        "conversa_consulta | acao=last_message_from cliente=%s phone_number_id=%s encontrada=%s",
        cliente_telefone,
        id_phone_unidade,
        bool(resultado),
    )
    return resultado[0] if resultado else None


def tentar_lock_conversa(id_conversa, cursor):
    cursor.execute("SELECT lock_ok, lock_version_atual FROM chatbot.lock_conversa(%s);", (id_conversa,))
    resultado = cursor.fetchone()

    if not resultado:
        logger.warning(
            "conversa_lock_sem_retorno | acao=negar_lock id_conversa=%s",
            id_conversa,
        )
        return False, None

    logger.debug(
        "conversa_lock_resultado | acao=lock id_conversa=%s lock_ok=%s lock_version=%s",
        id_conversa,
        bool(resultado[0]),
        resultado[1],
    )
    return bool(resultado[0]), resultado[1]


def unlock_conversa(id_conversa, lock_version, cursor):
    if lock_version is None:
        return False

    cursor.execute("SELECT chatbot.unlock_conversa(%s, %s);", (id_conversa, lock_version))
    resultado = cursor.fetchone()
    logger.debug(
        "conversa_unlock_resultado | acao=unlock id_conversa=%s lock_version=%s liberada=%s",
        id_conversa,
        lock_version,
        bool(resultado[0]) if resultado else False,
    )
    return bool(resultado[0]) if resultado else False


def buscar_estado_conversa(id_cliente, id_unidade, cursor):
    cursor.execute("""
        WITH conversa_ativa AS (
            SELECT
                id_conversa,
                id_etapa_atual,
                status_ativa,
                finalizou_em,
                'ativa' AS estado,
                status_dependente,
                last_message_from,
                followup_stage,
                followup_last_sent_at,
                lead_no_funil
            FROM chatbot.conversa
            WHERE id_cliente = %s
              AND id_unidade = %s
              AND status_ativa = TRUE
            LIMIT 1
        ),
        ultima_conversa AS (
            SELECT
                c.id_conversa,
                c.id_etapa_atual,
                c.status_ativa,
                c.finalizou_em,
                CASE
                    WHEN COALESCE(e.bloqueio_dias, 0) > 0
                     AND c.finalizou_em
                         > NOW() - (
                             COALESCE(e.bloqueio_dias, 0)
                             * INTERVAL '1 day'
                         )
                    THEN 'bloqueada'
                    ELSE 'liberada'
                END AS estado,
                c.status_dependente,
                c.last_message_from,
                c.followup_stage,
                c.followup_last_sent_at,
                c.lead_no_funil
            FROM chatbot.conversa c
            LEFT JOIN chatbot.etapa e
              ON e.id_etapa = c.id_etapa_atual
            WHERE c.id_cliente = %s
              AND c.id_unidade = %s
              AND c.status_ativa = FALSE
            ORDER BY c.finalizou_em DESC
            LIMIT 1
        )
        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado,
            status_dependente,
            last_message_from,
            followup_stage,
            followup_last_sent_at,
            lead_no_funil
        FROM conversa_ativa

        UNION ALL

        SELECT
            id_conversa,
            id_etapa_atual,
            status_ativa,
            finalizou_em,
            estado,
            status_dependente,
            last_message_from,
            followup_stage,
            followup_last_sent_at,
            lead_no_funil
        FROM ultima_conversa
        WHERE NOT EXISTS (SELECT 1 FROM conversa_ativa)

        LIMIT 1;
    """, (id_cliente, id_unidade, id_cliente, id_unidade))

    resultado = cursor.fetchone()
    logger.debug(
        "conversa_estado_consultado | acao=buscar_estado id_cliente=%s id_unidade=%s encontrada=%s estado=%s",
        id_cliente,
        id_unidade,
        bool(resultado),
        resultado[4] if resultado else None,
    )
    return resultado


def existe_mensagem_anterior_aberta_conversa(
    id_conversa,
    id_mensagem_atual,
    received_data_hora,
    cursor,
):
    if id_conversa is None:
        return False

    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM chatbot.fila_mensagens
            WHERE id_conversa = %s
              AND id_mensagem <> %s
              AND status IN ('pending', 'processing')
              AND (
                  received_data_hora < %s
                  OR (
                      received_data_hora = %s
                      AND id_mensagem < %s
                  )
              )
            LIMIT 1
        );
    """, (
        id_conversa,
        id_mensagem_atual,
        received_data_hora,
        received_data_hora,
        id_mensagem_atual,
    ))

    resultado = bool(cursor.fetchone()[0])
    logger.debug(
        "fila_ordem_consultada | acao=verificar_anterior id_conversa=%s id_mensagem=%s existe_anterior=%s",
        id_conversa,
        id_mensagem_atual,
        resultado,
    )
    return resultado


def buscar_ultimas_mensagens_historico(id_conversa, cursor, limite=6):
    cursor.execute("""
        SELECT
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
            status_envio
        FROM chatbot.historico_mensagens
        WHERE id_conversa = %s
        ORDER BY received_data_hora DESC, id_mensagem DESC
        LIMIT %s;
    """, (id_conversa, limite))

    resultados = cursor.fetchall()
    logger.debug(
        "historico_consultado | acao=buscar_ultimas id_conversa=%s total=%s limite=%s",
        id_conversa,
        len(resultados),
        limite,
    )
    return resultados


def buscar_historico_cliente_por_mensagem_fila(
    id_conversa,
    id_mensagem_fila,
    id_hash_msg,
    cursor,
):
    cursor.execute("""
        SELECT
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
            status_envio
        FROM chatbot.historico_mensagens
        WHERE id_conversa = %s
          AND quem_enviou = 'cliente'
          AND id_mensagem_fila = %s
          AND id_hash_msg = %s
        ORDER BY received_data_hora DESC, id_mensagem DESC
        LIMIT 1;
    """, (id_conversa, id_mensagem_fila, id_hash_msg))

    resultado = cursor.fetchone()
    logger.debug(
        "historico_cliente_consultado | acao=buscar_por_fila id_conversa=%s id_mensagem_fila=%s encontrado=%s",
        id_conversa,
        id_mensagem_fila,
        bool(resultado),
    )
    return resultado


def buscar_resposta_bot_por_mensagem_cliente(
    id_conversa,
    id_mensagem_fila,
    id_hash_cliente_origem,
    cursor,
):
    cursor.execute("""
        SELECT
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
            status_envio
        FROM chatbot.historico_mensagens
        WHERE id_conversa = %s
          AND quem_enviou = 'bot'
          AND id_mensagem_fila = %s
          AND id_hash_cliente_origem = %s
        ORDER BY received_data_hora DESC, id_mensagem DESC
        LIMIT 1;
    """, (id_conversa, id_mensagem_fila, id_hash_cliente_origem))

    resultado = cursor.fetchone()
    logger.debug(
        "historico_bot_consultado | acao=buscar_resposta_por_origem id_conversa=%s id_mensagem_fila=%s encontrado=%s",
        id_conversa,
        id_mensagem_fila,
        bool(resultado),
    )
    return resultado


# def buscar_conversa_ativa(id_cliente, id_unidade, cursor):
#     """
#     Busca a conversa ativa pelo cliente e unidade correspondentes.
#     Retorna todos os campos da tabela conversa.
#     """
#     cursor.execute("""
#         SELECT c.*
#         FROM chatbot.conversa c
#         WHERE c.id_cliente = %s
#           AND c.id_unidade = %s
#           AND c.status_ativa = TRUE
#         LIMIT 1;
#     """, (id_cliente, id_unidade))
#
#     return cursor.fetchone()
```

## Passo 7 - core/repositories/funil.py

**Arquivo completo:** `core/repositories/funil.py`

```python
def listar_conversas_pendentes_funil(
    cursor,
    *,
    limite=100,
):
    if not isinstance(limite, int) or limite <= 0:
        raise ValueError("limite deve ser um inteiro positivo")

    cursor.execute(
        """
        SELECT c.id_conversa
        FROM chatbot.conversa c
        JOIN chatbot.etapa e
          ON e.id_etapa = c.id_etapa_atual
        WHERE c.status_ativa = FALSE
          AND c.finalizou_em IS NOT NULL
          AND e.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        ORDER BY c.finalizou_em ASC, c.id_conversa ASC
        LIMIT %s;
        """,
        (limite,),
    )

    return [linha[0] for linha in cursor.fetchall()]


def marcar_conversa_como_enviada_ao_funil(id_conversa, cursor):
    cursor.execute(
        """
        UPDATE chatbot.conversa AS c
        SET lead_no_funil = TRUE
        FROM chatbot.etapa AS e
        WHERE c.id_conversa = %s
          AND e.id_etapa = c.id_etapa_atual
          AND c.status_ativa = FALSE
          AND c.finalizou_em IS NOT NULL
          AND e.elegivel_funil = TRUE
          AND c.lead_no_funil IS NOT TRUE
        RETURNING c.id_conversa;
        """,
        (id_conversa,),
    )

    return cursor.fetchone() is not None
```

## Passo 8 - core/cache/runtime/cache_conversas_bloqueadas.py

**Arquivo completo:** `core/cache/runtime/cache_conversas_bloqueadas.py`

```python
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from core.database.connection_aws import get_conn
from core.cache.redis_client import get_redis_safe
from core.logging_config import short_value
from core.repositories.politicas_etapa import (
    buscar_bloqueio_ativo_por_cliente_unidade,
)


logger = logging.getLogger("cache.bloqueia_conversa")

REDIS_PREFIX = "conversa_bloqueada"


def conversa_esta_bloqueada_cache(cliente_telefone, id_phone_unidade):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    try:
        r = get_redis_safe(retries=1, delay=0, validate=False)
        return bool(r.exists(key))

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_indisponivel | acao=fallback_banco cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )

    return _conversa_esta_bloqueada_banco_e_repara_cache(
        cliente_telefone,
        id_phone_unidade,
    )


def registrar_bloqueio_conversa_cache(
    cliente_telefone,
    id_phone_unidade,
    finalizou_em,
    bloqueio_dias,
    redis_retries=1,
    redis_delay=0,
):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    ttl = _calcular_ttl(finalizou_em, bloqueio_dias)

    if ttl <= 0:
        logger.info(
            "cache_bloqueio_ignorado | motivo=ttl_expirado acao=nao_registrar cliente=%s phone_number_id=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
        )
        return False

    payload = {
        "cliente_telefone": str(cliente_telefone),
        "id_phone_unidade": str(id_phone_unidade),
        "finalizou_em": str(finalizou_em) if finalizou_em else "",
        "bloqueio_dias": str(bloqueio_dias),
    }

    try:
        r = get_redis_safe(retries=redis_retries, delay=redis_delay, validate=False)
        r.hset(key, mapping=payload)
        r.expire(key, ttl)

        logger.info(
            "cache_bloqueio_registrado | acao=registrar cliente=%s phone_number_id=%s ttl=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            ttl,
        )
        return True

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_registrar_falhou | acao=ignorar cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        return False


def remover_bloqueio_conversa_cache(
    cliente_telefone,
    id_phone_unidade,
    redis_retries=1,
    redis_delay=0,
):
    key = _cache_key(cliente_telefone, id_phone_unidade)

    if key is None:
        return False

    try:
        r = get_redis_safe(retries=redis_retries, delay=redis_delay, validate=False)
        return bool(r.delete(key))

    except Exception as exc:
        logger.warning(
            "cache_bloqueio_remover_falhou | acao=ignorar cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        return False


def _conversa_esta_bloqueada_banco_e_repara_cache(
    cliente_telefone,
    id_phone_unidade,
):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        bloqueio = buscar_bloqueio_ativo_por_cliente_unidade(
            cliente_telefone,
            id_phone_unidade,
            cursor,
        )

        if bloqueio is None:
            remover_bloqueio_conversa_cache(
                cliente_telefone,
                id_phone_unidade,
                redis_retries=1,
                redis_delay=0,
            )
            return False

        registrar_bloqueio_conversa_cache(
            cliente_telefone,
            id_phone_unidade,
            bloqueio.finalizou_em,
            bloqueio.bloqueio_dias,
            redis_retries=1,
            redis_delay=0,
        )

        return True

    except Exception as exc:
        logger.exception(
            "fallback_banco_bloqueio_falhou | acao=liberar_por_falha cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(id_phone_unidade),
            exc,
        )
        return False

    finally:
        if conn:
            conn.close()


# EXCLUSIVO PARA DEV
def limpar_cache_conversas_bloqueadas_dev():
    # Exclusivo para DEV: use ao recriar o banco para remover bloqueios antigos do Redis.
    try:
        r = get_redis_safe()
        total_removido = 0
        lote = []

        for key in r.scan_iter(match=f"{REDIS_PREFIX}:*", count=500):
            lote.append(key)

            if len(lote) >= 500:
                total_removido += r.delete(*lote)
                lote = []

        if lote:
            total_removido += r.delete(*lote)

        logger.warning(
            "cache_bloqueio_dev_limpo | chaves_removidas=%s",
            total_removido,
        )
        return total_removido

    except Exception as exc:
        logger.warning("cache_bloqueio_dev_limpeza_falhou | erro=%s", exc)
        return 0


def _cache_key(cliente_telefone, id_phone_unidade):
    cliente = _normalizar(cliente_telefone)
    unidade = _normalizar(id_phone_unidade)

    if not cliente or not unidade:
        return None

    raw = f"{unidade}:{cliente}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    return f"{REDIS_PREFIX}:{digest}"


def _normalizar(valor):
    if valor is None:
        return None

    texto = str(valor).strip()
    return texto or None


def _calcular_ttl(finalizou_em, bloqueio_dias):
    if bloqueio_dias <= 0:
        return 0

    if finalizou_em is None:
        return bloqueio_dias * 24 * 60 * 60

    if isinstance(finalizou_em, str):
        finalizou_em = datetime.fromisoformat(finalizou_em)

    if finalizou_em.tzinfo is None:
        finalizou_em = finalizou_em.replace(tzinfo=timezone.utc)

    bloqueado_ate = finalizou_em + timedelta(days=bloqueio_dias)
    agora = datetime.now(timezone.utc)

    return int((bloqueado_ate - agora).total_seconds())
```

## Passo 9 - workers/worker_flow/tratar_bloqueio.py

**Arquivo completo:** `workers/worker_flow/tratar_bloqueio.py`

```python
import logging

from core.cache.runtime.cache_conversas_bloqueadas import registrar_bloqueio_conversa_cache
from core.logging_config import short_value
from core.repositories.deletes import deletar_mensagem_por_id
from core.repositories.politicas_etapa import (
    buscar_bloqueio_conversa_por_id,
)


logger = logging.getLogger("worker.bloqueio")


def tratar_conversa_bloqueada(
    id_mensagem,
    cliente_telefone,
    id_phone_unidade,
    id_conversa,
    cursor,
):
    bloqueio = buscar_bloqueio_conversa_por_id(id_conversa, cursor)

    if bloqueio is None:
        raise ValueError(
            "Conversa classificada como bloqueada sem política de bloqueio "
            f"(id_conversa={id_conversa})"
        )

    registrar_bloqueio_conversa_cache(
        cliente_telefone,
        id_phone_unidade,
        bloqueio.finalizou_em,
        bloqueio.bloqueio_dias,
    )

    deletadas = deletar_mensagem_por_id(id_mensagem, cursor)

    logger.info(
        "mensagem_ignorada | motivo=conversa_bloqueada acao=registrar_cache_remover_fila id_mensagem=%s cliente=%s phone_number_id=%s id_conversa=%s finalizou_em=%s bloqueio_dias=%s removida=%s",
        id_mensagem,
        short_value(cliente_telefone),
        short_value(id_phone_unidade),
        id_conversa,
        bloqueio.finalizou_em,
        bloqueio.bloqueio_dias,
        deletadas,
    )
```

## Passo 10 - workers/worker_flow/transacoes/encerramento_atendimento.py

**Arquivo completo:** `workers/worker_flow/transacoes/encerramento_atendimento.py`

```python
import logging

from core.repositories.encerramento_atendimento import (
    encerrar_conversa,
    excluir_dependente_da_conversa,
)
from core.repositories.politicas_etapa import buscar_politica_etapa
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
MOTIVO_ETAPA_FINAL = "etapa_final"


def resolver_intencao_encerramento(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("encerrar_atendimento"):
        return {
            "motivo": contexto_envio["motivo_encerramento"],
            "excluir_dependente": bool(
                contexto_envio.get("excluir_dependente")
            ),
        }

    # No retry, a resposta já existe e a decisão é reconstruída pela mesma
    # mensagem original da etapa 4, sem consultar conversas anteriores.
    if contexto_envio.get("resposta_ja_existia"):
        intencao_reconstruida = _reconstruir_encerramento_etapa4(
            contexto_historico
        )
        if intencao_reconstruida:
            return intencao_reconstruida

    if not contexto_envio.get("evento_transicao"):
        return None

    id_etapa_destino = contexto_envio.get("id_etapa_resultante")
    politica_destino = buscar_politica_etapa(
        id_etapa_destino,
        cursor,
    )

    if not politica_destino.encerra_automaticamente:
        return None

    return {
        "motivo": MOTIVO_ETAPA_FINAL,
        "excluir_dependente": False,
    }


def _reconstruir_encerramento_etapa4(contexto_historico):
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
        "atendimento_encerrado | acao=encerrar_conversa "
        "id_conversa=%s motivo=%s dependente_excluido=%s",
        id_conversa,
        intencao_encerramento["motivo"],
        intencao_encerramento["excluir_dependente"],
    )
    return True
```

## Passo 11 - workers/worker_flow/transacoes/persistencia_resposta.py

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
        cursor,
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

## Passo 12 - tests/unit/test_politicas_etapa.py

**Arquivo completo:** `tests/unit/test_politicas_etapa.py`

```python
import unittest
import inspect
from datetime import datetime

from core.repositories import querys
from core.repositories.politicas_etapa import (
    BloqueioConversa,
    buscar_bloqueio_ativo_por_cliente_unidade,
    buscar_bloqueio_conversa_por_id,
    buscar_politica_etapa,
)


class CursorFake:
    def __init__(self, resultado=None):
        self.resultado = resultado
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return self.resultado


class PoliticasEtapaTests(unittest.TestCase):
    def test_carrega_politica_da_etapa_final(self):
        cursor = CursorFake((7, True, 30, True))

        politica = buscar_politica_etapa(7, cursor)

        self.assertTrue(politica.encerra_automaticamente)
        self.assertEqual(politica.bloqueio_dias, 30)
        self.assertTrue(politica.elegivel_funil)
        self.assertEqual(cursor.params, (7,))

    def test_etapa_sem_cadastro_falha_sem_assumir_politica(self):
        cursor = CursorFake()

        with self.assertRaisesRegex(ValueError, "não encontrada"):
            buscar_politica_etapa(99, cursor)

    def test_busca_bloqueio_por_conversa_com_prazo_do_banco(self):
        finalizou_em = datetime(2026, 7, 1, 10, 0)
        cursor = CursorFake((finalizou_em, 30))

        bloqueio = buscar_bloqueio_conversa_por_id(10, cursor)

        self.assertEqual(
            bloqueio,
            BloqueioConversa(finalizou_em, 30),
        )
        self.assertIn("e.bloqueio_dias > 0", cursor.sql)
        self.assertEqual(cursor.params, (10,))

    def test_fallback_busca_apenas_bloqueio_ainda_ativo(self):
        finalizou_em = datetime(2026, 7, 1, 10, 0)
        cursor = CursorFake((finalizou_em, 30))

        bloqueio = buscar_bloqueio_ativo_por_cliente_unidade(
            "5575999999999",
            "123456",
            cursor,
        )

        self.assertEqual(bloqueio.bloqueio_dias, 30)
        self.assertIn(
            "e.bloqueio_dias * INTERVAL '1 day'",
            cursor.sql,
        )
        self.assertEqual(
            cursor.params,
            ("5575999999999", "123456"),
        )

    def test_estado_conversa_nao_depende_do_numero_sete(self):
        source = inspect.getsource(querys.buscar_estado_conversa)

        self.assertNotIn("id_etapa_atual = 7", source)
        self.assertIn("LEFT JOIN chatbot.etapa", source)
        self.assertIn("COALESCE(e.bloqueio_dias, 0)", source)


if __name__ == "__main__":
    unittest.main()
```

## Passo 13 - tests/unit/test_repositorio_funil.py

**Arquivo completo:** `tests/unit/test_repositorio_funil.py`

```python
import unittest

from core.repositories.funil import (
    listar_conversas_pendentes_funil,
    marcar_conversa_como_enviada_ao_funil,
)


class CursorFake:
    def __init__(self, *, fetchall=None, fetchone=None):
        self._fetchall = fetchall or []
        self._fetchone = fetchone
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self._fetchall

    def fetchone(self):
        return self._fetchone


class RepositorioFunilTests(unittest.TestCase):
    def test_lista_somente_conversas_finalizadas_pendentes(self):
        cursor = CursorFake(fetchall=[(10,), (20,)])

        resultado = listar_conversas_pendentes_funil(
            cursor,
            limite=50,
        )

        self.assertEqual(resultado, [10, 20])
        self.assertEqual(cursor.params, (50,))
        self.assertIn("e.elegivel_funil = TRUE", cursor.sql)
        self.assertIn("c.status_ativa = FALSE", cursor.sql)
        self.assertIn("c.finalizou_em IS NOT NULL", cursor.sql)
        self.assertIn("c.lead_no_funil IS NOT TRUE", cursor.sql)

    def test_rejeita_limite_invalido(self):
        cursor = CursorFake()

        with self.assertRaises(ValueError):
            listar_conversas_pendentes_funil(cursor, limite=0)

    def test_marca_envio_ao_funil_com_sucesso(self):
        cursor = CursorFake(fetchone=(10,))

        atualizado = marcar_conversa_como_enviada_ao_funil(
            10,
            cursor,
        )

        self.assertTrue(atualizado)
        self.assertEqual(cursor.params, (10,))
        self.assertIn("SET lead_no_funil = TRUE", cursor.sql)
        self.assertIn("e.elegivel_funil = TRUE", cursor.sql)
        self.assertIn("c.status_ativa = FALSE", cursor.sql)
        self.assertIn("c.finalizou_em IS NOT NULL", cursor.sql)
        self.assertIn("c.lead_no_funil IS NOT TRUE", cursor.sql)

    def test_marcacao_repetida_e_idempotente(self):
        cursor = CursorFake(fetchone=None)

        atualizado = marcar_conversa_como_enviada_ao_funil(
            10,
            cursor,
        )

        self.assertFalse(atualizado)


if __name__ == "__main__":
    unittest.main()
```

## Passo 14 - tests/unit/test_cache_and_admin.py

**Arquivo completo:** `tests/unit/test_cache_and_admin.py`

```python
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib import admin, messages

from webhook.admin import UnidadeAdmin
from webhook.models import Unidade
from core.cache import cache_reset, cache_unidade
from core.cache.runtime import cache_cliente, cache_conversas_bloqueadas


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


class FakeRedisBloqueio:
    def __init__(self):
        self.payload = None
        self.ttl = None

    def hset(self, _key, mapping):
        self.payload = mapping

    def expire(self, _key, ttl):
        self.ttl = ttl


class FakeRequest:
    user = "tester"

    def __init__(self):
        self.messages = []


def capturar_message_user(_self, request, message, level=messages.INFO):
    request.messages.append((message, level))


class CacheAndAdminTests(unittest.TestCase):
    def test_cache_cliente_redis_falha_retorna_none(self):
        with patch.object(
            cache_cliente,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ):
            self.assertIsNone(cache_cliente.buscar_cliente_cache("5571999999999"))

    def test_cache_unidade_redis_falha_usa_banco(self):
        chamadas = []

        with patch.object(
            cache_unidade,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_unidade,
            "_unidade_esta_ativa_banco_e_repara_cache",
            lambda phone, **_kwargs: chamadas.append(phone) or True,
        ):
            self.assertTrue(cache_unidade.unidade_esta_ativa("123456"))

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

    def test_cache_unidade_redis_e_banco_falham_sinaliza_indisponibilidade(self):
        with patch.object(
            cache_unidade,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_unidade,
            "get_conn",
            side_effect=ConnectionError("banco caiu"),
        ):
            with self.assertRaises(cache_unidade.ValidacaoUnidadeIndisponivel):
                cache_unidade.unidade_esta_ativa("123456")

    def test_cache_conversa_bloqueada_redis_falha_usa_banco(self):
        chamadas = []

        with patch.object(
            cache_conversas_bloqueadas,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_conversas_bloqueadas,
            "_conversa_esta_bloqueada_banco_e_repara_cache",
            lambda cliente, phone: chamadas.append((cliente, phone)) or True,
        ):
            self.assertTrue(
                cache_conversas_bloqueadas.conversa_esta_bloqueada_cache(
                    "5571999999999",
                    "123456",
                )
            )

        self.assertEqual(chamadas, [("5571999999999", "123456")])

    def test_cache_bloqueio_usa_prazo_recebido_do_banco(self):
        redis_fake = FakeRedisBloqueio()
        finalizou_em = datetime.now(timezone.utc)

        with patch.object(
            cache_conversas_bloqueadas,
            "get_redis_safe",
            return_value=redis_fake,
        ):
            registrado = (
                cache_conversas_bloqueadas
                .registrar_bloqueio_conversa_cache(
                    "5571999999999",
                    "123456",
                    finalizou_em,
                    15,
                )
            )

        self.assertTrue(registrado)
        self.assertEqual(redis_fake.payload["bloqueio_dias"], "15")
        self.assertGreater(redis_fake.ttl, 14 * 24 * 60 * 60)
        self.assertLessEqual(redis_fake.ttl, 15 * 24 * 60 * 60)

    def test_cache_reset_limpa_prefixos_e_recria_unidades(self):
        fake_redis = FakeRedis()

        with patch.object(cache_reset, "get_redis_safe", return_value=fake_redis), patch.object(
            cache_reset,
            "recarregar_cache_unidades",
            return_value=3,
        ):
            resultado = cache_reset.resetar_cache_redis_dev()

        self.assertEqual(resultado["unidades_recriadas"], 3)
        self.assertGreaterEqual(resultado["chaves_exatas_removidas"], 1)
        self.assertEqual(resultado["chaves_por_prefixo_removidas"], 6)
        self.assertTrue(
            any(padrao == "cliente_cache:*" for padrao, _count in fake_redis.patterns)
        )
        self.assertTrue(
            any(padrao == "conversa_bloqueada:*" for padrao, _count in fake_redis.patterns)
        )
        self.assertTrue(
            any(padrao.startswith("webhook_flood_rate") for padrao, _count in fake_redis.patterns)
        )

    def test_admin_unidade_bloqueia_alteracao_se_redis_falhar(self):
        unidade_admin = UnidadeAdmin(Unidade, admin.site)
        request = FakeRequest()

        with patch.object(UnidadeAdmin, "message_user", capturar_message_user), patch(
            "webhook.admin.validar_cache_unidades_disponivel_ou_erro",
            side_effect=cache_unidade.CacheUnidadesIndisponivel("redis caiu"),
        ):
            resultado = unidade_admin._validar_cache_unidades_antes_de_alterar(
                request,
                "salvar",
                meta_validada=True,
            )

        self.assertFalse(resultado)
        self.assertEqual(request.messages[0][1], messages.ERROR)
        self.assertIn("Redis falhou", request.messages[0][0])
        self.assertIn(
            "não foi salva no banco",
            request.messages[0][0],
        )


if __name__ == "__main__":
    unittest.main()
```

## Passo 15 - tests/unit/test_encerramento_etapa4.py

**Arquivo completo:** `tests/unit/test_encerramento_etapa4.py`

```python
import unittest
from types import SimpleNamespace
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
            object(),
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
            object(),
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
            object(),
        )

        self.assertIsNone(resultado)

    def test_transicao_para_etapa_final_cria_intencao_generica(self):
        politica = SimpleNamespace(encerra_automaticamente=True)

        with patch.object(
            encerramento,
            "buscar_politica_etapa",
            return_value=politica,
        ) as buscar:
            resultado = encerramento.resolver_intencao_encerramento(
                {
                    "id_conversa": 10,
                    "id_etapa_origem_transicao": 6,
                },
                {
                    "evento_transicao": "agendamento_enviado",
                    "id_etapa_resultante": 7,
                },
                object(),
            )

        buscar.assert_called_once()
        self.assertEqual(
            resultado,
            {
                "motivo": encerramento.MOTIVO_ETAPA_FINAL,
                "excluir_dependente": False,
            },
        )

    def test_retry_da_transicao_final_reconstroi_encerramento(self):
        politica = SimpleNamespace(encerra_automaticamente=True)

        with patch.object(
            encerramento,
            "buscar_politica_etapa",
            return_value=politica,
        ):
            resultado = encerramento.resolver_intencao_encerramento(
                {
                    "id_conversa": 10,
                    "id_etapa_origem_transicao": 6,
                },
                {
                    "resposta_ja_existia": True,
                    "evento_transicao": "agendamento_enviado",
                    "id_etapa_resultante": 7,
                },
                object(),
            )

        self.assertEqual(
            resultado,
            {
                "motivo": encerramento.MOTIVO_ETAPA_FINAL,
                "excluir_dependente": False,
            },
        )

    def test_tratamento_na_etapa4_nao_consulta_politica_nem_encerra(self):
        with patch.object(
            encerramento,
            "buscar_politica_etapa",
        ) as buscar:
            resultado = encerramento.resolver_intencao_encerramento(
                contexto_historico("não sei"),
                {
                    "tratamento": True,
                    "id_etapa_resultante": 4,
                },
                object(),
            )

        self.assertIsNone(resultado)
        buscar.assert_not_called()

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
                lock_version=7,
                cursor=object(),
                contexto_final=contexto_final,
            )

        self.assertEqual(chamadas, ["encerrar", "sent"])


if __name__ == "__main__":
    unittest.main()
```

## Passo 16 - tests/unit/test_deploy_contract.py

**Arquivo completo:** `tests/unit/test_deploy_contract.py`

```python
import inspect
import unittest

from core.database.deploy import (
    bank_script,
    etapa_transicao_script,
    povoar_etapas,
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

    def test_etapa_possui_politicas_escalaveis(self):
        source = inspect.getsource(bank_script.criar_tabelas)

        self.assertIn("encerra_automaticamente BOOLEAN", source)
        self.assertIn("bloqueio_dias INTEGER", source)
        self.assertIn("elegivel_funil BOOLEAN", source)
        self.assertIn("ck_etapa_bloqueio_dias", source)
        self.assertIn("idx_conversa_funil_pendente", source)
        self.assertIn("WHERE id_etapa = 7", source)

    def test_seed_preserva_bloqueio_atual_somente_na_etapa_7(self):
        etapa_final = povoar_etapas.ETAPAS[-1]

        self.assertEqual(etapa_final[0], 7)
        self.assertTrue(etapa_final[2])
        self.assertEqual(etapa_final[3], 30)
        self.assertTrue(etapa_final[4])
        self.assertTrue(
            all(
                not encerra and dias == 0 and not funil
                for (
                    _id,
                    _nome,
                    encerra,
                    dias,
                    funil,
                ) in povoar_etapas.ETAPAS[:-1]
            )
        )

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

## Ordem de aplicação

1. Materializar exatamente os arquivos acima.
2. Executar `python -m compileall -q callback core workers tests`.
3. Executar `python callback/manage.py check`.
4. Executar `python -m unittest discover -s tests -p "test_*.py"`.
5. Com o RDS acessível, executar `python -m core.database.deploy.setup_database`.
6. Reexecutar a suíte após o deploy.

## Critérios de aceite

- Não existe mais comparação runtime `id_etapa_atual = 7` para decidir bloqueio.
- A etapa 7 continua bloqueando por exatamente 30 dias.
- Conversas inativas antigas com etapa nula continuam sendo reconhecidas como liberadas.
- Etapa 4 encerrada antecipadamente permite uma nova conversa imediatamente.
- Tratamento de idade inválida permanece na etapa 4.
- Redis e PostgreSQL usam o mesmo `bloqueio_dias`.
- Somente etapas com `elegivel_funil = TRUE` aparecem na fila lógica do funil.
- O update do funil não marca uma conversa ativa ou inelegível.
- Retry de resposta final existente reconstrói o encerramento sem reenviar pela Meta.
- Webhook, fila A/B/C, locks, regras de turno e jobs existentes permanecem inalterados.
- O `flow_worker` permanece sem alterações.
- A prévia isolada desta revisão passou por 312 testes antes da geração do documento.