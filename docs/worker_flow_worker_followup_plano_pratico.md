# Plano prático — `worker_followup` e retorno após inatividade

> Documento irmão de [worker_flow_worker_followup_plano_teorico.md](./worker_flow_worker_followup_plano_teorico.md).
> Base de implementação: **V1.1.1**, commit `84735aeaa521cfcf3a8bb13b2a8eddeb126fa1df`.
> Preparado em 08/09/2026. **Status: plano para implementação e homologação.**
> Este documento contém o conteúdo final integral de **27 arquivos**, um por passo.
> A preparação e os testes usaram uma cópia temporária isolada. Nenhum worker,
> serviço da VM, banco de produção ou arquivo de runtime do projeto foi alterado.

## Relação com o teórico e versão de referência

O teórico define o comportamento; este prático materializa os contratos em código
e inclui os arquivos de migração, operação e testes. A ordem de construção continua
sendo **novo worker_followup primeiro; integração do worker_flow depois**. Na VM,
a ordem de ativação é obrigatoriamente **flow compatível primeiro; follow-up depois**.

O teórico ainda menciona V1.1.0 como base e reserva V1.1.1 para o follow-up. Essas
referências foram escritas antes de a V1.1.1 ser utilizada para o painel compacto e
os CSVs essenciais. Nesta edição, V1.1.1 identifica a base já publicada, não a
entrega de follow-up. O número da versão futura será definido na implementação.
Isso não muda as regras funcionais do documento irmão.

O plano de `user_id` e o plano de IA não são aplicados aqui. Continuam existindo
22 etapas e a identidade atual por `wa_id`, dentro da unidade identificada por
`phone_number_id`. Não há renumeração de etapas nem mudança no mapa de transições.

## Comportamento que este código implementa

| Situação | Ação | Estado depois do sucesso |
|---|---|---|
| Última resposta comum do bot sem reação por pelo menos sete horas; demais condições atendidas | Enviar exatamente `Você viu a minha mensagem?` | `followup_stage = 1` |
| Cliente continua em silêncio | Não enviar outro lembrete | Stage permanece positivo |
| Migração inicial em banco existente | Registrar todas as conversas ativas e marcar stage 1, sem enviar mensagens | Retomada pendente para o legado |
| Primeira entrada aceita com stage positivo | Gravar a reação, saudar e repetir a etapa atual, incluindo botões e conteúdo dinâmico | Stage vira zero junto do commit da repetição |
| Falha no sender ou na persistência da repetição | Manter a recuperação atual da fila | Stage continua positivo |
| Retry de uma reação cuja repetição já foi confirmada | Recuperar o histórico e concluir a fila | Sem reenviar e sem resetar um ciclo posterior |
| Entrada aceita com stage zero | Usar o fluxo normal | Validadores, mapa e saudação reativa de três horas permanecem |

Novos lembretes são permitidos somente nas etapas **1–17**. A etapa 18
(agendamento) e todas as posteriores são inelegíveis, mesmo com stage zero e
sete horas sem resposta. O limite vale na seleção e na releitura depois do lock.
A recuperação pelo `worker_flow` continua aceitando ciclos positivos legados nas
etapas 1–21; repetir um ciclo já existente não autoriza um novo envio proativo.

NULL é normalizado como zero para elegibilidade. Stages 2 ou maiores são tratados
como retorno de follow-up no flow, para recuperação de dados legados; o novo worker
nunca os produz. Stage negativo falha fechado e aparece no diagnóstico.

A reação não é descartada do banco. Apenas seu **conteúdo não é interpretado como
resposta de negócio** nesse primeiro processamento. Por exemplo, `Começar triagem`
recebido depois de um lembrete repete a introdução da triagem e encerra o ciclo.
Uma nova resposta ao botão, já com stage zero, é interpretada normalmente.

Não existem segundo/terceiro lembretes, encerramento por silêncio ou alteração de
`turnos_sem_avanco`. A repetição não escolhe evento, não altera cadastro/dependente,
não grava respostas de triagem, não publica no Funil e não aciona encerramento.
`followup_last_sent_at` permanece como informação de auditoria depois do reset.

Todo retorno com stage positivo usa `Que bom te ver novamente, <nome>!`, seguido
de duas quebras de linha e da mensagem da etapa. Sem nome já persistido, usa
`Que bom te ver novamente!`. Isso vale para lembrete real e marcação do legado,
independentemente do tempo de retorno. A reação não é interpretada para descobrir
o nome. A saudação `Olá novamente` continua exclusiva do stage zero após três horas.

A migração única marca stage 1 em todas as conversas que continuam ativas no
momento da aplicação, incluindo as etapas 18–21. Guarda ID, stage anterior e
horário em `followup_legado`, sem inventar mensagem, recibo ou `last_sent_at`.
Conversas encerradas não são alteradas; as criadas depois continuam com stage zero.
A marcação não é repetida em reinícios/deploys. O setup de banco novo apenas cria
as estruturas. Stage positivo decide a retomada, mas sozinho não comprova envio.

## Decisões técnicas materializadas

### Identificação persistente do ciclo e da reação

O histórico atual é particionado por `received_data_hora`, com chave primária
`(id_mensagem, received_data_hora)`. Uma unicidade global da chave do ciclo apenas
nesse histórico não atenderia à forma atual de particionamento. Por isso o plano
acrescenta três tabelas internas:

| Tabela | Identidade e finalidade |
|---|---|
| `followup_envio` | Chave composta `(id_conversa, id_ancora, ancora_em)`. A âncora é a última resposta comum confirmada do bot. Guarda a comprovação local do único lembrete daquele ciclo. |
| `followup_retomada` | Chave `(id_conversa, id_mensagem_fila, id_hash_cliente)`. Registra por que a entrada não foi interpretada e quando sua repetição foi concluída. |
| `followup_legado` | Chave `id_conversa`. Audita o stage anterior e o horário da marcação inicial; não representa mensagem enviada. |

A chave composta de `followup_envio` é a implementação tipada da identidade lógica
`followup:conversa:ancora:1` proposta no teórico. A comparação de datas é feita por
TIMESTAMPTZ no PostgreSQL, não por texto formatado ou horário local do processo.

O lembrete proativo entra em `historico_mensagens` como `bot`, `text` e `sent`, com
`id_mensagem_fila = NULL` e `id_hash_cliente_origem = NULL`. Não inventamos uma fila
ou um hash de cliente para acomodar uma saída que surgiu por inatividade.

As tabelas internas usam FK da conversa com exclusão em cascata. A referência à
fila na retomada fica como identificador de auditoria, sem FK que apague o marcador
quando a fila for limpa. O histórico particionado também não ganha uma FK inversa
que impeça a manutenção de partições. Falta de comprovação em retomada concluída
gera erro de integridade; não autoriza reenviar por adivinhação.

Não há novos modelos Django/admin, porque os recibos são internos e usados por SQL.
As colunas de follow-up da conversa já existem na base. A migração não as recria;
marca stage 1 nas ativas e preserva `followup_last_sent_at`. Não impõe um CHECK 0–1
que inviabilize recuperar stages legados. O UPDATE e a auditoria são atômicos.

### Concorrência e fronteiras do envio

1. A seleção paginada não autoriza envio. Cada candidata precisa obter o lock
   `chatbot.lock_conversa`, ter sua posse conferida e ser relida.
2. A releitura verifica unidade, destinatário, etapa ativa, pagamento, bloqueios,
   flood persistido, horário, histórico e fila. A fila é reconhecida pelo vínculo
   de conversa **ou** pelo par cliente/unidade, inclusive quando não vinculada.
3. Uma fila `pending`/`processing` adia o proativo mesmo se sua resposta já estiver
   gravada. Essa espera é conservadora e não modifica a regra A/B/C do webhook.
4. A transação de releitura termina antes da chamada HTTP. Não se segura um lock
   físico de linha durante a comunicação com a Meta. O lock lógico versionado
   continua sendo compartilhado pelos workers.
5. O flow relê seu contexto após obter o lock. Antes do envio, renova a posse em um
   checkpoint adicional. Antes da persistência e da finalização, confere o fencing
   e mantém a linha protegida até o respectivo commit.
6. Uma entrada aceita entre a checagem final e a conclusão da chamada Meta pode
   cruzar com o lembrete. Depois do aceite externo, a mera presença dessa nova fila
   não cancela a gravação do envio: o flow obterá o lock e verá stage positivo.
7. Dono antigo que perdeu a versão não zera stage, não finaliza fila e não libera
   o lock do novo dono. A recuperação da fila segue seus mecanismos atuais.

A prova local impede reenvios após o commit. **Aceite externo e commit local não
formam uma transação distribuída**: queda, timeout com resultado incerto ou perda de
lease nessa fronteira ainda podem causar a duplicidade rara já aceita pelo projeto.
O código não promete entrega exatamente uma vez nem trata um timeout como certeza
de que a mensagem não saiu. Os logs de falha após aceite incluem o ID conhecido.

### Janela de atendimento da Meta

As sete horas são contadas desde a resposta do bot. A permissão de enviar texto
livre depende de outra referência: a última mensagem do cliente dentro da janela
de atendimento de 24 horas. Fora dela, o canal exige um template aprovado.
[Fonte: política oficial do WhatsApp, seção 2](https://whatsappbusiness.com/policy/).

Este plano não cria templates. A consulta exige evidência de mensagem recebida
dentro da janela e reserva um minuto antes de seu fechamento. Assim, se o serviço
retornar de uma longa parada e a janela já estiver encerrada, ele não tentará
compensar o atraso enviando texto livre. A margem é uma proteção do canal, não
uma mudança na regra de inatividade de sete horas. Entradas descartadas pelo
webhook não são inventadas no histórico para prolongar essa janela.

### Processo, configuração e monitoramento

O serviço novo usa a mesma VM e conta `chatbot`, mas possui seu próprio processo.
Não é iniciado pelo Django nem pelo webhook. As variáveis operacionais têm os
seguintes padrões no módulo de configuração:

| Variável | Padrão | Uso |
|---|---|---|
| `FOLLOWUP_WORKER_ENABLED` | `false` | Execução manual sem ativação explícita não inicia envios. A unit proposta define `true`. |
| `FOLLOWUP_POLL_SECONDS` | `60` | Intervalo entre lotes; aceito de 5 a 3600 segundos. |
| `FOLLOWUP_BATCH_SIZE` | `20` | Limite por lote; aceito de 1 a 100. |

Não são necessários novos segredos ou um segundo arquivo `.env`. A unit inclui
as configurações operacionais e reutiliza `/etc/chatbot/chatbot.env`. Se alguma
dessas chaves for definida também no EnvironmentFile, seu valor deve ser conferido
na implantação, pois o EnvironmentFile prevalece sobre `Environment=` do systemd.

O intervalo não promete disparo no segundo exato do vencimento: consulta, tamanho
do lote e disponibilidade do canal podem atrasar o envio, mas nunca antecipá-lo.
O lote contém até 20 candidatas, processadas sequencialmente, uma conversa por
vez. Cada conversa usa conexão, lock e transações próprios; não existe commit
conjunto das 20. Uma falha local não desfaz os envios já persistidos das demais.
A seleção não reserva todas as conversas: cada candidata é relida após seu lock.
A paginação evita que candidatas antigas com erro impeçam a visita das seguintes.
Falhas da varredura usam backoff de 5 a 300 segundos; falhas individuais aguardam
a próxima passagem pela candidata, sem retry HTTP automático em laço apertado.
O cursor avança mesmo em falhas de uma candidata, inclusive conexão ou limpeza,
para visitar as demais. Quando chega ao fim da paginação, volta ao início e pode
tentar as que falharam, se ainda elegíveis. Isso não garante retry no lote seguinte:
uma resposta do cliente, bloqueio, mudança de etapa ou fim da janela Meta pode excluí-las.

O diagnóstico é somente leitura. O painel segue mostrando o lembrete como texto
normal do bot, contando-o entre as mensagens. Ele não precisa de campo de escrita,
badge exclusivo ou alteração nos filtros/CSV. A autorização por unidade, tags de
perfil, correção da triagem, responsividade e as quatro exportações da V1.1.1
permanecem nos arquivos atuais, fora da substituição descrita abaixo.

## Como materializar os passos

- Usar uma cópia de desenvolvimento da base indicada e conferir alterações locais
  antes de substituir arquivos. O manifesto ao final registra hashes com finais
  de linha normalizados para LF.
- Cada passo contém **um arquivo inteiro**. Nos arquivos existentes, o bloco
  substitui o conteúdo completo; nos novos, cria o caminho indicado.
- Os passos de SQL, systemd, testes e READMEs também contêm arquivos completos.
  Nenhum bloco solicita manter um trecho omitido, preencher função ou aplicar diff.
- Escrever os arquivos em ordem prepara a implementação. Isso não executa a
  migração, não inicia o serviço e não envia mensagens.
- Materializar e testar ambas as partes antes do deploy. Não ativar o worker
  proativo quando apenas a Parte 1 estiver pronta.
- Não copiar os planos de `user_id` ou IA para dentro desta implementação. Não
  alterar `.env`, `VERSIONAMENTO.txt`, requisitos, catálogo de etapas, payloads,
  webhook, Funil ou fontes do painel por conta deste documento.

## Inventário dos passos

| Passo | Ação | Arquivo |
|---|---|---|
| 1 | Alterar | `core/database/connection_aws.py` |
| 2 | Criar | `core/database/deploy_database/followup_script.py` |
| 3 | Alterar | `core/database/deploy_database/bank_script.py` |
| 4 | Criar | `deploy/migrations/followup_registros.sql` |
| 5 | Criar | `core/repositories/atendimento/followup.py` |
| 6 | Criar | `core/integrations/whatsapp/messages/followup_messages.py` |
| 7 | Alterar | `core/integrations/whatsapp/pywa_functions/cliente.py` |
| 8 | Criar | `core/integrations/whatsapp/pywa_functions/pywa_senders/followup.py` |
| 9 | Criar | `workers/worker_followup/__init__.py` |
| 10 | Criar | `workers/worker_followup/config.py` |
| 11 | Criar | `workers/worker_followup/followup_worker.py` |
| 12 | Criar | `workers/worker_followup/iniciar_worker_followup.py` |
| 13 | Criar | `deploy/systemd/chatbot-worker-followup.service` |
| 14 | Criar | `workers/worker_flow/response_flow/repeticao_followup.py` |
| 15 | Criar | `workers/worker_flow/transacoes/retorno_followup.py` |
| 16 | Alterar | `workers/worker_flow/response_flow/flow_worker.py` |
| 17 | Alterar | `tests/unit/test_worker_flow_runtime.py` |
| 18 | Criar | `tests/unit/test_followup.py` |
| 19 | Criar | `tests/integration/__init__.py` |
| 20 | Criar | `tests/integration/test_followup_postgres.py` |
| 21 | Criar | `utilitarios/verificar_followup.py` |
| 22 | Alterar | `REGRAS_DE_NEGOCIO.md` |
| 23 | Alterar | `workers/README.md` |
| 24 | Alterar | `core/repositories/README.md` |
| 25 | Alterar | `core/integrations/whatsapp/README.md` |
| 26 | Alterar | `tests/README.md` |
| 27 | Alterar | `deploy/README.md` |

---

# Parte 1 — Novo worker_followup: contratos e persistência

## Passo 1 — `core/database/connection_aws.py`

**Ação:** Alterar.

Acrescentar timeout de conexão opcional. Chamadas existentes conservam seus argumentos e comportamento; o novo worker limita a espera por conexão.

```python
import logging

import psycopg

from core.config_env import env_int, env_optional, env_required

logger = logging.getLogger("db.connection")

setup = {
    "host": env_required("DB_HOST"),
    "dbname": env_required("DB_NAME"),
    "user": env_required("DB_USER"),
    "password": env_required("DB_PASSWORD"),
    "port": env_int("DB_PORT", 5432),
}

_db_sslmode = env_optional("DB_SSLMODE")
_db_sslrootcert = env_optional("DB_SSLROOTCERT")

if _db_sslmode:
    setup["sslmode"] = _db_sslmode

if _db_sslrootcert:
    setup["sslrootcert"] = _db_sslrootcert


def get_conn(application_name=None, *, connect_timeout=None):
    connect_kwargs = dict(setup)

    if application_name:
        connect_kwargs["application_name"] = application_name

    if connect_timeout is not None:
        if type(connect_timeout) is not int or connect_timeout <= 0:
            raise ValueError("connect_timeout deve ser inteiro positivo")
        connect_kwargs["connect_timeout"] = connect_timeout

    conn = psycopg.connect(**connect_kwargs)
    logger.debug(
        "banco_conexao_aberta | acao=connect host=%s database=%s user=%s application_name=%s",
        setup["host"],
        setup["dbname"],
        setup["user"],
        application_name,
    )
    return conn


# conn.close automaticamente fecha qualquer cursor associado a ela.
# Se fizer conn.close, nao precisa fazer cursor.close.
```

## Passo 2 — `core/database/deploy_database/followup_script.py`

**Ação:** Criar.

Declarar as três tabelas internas para instalação limpa, sem marcar conversas. Recebe cursor e não assume a transação do setup.

```python
"""DDL canônico de instalação limpa; migração incremental fica em deploy/migrations."""

DDL_FOLLOWUP = """

CREATE TABLE IF NOT EXISTS chatbot.followup_envio (
    id_conversa INTEGER NOT NULL REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    id_ancora INTEGER NOT NULL,
    ancora_em TIMESTAMPTZ NOT NULL,
    id_historico_bot INTEGER NOT NULL,
    enviado_em TIMESTAMPTZ NOT NULL,
    id_hash_msg VARCHAR(255) NOT NULL,
    PRIMARY KEY (id_conversa, id_ancora, ancora_em),
    UNIQUE (id_conversa, id_historico_bot, enviado_em)
);

CREATE TABLE IF NOT EXISTS chatbot.followup_retomada (
    id_conversa INTEGER NOT NULL REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    id_mensagem_fila INTEGER NOT NULL,
    id_hash_cliente VARCHAR(255) NOT NULL,
    id_etapa INTEGER NOT NULL REFERENCES chatbot.etapa(id_etapa),
    stage_anterior INTEGER NOT NULL CHECK (stage_anterior > 0),
    followup_em TIMESTAMPTZ,
    registrada_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    concluida_em TIMESTAMPTZ,
    PRIMARY KEY (id_conversa, id_mensagem_fila, id_hash_cliente)
);

CREATE INDEX IF NOT EXISTS idx_followup_retomada_aberta ON chatbot.followup_retomada(id_conversa)
WHERE concluida_em IS NULL;

CREATE TABLE IF NOT EXISTS chatbot.followup_legado (
    id_conversa INTEGER PRIMARY KEY REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    stage_anterior INTEGER,
    marcada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

"""


def criar_tabelas_followup(cursor):
    cursor.execute(DDL_FOLLOWUP)
```

## Passo 3 — `core/database/deploy_database/bank_script.py`

**Ação:** Alterar.

Conectar o DDL de follow-up ao criador canônico, dentro da transação já existente. O arquivo abaixo é completo, incluindo as funções de lock e dequeue preservadas.

```python
import logging

from core.database.deploy_database.transacao_deploy import transacao_deploy
from core.database.deploy_database.followup_script import criar_tabelas_followup

logger = logging.getLogger("db.deploy_database")


def criar_funcoes_lock():
    with transacao_deploy("criar_funcoes_lock", logger) as cursor:
        cursor.execute("""
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
                    OR c.processing_started_at
                        < NOW() - INTERVAL '110.0 seconds'
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

    logger.info("banco_setup_ok | acao=criar_funcoes_lock")


def criar_funcao_dequeue_message():
    with transacao_deploy("criar_funcao_dequeue_message", logger) as cursor:
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
                        AND f.processing_started_at
                            < NOW() - INTERVAL '2 minutes'
                    )
                ORDER BY
                    CASE
                        WHEN f.status = 'pending' THEN f.next_attempt_at
                        WHEN f.status = 'processing'
                            THEN f.processing_started_at
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

    logger.info("banco_setup_ok | acao=criar_funcao_dequeue_message")


def criar_tabelas():
    """Cria o schema final da V1 em ordem de dependência, sem migrações."""
    with transacao_deploy("criar_tabelas", logger) as cursor:
        cursor.execute("""
        CREATE SCHEMA IF NOT EXISTS chatbot;

        DO $dependencia_django$
        BEGIN
            IF TO_REGCLASS('chatbot.auth_user') IS NULL THEN
                RAISE EXCEPTION
                    'Prepare o schema chatbot e execute as migrations do Django antes do DDL de negocio: chatbot.auth_user deve existir.';
            END IF;
        END
        $dependencia_django$;

        -- 1. CLIENTE E UNIDADE (AUTH_USER PREPARADA PELO DJANGO)

        CREATE TABLE IF NOT EXISTS chatbot.cliente (
            id_cliente SERIAL PRIMARY KEY,
            nome VARCHAR(200),
            waid_telefone VARCHAR(50) UNIQUE NOT NULL,
            email VARCHAR(200) UNIQUE,
            idade INTEGER,
            profissao VARCHAR(100)
        );

        CREATE TABLE IF NOT EXISTS chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY,
            nome_unidade VARCHAR(300) NOT NULL,
            nome_agente VARCHAR(100) NOT NULL,
            genero VARCHAR(9) NOT NULL,
            cnpj VARCHAR(50) UNIQUE NOT NULL,
            email_responsavel VARCHAR(255) UNIQUE NOT NULL,
            telefone VARCHAR(20) UNIQUE NOT NULL,
            numero_comercial VARCHAR(30),
            suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE,
            email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
            waba_id VARCHAR(100) UNIQUE NOT NULL,
            phone_number_id VARCHAR(100) UNIQUE NOT NULL,
            link_agendamento VARCHAR(400) UNIQUE NOT NULL,
            link_instagram VARCHAR(400),
            bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE,
            status_pagamento BOOLEAN DEFAULT TRUE,
            id_usuario_monitoramento INT NULL,

            CONSTRAINT uq_unidade_nome_unidade
                UNIQUE (nome_unidade),

            CONSTRAINT ck_unidade_nome_unidade_nao_vazio
                CHECK (nome_unidade ~ '[^[:space:]]'),

            CONSTRAINT ck_unidade_nome_agente_nao_vazio
                CHECK (nome_agente ~ '[^[:space:]]'),

            CONSTRAINT ck_unidade_genero
                CHECK (genero IN ('masculino', 'feminino')),

            CONSTRAINT uq_unidade_usuario_monitoramento
                UNIQUE (id_usuario_monitoramento),
            CONSTRAINT unidade_id_usuario_monitoramento_fkey
                FOREIGN KEY (id_usuario_monitoramento)
                REFERENCES chatbot.auth_user(id)
                ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS chatbot.etapa (
            id_etapa SERIAL PRIMARY KEY,
            nome_etapa VARCHAR(100) UNIQUE NOT NULL,
            encerra_automaticamente BOOLEAN NOT NULL DEFAULT FALSE,
            bloqueio_dias INTEGER NOT NULL DEFAULT 0,
            elegivel_funil BOOLEAN NOT NULL DEFAULT FALSE,

            CONSTRAINT ck_etapa_bloqueio_dias
                CHECK (bloqueio_dias >= 0)
        );

        -- 2. CONFIGURACAO DO FUNIL POR UNIDADE

        CREATE TABLE IF NOT EXISTS chatbot.integracao_funil_unidade (
            id_integracao_funil SERIAL PRIMARY KEY,
            id_unidade INT NOT NULL UNIQUE,

            nome_widget VARCHAR(300) NOT NULL,
            data_salvamento_widget DATE,
            codigo_widget VARCHAR(100) UNIQUE NOT NULL,
            link_api_carrossel VARCHAR(500) UNIQUE NOT NULL,
            codigo_canal_venda VARCHAR(100) NOT NULL,

            widget_ativo BOOLEAN NOT NULL DEFAULT TRUE,
            integracao_ativa BOOLEAN NOT NULL DEFAULT TRUE,

            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT ck_integracao_funil_nome_widget
                CHECK (BTRIM(nome_widget) <> ''),

            CONSTRAINT ck_integracao_funil_codigo_widget
                CHECK (BTRIM(codigo_widget) <> ''),

            CONSTRAINT ck_integracao_funil_link_api
                CHECK (BTRIM(link_api_carrossel) <> ''),

            CONSTRAINT ck_integracao_funil_codigo_canal
                CHECK (BTRIM(codigo_canal_venda) <> ''),

            CONSTRAINT integracao_funil_unidade_id_unidade_fkey
                FOREIGN KEY (id_unidade)
                REFERENCES chatbot.unidade(id_unidade)
                ON DELETE CASCADE
        );

        -- 3. CONVERSA: RAIZ TRANSACIONAL DO ATENDIMENTO

        CREATE TABLE IF NOT EXISTS chatbot.conversa (
            id_conversa SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_unidade INT NOT NULL,
            id_etapa_atual INT,

            status_ativa BOOLEAN NOT NULL DEFAULT TRUE,
            status_dependente BOOLEAN DEFAULT FALSE,
            profissao VARCHAR(100) NULL,

            last_interaction_at TIMESTAMPTZ,

            last_message_from VARCHAR(10)
                CHECK (last_message_from IN ('cliente', 'bot')),

            followup_stage INTEGER DEFAULT 0,
            followup_last_sent_at TIMESTAMPTZ NULL,

            lead_no_funil BOOLEAN DEFAULT FALSE,

            processing BOOLEAN DEFAULT FALSE,
            processing_started_at TIMESTAMPTZ NULL,
            lock_version INTEGER DEFAULT 0,
            turnos_sem_avanco INTEGER NOT NULL DEFAULT 0,

            iniciou_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finalizou_em TIMESTAMPTZ,
            motivo_encerramento VARCHAR(30),

            CONSTRAINT ck_conversa_motivo_encerramento
                CHECK (
                    motivo_encerramento IS NULL
                    OR motivo_encerramento IN (
                        'idade_invalida',
                        'foi_agendado',
                        'encaminhado_suporte_idoso'
                    )
                ),

            CONSTRAINT ck_conversa_turnos_sem_avanco
                CHECK (turnos_sem_avanco BETWEEN 0 AND 12),

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
        ON chatbot.conversa (
            last_message_from,
            followup_stage,
            last_interaction_at
        );

        CREATE INDEX IF NOT EXISTS idx_conversa_processing
        ON chatbot.conversa (processing, processing_started_at);

        CREATE INDEX IF NOT EXISTS idx_conversa_ultima_inativa
        ON chatbot.conversa (id_cliente, id_unidade, finalizou_em DESC)
        INCLUDE (id_conversa, id_etapa_atual)
        WHERE status_ativa = FALSE;

        CREATE INDEX IF NOT EXISTS idx_conversa_funil_pendente
        ON chatbot.conversa (id_etapa_atual, id_conversa)
        WHERE lead_no_funil IS NOT TRUE;

        -- 4. DEPENDENTE: EXISTE SOMENTE DENTRO DE UMA CONVERSA

        CREATE TABLE IF NOT EXISTS chatbot.dependente (
            id_dependente SERIAL PRIMARY KEY,
            id_cliente INT NOT NULL,
            id_conversa INT,
            nome_dependente VARCHAR(200),
            idade INTEGER,

            FOREIGN KEY (id_cliente)
                REFERENCES chatbot.cliente(id_cliente)
                ON DELETE CASCADE,

            CONSTRAINT dependente_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_dependente_cliente
        ON chatbot.dependente (id_cliente);

        CREATE UNIQUE INDEX IF NOT EXISTS uq_dependente_conversa
        ON chatbot.dependente (id_conversa)
        WHERE id_conversa IS NOT NULL;

        CREATE INDEX IF NOT EXISTS idx_dependente_conversa
        ON chatbot.dependente (id_conversa);

        -- 5. FILA: CRIADA ANTES DO HISTÓRICO PARA A FK NASCER PRONTA

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

            CHECK (status IN ('pending', 'processing', 'sent', 'failed'))
        );

        CREATE INDEX IF NOT EXISTS idx_fila_pending_next_attempt
        ON chatbot.fila_mensagens (next_attempt_at, id_mensagem)
        WHERE status = 'pending';

        CREATE INDEX IF NOT EXISTS idx_fila_processing_timeout
        ON chatbot.fila_mensagens (processing_started_at, id_mensagem)
        WHERE status = 'processing';

        CREATE INDEX IF NOT EXISTS idx_fila_conversa_aberta_data
        ON chatbot.fila_mensagens (
            id_conversa,
            received_data_hora,
            id_mensagem
        )
        WHERE id_conversa IS NOT NULL
          AND status IN ('pending', 'processing');

        -- 6. HISTÓRICO PARTICIONADO E RESPOSTAS DA TRIAGEM

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

            CONSTRAINT fk_historico_mensagem_fila
                FOREIGN KEY (id_mensagem_fila)
                REFERENCES chatbot.fila_mensagens(id_mensagem)
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

        CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios (
            id_resposta_desafio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL,
            id_etapa INT NOT NULL,
            resposta VARCHAR(20) NOT NULL,
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

        -- 7. PESQUISA DE SATISFACAO DO ATENDIMENTO

        CREATE TABLE IF NOT EXISTS chatbot.pesquisa_satisfacao (
            id_pesquisa_satisfacao SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL UNIQUE,
            nota SMALLINT,
            comentario TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT pesquisa_satisfacao_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            CONSTRAINT ck_pesquisa_satisfacao_nota
                CHECK (nota IS NULL OR nota BETWEEN 1 AND 5)
        );

        -- 8. FILA OPERACIONAL DO WORKER DE FUNIL

        CREATE TABLE IF NOT EXISTS chatbot.funil_envios (
            id_funil_envio SERIAL PRIMARY KEY,
            id_conversa INT NOT NULL UNIQUE,
            status VARCHAR(20) NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            processing_started_at TIMESTAMPTZ,
            enviado_em TIMESTAMPTZ,
            ultimo_erro TEXT,
            resposta_funil TEXT,
            criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT funil_envios_id_conversa_fkey
                FOREIGN KEY (id_conversa)
                REFERENCES chatbot.conversa(id_conversa)
                ON DELETE CASCADE,

            CONSTRAINT ck_funil_envios_status
                CHECK (status IN ('pending', 'processing', 'sent')),

            CONSTRAINT ck_funil_envios_attempt_count
                CHECK (attempt_count >= 0)
        );

        CREATE INDEX IF NOT EXISTS idx_funil_envios_disponiveis
        ON chatbot.funil_envios (
            status,
            next_attempt_at,
            processing_started_at,
            id_funil_envio
        )
        WHERE status IN ('pending', 'processing');
        """)

        criar_tabelas_followup(cursor)

    logger.info("banco_setup_ok | acao=criar_tabelas")


def configurar_role_banco():
    """Aplica timezone e limites operacionais da role em uma transação."""
    with transacao_deploy("configurar_role_banco", logger) as cursor:
        cursor.execute("""
            ALTER ROLE fushi
            SET timezone TO 'America/Sao_Paulo';

            ALTER ROLE fushi
            SET idle_in_transaction_session_timeout = '30min';

            ALTER ROLE fushi
            SET statement_timeout = '10min';

            ALTER ROLE fushi
            SET lock_timeout = '15s';
        """)

    logger.info("banco_setup_ok | acao=configurar_role_banco role=fushi")
```

## Passo 4 — `deploy/migrations/followup_registros.sql`

**Ação:** Criar.

Preparar a migração manual, única e transacional para bancos existentes: auditar as ativas e marcar stage 1 sem enviar mensagens. Criar este arquivo agora não significa executar seu SQL agora.

```sql
-- Aplicação manual única, com flow parado e follow-up desligado. Não executa envios.
BEGIN;
SET LOCAL lock_timeout = '5s';
DO $dependencias$
BEGIN
    IF TO_REGCLASS('chatbot.conversa') IS NULL
       OR TO_REGCLASS('chatbot.historico_mensagens') IS NULL
       OR TO_REGCLASS('chatbot.etapa') IS NULL THEN
        RAISE EXCEPTION 'Dependencias de followup ausentes';
    END IF;
END
$dependencias$;

-- Estabiliza o conjunto legado enquanto ele é registrado e marcado.
LOCK TABLE chatbot.conversa IN SHARE ROW EXCLUSIVE MODE;
DO $integridade_legado$
BEGIN
    IF EXISTS (
        SELECT 1 FROM chatbot.conversa c
        LEFT JOIN chatbot.etapa e ON e.id_etapa = c.id_etapa_atual
        WHERE c.status_ativa IS TRUE AND (
            c.finalizou_em IS NOT NULL OR e.id_etapa IS NULL
            OR c.id_etapa_atual NOT BETWEEN 1 AND 21
            OR e.encerra_automaticamente IS TRUE
        )
    ) THEN
        RAISE EXCEPTION 'Conversa ativa inconsistente ou terminal; concluir a recuperacao do flow antes de migrar';
    END IF;
END
$integridade_legado$;

CREATE TABLE chatbot.followup_envio (
    id_conversa INTEGER NOT NULL REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    id_ancora INTEGER NOT NULL,
    ancora_em TIMESTAMPTZ NOT NULL,
    id_historico_bot INTEGER NOT NULL,
    enviado_em TIMESTAMPTZ NOT NULL,
    id_hash_msg VARCHAR(255) NOT NULL,
    PRIMARY KEY (id_conversa, id_ancora, ancora_em),
    UNIQUE (id_conversa, id_historico_bot, enviado_em)
);

CREATE TABLE chatbot.followup_retomada (
    id_conversa INTEGER NOT NULL REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    id_mensagem_fila INTEGER NOT NULL,
    id_hash_cliente VARCHAR(255) NOT NULL,
    id_etapa INTEGER NOT NULL REFERENCES chatbot.etapa(id_etapa),
    stage_anterior INTEGER NOT NULL CHECK (stage_anterior > 0),
    followup_em TIMESTAMPTZ,
    registrada_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    concluida_em TIMESTAMPTZ,
    PRIMARY KEY (id_conversa, id_mensagem_fila, id_hash_cliente)
);

CREATE INDEX idx_followup_retomada_aberta ON chatbot.followup_retomada(id_conversa)
WHERE concluida_em IS NULL;

CREATE TABLE chatbot.followup_legado (
    id_conversa INTEGER PRIMARY KEY REFERENCES chatbot.conversa(id_conversa) ON DELETE CASCADE,
    stage_anterior INTEGER,
    marcada_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO chatbot.followup_legado (id_conversa, stage_anterior)
SELECT id_conversa, followup_stage FROM chatbot.conversa WHERE status_ativa IS TRUE;

-- Marca também etapas 18–21 para retomada reativa; elas nunca recebem proativo.
-- Preserva etapa, histórico, finalização, última interação e last_sent_at.
UPDATE chatbot.conversa c
SET followup_stage = 1
FROM chatbot.followup_legado l
WHERE c.id_conversa = l.id_conversa;

SELECT COUNT(*) AS conversas_ativas_marcadas FROM chatbot.followup_legado;

COMMIT;
```

## Passo 5 — `core/repositories/atendimento/followup.py`

**Ação:** Criar.

Centralizar elegibilidade, releitura, fencing, identificação do ciclo, retomada e diagnóstico. Nenhuma função deste repositório faz commit, rollback, envio ou escolha de transição.

```python
"""Consultas de follow-up e fencing; commit/rollback pertencem ao orquestrador."""


class LockConversaPerdido(RuntimeError):
    """O processamento deixou de possuir a versão válida do lock."""


def proteger_conversa(id_conversa, lock_version, cursor, *, renovar=False):
    cursor.execute(
        """
        SELECT id_conversa FROM chatbot.conversa
        WHERE id_conversa = %s AND processing IS TRUE AND lock_version = %s
          AND processing_started_at > clock_timestamp() - INTERVAL '110 seconds'
        FOR UPDATE;
    """,
        (id_conversa, lock_version),
    )
    if cursor.fetchone() is None:
        raise LockConversaPerdido(
            f"Lock perdido: conversa={id_conversa}, versao={lock_version}"
        )
    if renovar:
        cursor.execute(
            """
            UPDATE chatbot.conversa SET processing_started_at = clock_timestamp()
            WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE;
        """,
            (id_conversa, lock_version),
        )


def reler_conversa(contexto_banco, lock_version, cursor):
    anterior = contexto_banco["conversa"]
    proteger_conversa(anterior["id_conversa"], lock_version, cursor)
    cursor.execute(
        """
        SELECT id_etapa_atual, status_ativa, status_dependente, last_message_from,
               followup_stage, followup_last_sent_at, lead_no_funil, finalizou_em
        FROM chatbot.conversa
        WHERE id_conversa = %s AND id_cliente = %s AND id_unidade = %s;
    """,
        (
            anterior["id_conversa"],
            contexto_banco["id_cliente"],
            contexto_banco["id_unidade"],
        ),
    )
    row = cursor.fetchone()
    if row is None or row[1] is not True or row[7] is not None:
        raise LockConversaPerdido(
            "Conversa deixou de ser ativa para este cliente/unidade"
        )
    campos = (
        "id_etapa_atual",
        "status_ativa",
        "status_dependente",
        "last_message_from",
        "followup_stage",
        "followup_last_sent_at",
        "lead_no_funil",
        "finalizou_em",
    )
    conversa = dict(anterior, **dict(zip(campos, row)), lock_version=lock_version)
    stage = conversa["followup_stage"] or 0
    if stage < 0:
        raise ValueError("followup_stage negativo; requer saneamento explícito")
    return dict(contexto_banco, conversa=conversa)


def buscar_contexto_repeticao(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT cl.nome, d.nome_dependente, d.idade, u.nome_unidade, u.nome_agente,
               u.genero, u.link_agendamento, u.link_instagram,
               c.status_dependente, e.encerra_automaticamente
        FROM chatbot.conversa c
        JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
        JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
        JOIN chatbot.etapa e ON e.id_etapa = c.id_etapa_atual
        LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
        WHERE c.id_conversa = %s AND c.id_unidade = %s AND c.status_ativa IS TRUE;
    """,
        (id_conversa, id_unidade),
    )
    row = cursor.fetchone()
    if not row or row[-1]:
        raise ValueError("Etapa inexistente, encerrada ou terminal para repetição")
    return dict(
        zip(
            (
                "nome_cliente",
                "nome_dependente",
                "idade_dependente",
                "nome_unidade",
                "nome_agente",
                "genero",
                "link_agendamento",
                "link_instagram",
                "status_dependente",
                "terminal",
            ),
            row,
        )
    )


def buscar_retomada(id_conversa, mensagem, cursor):
    cursor.execute(
        """
        SELECT id_etapa, stage_anterior, followup_em, concluida_em
        FROM chatbot.followup_retomada
        WHERE id_conversa = %s AND id_mensagem_fila = %s AND id_hash_cliente = %s;
    """,
        (id_conversa, mensagem["id_mensagem"], mensagem["id_hash"]),
    )
    row = cursor.fetchone()
    return (
        dict(zip(("id_etapa", "stage_anterior", "followup_em", "concluida_em"), row))
        if row
        else None
    )


def registrar_retomada(conversa, mensagem, cursor):
    cursor.execute(
        """
        INSERT INTO chatbot.followup_retomada
            (id_conversa, id_mensagem_fila, id_hash_cliente, id_etapa, stage_anterior, followup_em)
        VALUES (%s, %s, %s, %s, %s, %s);
    """,
        (
            conversa["id_conversa"],
            mensagem["id_mensagem"],
            mensagem["id_hash"],
            conversa["id_etapa_atual"],
            conversa["followup_stage"],
            conversa["followup_last_sent_at"],
        ),
    )


def concluir_retomada(contexto, data_bot, cursor):
    proteger_conversa(contexto["id_conversa"], contexto["lock_version"], cursor)
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET followup_stage = 0, last_message_from = 'bot', last_interaction_at = %s
        WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE
          AND status_ativa IS TRUE AND finalizou_em IS NULL AND id_etapa_atual = %s
          AND followup_stage = %s AND followup_last_sent_at IS NOT DISTINCT FROM %s;
    """,
        (
            data_bot,
            contexto["id_conversa"],
            contexto["lock_version"],
            contexto["id_etapa_atual"],
            contexto["stage_anterior"],
            contexto["followup_em"],
        ),
    )
    if cursor.rowcount != 1:
        raise LockConversaPerdido(
            "Ciclo de follow-up mudou antes da confirmação da repetição"
        )
    msg = contexto["mensagem_cliente_atual"]
    cursor.execute(
        """
        UPDATE chatbot.followup_retomada SET concluida_em = %s
        WHERE id_conversa = %s AND id_mensagem_fila = %s AND id_hash_cliente = %s
          AND concluida_em IS NULL;
    """,
        (
            data_bot,
            contexto["id_conversa"],
            msg["id_mensagem_fila"],
            msg["id_hash_msg"],
        ),
    )
    if cursor.rowcount != 1:
        raise ValueError("Registro da retomada ausente ou já concluído")


# O SELECT é reexecutado com a posse do lock imediatamente antes do despacho.
# Pendências são filtradas pelo par cliente/unidade, inclusive sem id_conversa.
CONSULTA_ELEGIVEIS = """
    SELECT c.id_conversa, c.id_cliente, c.id_unidade, c.id_etapa_atual,
           cl.waid_telefone, u.phone_number_id, u.telefone,
           b.id_mensagem AS id_ancora, b.received_data_hora AS ancora_em
    FROM chatbot.conversa c
    JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
    JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
    JOIN chatbot.etapa e ON e.id_etapa = c.id_etapa_atual
    JOIN LATERAL (
        SELECT h.id_mensagem, h.received_data_hora
        FROM chatbot.historico_mensagens h
        WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'bot' AND h.status_envio = 'sent'
        ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1
    ) b ON TRUE
    WHERE c.status_ativa IS TRUE AND c.finalizou_em IS NULL
      AND c.id_etapa_atual BETWEEN 1 AND 17 AND e.encerra_automaticamente IS FALSE
      AND COALESCE(c.followup_stage, 0) = 0 AND c.last_message_from = 'bot'
      AND c.last_interaction_at = b.received_data_hora
      AND b.received_data_hora <= clock_timestamp() - INTERVAL '7 hours'
      AND c.turnos_sem_avanco < 12 AND u.status_pagamento IS TRUE
      AND NULLIF(TRIM(cl.waid_telefone), '') IS NOT NULL
      AND NULLIF(TRIM(u.phone_number_id), '') IS NOT NULL
      AND NULLIF(TRIM(u.telefone), '') IS NOT NULL

      AND NOT EXISTS (
          SELECT 1 FROM chatbot.conversa anterior
          JOIN chatbot.etapa terminal ON terminal.id_etapa = anterior.id_etapa_atual
          WHERE anterior.id_cliente = c.id_cliente AND anterior.id_unidade = c.id_unidade
            AND anterior.status_ativa IS FALSE AND terminal.bloqueio_dias > 0
            AND anterior.finalizou_em > clock_timestamp() - terminal.bloqueio_dias * INTERVAL '1 day'
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.webhook_flood_evento f
          WHERE f.wa_id_cliente = cl.waid_telefone AND f.phone_id_unidade = u.phone_number_id
            AND f.received_at >= clock_timestamp() - INTERVAL '5 seconds'
          GROUP BY f.wa_id_cliente, f.phone_id_unidade HAVING COUNT(*) >= 15
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.cliente_bloqueado_meta x
          WHERE x.wa_id_cliente = cl.waid_telefone AND x.phone_id_unidade = u.phone_number_id
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.fila_mensagens f
          WHERE (f.id_conversa = c.id_conversa OR
                 (f.cliente_telefone = cl.waid_telefone AND f.id_phone_unidade = u.phone_number_id))
            AND f.status IN ('pending', 'processing')
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.historico_mensagens h
          WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'cliente'
            AND h.received_data_hora >= b.received_data_hora
      )
      AND EXISTS (
          SELECT 1 FROM chatbot.historico_mensagens h
          WHERE h.id_conversa = c.id_conversa AND h.quem_enviou = 'cliente'
            AND h.received_data_hora > clock_timestamp() - INTERVAL '24 hours' + INTERVAL '1 minute'
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.followup_envio f WHERE f.id_conversa = c.id_conversa
            AND ((f.id_ancora = b.id_mensagem AND f.ancora_em = b.received_data_hora)
              OR (f.id_historico_bot = b.id_mensagem AND f.enviado_em = b.received_data_hora))
      )
      AND NOT EXISTS (
          SELECT 1 FROM chatbot.followup_retomada r
          WHERE r.id_conversa = c.id_conversa AND r.concluida_em IS NULL
            AND EXISTS (SELECT 1 FROM chatbot.fila_mensagens f
                        WHERE f.id_mensagem = r.id_mensagem_fila
                          AND f.id_hash_msg = r.id_hash_cliente
                          AND f.status IN ('pending', 'processing'))
      )
"""

COLUNAS_ELEGIVEL = (
    "id_conversa",
    "id_cliente",
    "id_unidade",
    "id_etapa",
    "cliente_telefone",
    "id_phone_unidade",
    "unidade_telefone",
    "id_ancora",
    "ancora_em",
)


def listar_elegiveis(cursor, limite=20, depois=None):
    parametros = []
    sql = CONSULTA_ELEGIVEIS
    if depois is not None:
        sql += " AND (b.received_data_hora, c.id_conversa) > (%s, %s)"
        parametros.extend(depois)
    sql += " ORDER BY b.received_data_hora, c.id_conversa LIMIT %s;"
    parametros.append(limite)
    cursor.execute(sql, parametros)
    return [dict(zip(COLUNAS_ELEGIVEL, row)) for row in cursor.fetchall()]


def reler_elegivel(id_conversa, cursor):
    cursor.execute(CONSULTA_ELEGIVEIS + " AND c.id_conversa = %s;", (id_conversa,))
    row = cursor.fetchone()
    return dict(zip(COLUNAS_ELEGIVEL, row)) if row else None


def persistir_followup(dados, envio, lock_version, cursor):
    proteger_conversa(dados["id_conversa"], lock_version, cursor)
    if not envio.get("id_hash_msg_bot") or not envio.get("enviou"):
        raise ValueError("Follow-up sem confirmação da Meta")
    cursor.execute(
        """
        INSERT INTO chatbot.historico_mensagens
            (id_conversa, id_etapa, received_data_hora, cliente_telefone, conteudo_texto,
             tipo_mensagem, id_hash_msg, id_mensagem_fila, id_hash_cliente_origem,
             id_phone_unidade, unidade_telefone, quem_enviou, status_envio)
        VALUES (%s, %s, clock_timestamp(), %s, %s, 'text', %s, NULL, NULL, %s, %s, 'bot', 'sent')
        RETURNING id_mensagem, received_data_hora;
    """,
        (
            dados["id_conversa"],
            dados["id_etapa"],
            dados["cliente_telefone"],
            envio["mensagem_bot"],
            envio["id_hash_msg_bot"],
            dados["id_phone_unidade"],
            dados["unidade_telefone"],
        ),
    )
    id_bot, data_bot = cursor.fetchone()
    cursor.execute(
        """
        INSERT INTO chatbot.followup_envio
            (id_conversa, id_ancora, ancora_em, id_historico_bot, enviado_em, id_hash_msg)
        VALUES (%s, %s, %s, %s, %s, %s);
    """,
        (
            dados["id_conversa"],
            dados["id_ancora"],
            dados["ancora_em"],
            id_bot,
            data_bot,
            envio["id_hash_msg_bot"],
        ),
    )
    # Uma entrada nova na fila após o despacho não invalida a confirmação da Meta.
    # O flow aguardará este lock e lerá stage 1 ao consumir aquela entrada.
    cursor.execute(
        """
        UPDATE chatbot.conversa
        SET followup_stage = 1, followup_last_sent_at = %s,
            last_message_from = 'bot', last_interaction_at = %s
        WHERE id_conversa = %s AND lock_version = %s AND processing IS TRUE
          AND status_ativa IS TRUE AND finalizou_em IS NULL AND id_etapa_atual = %s
          AND COALESCE(followup_stage, 0) = 0 AND last_message_from = 'bot'
          AND last_interaction_at = %s;
    """,
        (
            data_bot,
            data_bot,
            dados["id_conversa"],
            lock_version,
            dados["id_etapa"],
            dados["ancora_em"],
        ),
    )
    if cursor.rowcount != 1:
        raise LockConversaPerdido("Contexto mudou depois do despacho do follow-up")
    return id_bot, data_bot


def configurar_consulta_followup(cursor, *, sessao=False):
    if sessao:
        cursor.execute("SET statement_timeout = '15s'")
        cursor.execute("SET lock_timeout = '5s'")
    else:
        cursor.execute("SET LOCAL statement_timeout = '15s'")


def consultar_diagnostico(cursor):
    cursor.execute("SET TRANSACTION READ ONLY")
    configurar_consulta_followup(cursor)
    cursor.execute(
        "SELECT to_regclass('chatbot.followup_envio'), to_regclass('chatbot.followup_retomada'), to_regclass('chatbot.followup_legado')"
    )
    if not all(cursor.fetchone()):
        raise ValueError("SCHEMA_FOLLOWUP_AUSENTE")
    cursor.execute("""
        SELECT COUNT(*) FILTER (WHERE followup_stage > 0),
               COUNT(*) FILTER (WHERE followup_stage < 0),
               COUNT(*) FILTER (WHERE followup_stage > 1),
               COUNT(*) FILTER (WHERE last_interaction_at > clock_timestamp())
        FROM chatbot.conversa;
    """)
    positivos, negativos, legados, futuros = cursor.fetchone()
    cursor.execute("SELECT COUNT(*) FROM chatbot.followup_legado")
    marcadas_na_migracao = cursor.fetchone()[0]
    candidatos = listar_elegiveis(cursor, 10)
    return {
        "ciclos_aguardando_reacao": positivos,
        "conversas_marcadas_na_migracao": marcadas_na_migracao,
        "stages_negativos": negativos,
        "stages_maiores_que_um": legados,
        "horarios_futuros": futuros,
        "amostra_elegiveis": [
            {k: item[k] for k in ("id_conversa", "id_unidade", "id_etapa")}
            for item in candidatos
        ],
    }
```


---

# Parte 1 — Novo worker_followup: mensagem, envio e processo

## Passo 6 — `core/integrations/whatsapp/messages/followup_messages.py`

**Ação:** Criar.

Manter o texto aprovado no catálogo da integração, sem botões, prefixo ou personalização.

```python
"""Lembrete proativo e saudação da retomada com stage positivo."""

MENSAGEM_FOLLOWUP = "Você viu a minha mensagem?"


def montar_saudacao_retomada_followup(nome=None):
    """Usa somente o nome já persistido, sem interpretar a nova mensagem."""
    nome_normalizado = " ".join(nome.split()) if isinstance(nome, str) else ""
    if nome_normalizado:
        return f"Que bom te ver novamente, {nome_normalizado}!\n\n"
    return "Que bom te ver novamente!\n\n"
```

## Passo 7 — `core/integrations/whatsapp/pywa_functions/cliente.py`

**Ação:** Alterar.

Aceitar uma sessão HTTP opcional no cliente PyWa compartilhado, mantendo as chamadas antigas e o escopo atual de prefixos.

```python
from contextlib import contextmanager
from contextvars import ContextVar

from pywa import WhatsApp

from core.integrations.whatsapp.tools.config import (
    TOKEN_USUARIO_META,
    get_meta_graph_api_version,
)

_PREFIXO_MENSAGEM_BOT = ContextVar(
    "prefixo_mensagem_bot",
    default=None,
)


def conta_wa(phone_id, token=TOKEN_USUARIO_META, *, session=None):
    phone_id = _normalizar_phone_id(phone_id)

    opcoes = {"session": session} if session is not None else {}
    cliente = WhatsApp(
        token=token,
        phone_id=phone_id,
        api_version=get_meta_graph_api_version(),
        **opcoes,
    )

    if _PREFIXO_MENSAGEM_BOT.get():
        return _ClienteWhatsAppComPrefixo(cliente)

    return cliente


@contextmanager
def usar_prefixo_mensagem_bot(prefixo):
    """Limita o prefixo à resolução corrente, inclusive sob exceção."""
    prefixo_normalizado = prefixo if isinstance(prefixo, str) else None
    token = _PREFIXO_MENSAGEM_BOT.set(prefixo_normalizado or None)

    try:
        yield
    finally:
        _PREFIXO_MENSAGEM_BOT.reset(token)


def aplicar_prefixo_mensagem_bot(texto, prefixo=None):
    prefixo = prefixo if prefixo is not None else _PREFIXO_MENSAGEM_BOT.get()

    if not prefixo or not isinstance(texto, str):
        return texto

    if texto.startswith(prefixo):
        return texto

    return f"{prefixo}{texto}"


class _ClienteWhatsAppComPrefixo:
    """Decora textos enviados no escopo corrente do flow sender."""

    def __init__(self, cliente):
        self._cliente = cliente

    def send_message(self, *args, **kwargs):
        return self._enviar_com_prefixo(
            self._cliente.send_message,
            args,
            kwargs,
        )

    def request_contact_info(self, *args, **kwargs):
        return self._enviar_com_prefixo(
            self._cliente.request_contact_info,
            args,
            kwargs,
        )

    @staticmethod
    def _enviar_com_prefixo(metodo, args, kwargs):
        if "text" in kwargs:
            kwargs = dict(kwargs)
            kwargs["text"] = aplicar_prefixo_mensagem_bot(kwargs["text"])

        return metodo(*args, **kwargs)

    def __getattr__(self, nome):
        return getattr(self._cliente, nome)


def _normalizar_phone_id(phone_id):
    if phone_id is None:
        raise ValueError("phone_id da unidade nao informado")

    phone_id = str(phone_id).strip()

    if not phone_id:
        raise ValueError("phone_id da unidade vazio")

    return phone_id
```

## Passo 8 — `core/integrations/whatsapp/pywa_functions/pywa_senders/followup.py`

**Ação:** Criar.

Enviar somente o texto aprovado, com destinatário e phone_id recebidos do worker. Encerrar a sessão e devolver o ID real confirmado pela Meta.

```python
"""Envia texto proativo sem fila fictícia, prefixo de retorno ou transição."""

import httpx

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.followup_messages import MENSAGEM_FOLLOWUP
from core.integrations.whatsapp.pywa_functions.cliente import (
    conta_wa,
    usar_prefixo_mensagem_bot,
)
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)


def enviar_followup(cliente_telefone, phone_id_unidade):
    try:
        # Sem retry HTTP automático: resultado incerto exige observação no worker.
        with httpx.Client(timeout=httpx.Timeout(20, connect=5)) as session:
            with usar_prefixo_mensagem_bot(None):
                cliente = conta_wa(phone_id_unidade, session=session)
                retorno = cliente.send_message(
                    to=cliente_telefone, text=MENSAGEM_FOLLOWUP
                )
        return {
            "enviou": True,
            "id_hash_msg_bot": extrair_id_hash_msg_bot(retorno),
            "mensagem_bot": MENSAGEM_FOLLOWUP,
            "tipo_mensagem": "text",
        }
    except Exception as exc:
        raise ErroEnvioMeta(
            "Falha no envio proativo de follow-up",
            id_etapa=None,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from exc
```

## Passo 9 — `workers/worker_followup/__init__.py`

**Ação:** Criar.

Declarar o pacote do novo serviço, sem inicialização de laços na importação.

```python
"""Worker proativo de inatividade, independente da fila de mensagens."""
```

## Passo 10 — `workers/worker_followup/config.py`

**Ação:** Criar.

Ler ativação, lote e intervalo operacional. As sete horas não são uma configuração ajustável pelo cliente do painel.

```python
from dataclasses import dataclass

from core.config_env import env_bool, env_int


@dataclass(frozen=True)
class ConfigFollowup:
    habilitado: bool
    intervalo: int
    lote: int


def carregar_config():
    intervalo = env_int("FOLLOWUP_POLL_SECONDS", 60)
    lote = env_int("FOLLOWUP_BATCH_SIZE", 20)
    if not 5 <= intervalo <= 3600 or not 1 <= lote <= 100:
        raise ValueError("FOLLOWUP_POLL_SECONDS: 5..3600; FOLLOWUP_BATCH_SIZE: 1..100")
    return ConfigFollowup(env_bool("FOLLOWUP_WORKER_ENABLED", False), intervalo, lote)
```

## Passo 11 — `workers/worker_followup/followup_worker.py`

**Ação:** Criar.

Implementar a seleção paginada e o ciclo proativo com conexão por conversa, lock compartilhado, releitura, envio, commit e liberação condicionada.

```python
"""Propriedade transacional do ciclo proativo; não consome fila nem etapas."""

import logging
from datetime import timedelta
from time import monotonic

from core.database.connection_aws import get_conn
from core.repositories.atendimento.conversas import (
    tentar_lock_conversa,
    unlock_conversa,
)
from core.repositories.atendimento.followup import (
    configurar_consulta_followup,
    listar_elegiveis,
    persistir_followup,
    proteger_conversa,
    reler_elegivel,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.followup import (
    enviar_followup,
)

logger = logging.getLogger("worker.followup")


def obter_lote(limite, depois=None):
    with get_conn(application_name="worker_followup_scan", connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            configurar_consulta_followup(cursor)
            return listar_elegiveis(cursor, limite, depois)


def processar_candidato(candidato, parar):
    inicio = monotonic()
    conn = get_conn(application_name="worker_followup", connect_timeout=10)
    versao = None
    envio = None
    id_conversa = candidato["id_conversa"]
    try:
        with conn.cursor() as cursor:
            configurar_consulta_followup(cursor, sessao=True)
            lock_ok, versao_obtida = tentar_lock_conversa(id_conversa, cursor)
            conn.commit()
            if not lock_ok:
                logger.debug(
                    "followup_descartado | conversa=%s motivo=lock_ocupado", id_conversa
                )
                return False
            versao = versao_obtida
            proteger_conversa(id_conversa, versao, cursor, renovar=True)
            dados = reler_elegivel(id_conversa, cursor)
            conn.commit()
            if dados is None or parar.is_set():
                logger.debug(
                    "followup_descartado | conversa=%s motivo=%s versao=%s",
                    id_conversa,
                    "parada_solicitada" if parar.is_set() else "guard_revalidacao",
                    versao,
                )
                return False
            logger.info(
                "followup_despacho | conversa=%s cliente_id=%s unidade=%s etapa=%s "
                "stage_anterior=0 stage_proposto=1 ancora_id=%s ancora_em=%s vence_em=%s versao=%s",
                id_conversa,
                dados["id_cliente"],
                dados["id_unidade"],
                dados["id_etapa"],
                dados["id_ancora"],
                dados["ancora_em"],
                dados["ancora_em"] + timedelta(hours=7),
                versao,
            )
            # Releitura já inclui histórico, fila, bloqueios, unidade e janela Meta.
            envio = enviar_followup(
                dados["cliente_telefone"], dados["id_phone_unidade"]
            )
            id_bot, _ = persistir_followup(dados, envio, versao, cursor)
            conn.commit()
            logger.info(
                "followup_confirmado | conversa=%s unidade=%s etapa=%s stage=1 versao=%s historico=%s",
                id_conversa,
                dados["id_unidade"],
                dados["id_etapa"],
                versao,
                id_bot,
            )
            return True
    except Exception:
        conn.rollback()
        if envio and envio.get("enviou"):
            logger.critical(
                "followup_commit_falhou | conversa=%s versao=%s id_hash_msg=%s risco=duplicidade",
                id_conversa,
                versao,
                envio.get("id_hash_msg_bot"),
                exc_info=True,
            )
        else:
            logger.exception(
                "followup_falhou | conversa=%s versao=%s stage_preservado=true",
                id_conversa,
                versao,
            )
        return False
    finally:
        try:
            if versao is not None:
                with conn.cursor() as cursor:
                    unlock_conversa(id_conversa, versao, cursor)
                conn.commit()
        except Exception:
            conn.rollback()
            logger.exception(
                "followup_unlock_falhou | conversa=%s versao=%s", id_conversa, versao
            )
        finally:
            conn.close()
            logger.debug(
                "followup_ciclo_final | conversa=%s duracao_ms=%.0f",
                id_conversa,
                (monotonic() - inicio) * 1000,
            )


def executar_worker(config, parar):
    depois = None
    falhas_scan = 0
    while not parar.is_set():
        try:
            candidatos = obter_lote(config.lote, depois)
            falhas_scan = 0
            for candidato in candidatos:
                if parar.is_set():
                    break
                try:
                    processar_candidato(candidato, parar)
                except Exception:
                    # Inclui falhas de conexão/limpeza fora do try do processamento.
                    logger.exception(
                        "followup_candidata_falhou | conversa=%s acao=seguir_lote",
                        candidato["id_conversa"],
                    )
                depois = (candidato["ancora_em"], candidato["id_conversa"])
            if len(candidatos) < config.lote:
                depois = None
            # Limite por rodada também evita tempestade de retry sem resposta confirmada.
            parar.wait(config.intervalo)
        except Exception:
            falhas_scan += 1
            espera = min(300, 5 * (2 ** min(falhas_scan - 1, 6)))
            logger.exception("followup_scan_falhou | retry_em=%s", espera)
            parar.wait(espera)
```

## Passo 12 — `workers/worker_followup/iniciar_worker_followup.py`

**Ação:** Criar.

Criar o ponto de entrada do processo, configurar logging e aceitar SIGTERM/SIGINT antes de iniciar outro despacho.

```python
import logging
import signal
from threading import Event

from core.logging_config import setup_logging
from workers.worker_followup.config import carregar_config


def main():
    setup_logging()
    config = carregar_config()
    logger = logging.getLogger("worker.followup.main")
    parar = Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: parar.set())
    if not config.habilitado:
        logger.info("followup_desabilitado | nenhum_envio=true")
        return
    from workers.worker_followup.followup_worker import executar_worker

    logger.info(
        "followup_iniciado | lote=%s intervalo=%s lembretes_por_ciclo=1",
        config.lote,
        config.intervalo,
    )
    executar_worker(config, parar)
    logger.info("followup_encerrado")


if __name__ == "__main__":
    main()
```

## Passo 13 — `deploy/systemd/chatbot-worker-followup.service`

**Ação:** Criar.

Definir o quarto serviço, com a mesma conta e restrições dos workers atuais. Instalar a unit não inicia o serviço; a ativação fica para depois do flow compatível.

```ini
[Unit]
Description=Chatbot - lembrete após sete horas sem resposta
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=chatbot
Group=chatbot
WorkingDirectory=/opt/chatbot/app
EnvironmentFile=/etc/chatbot/chatbot.env
Environment=PYTHONPATH=/opt/chatbot/app
Environment=PYTHONUNBUFFERED=1
Environment=FOLLOWUP_WORKER_ENABLED=true
Environment=FOLLOWUP_POLL_SECONDS=60
Environment=FOLLOWUP_BATCH_SIZE=20
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/chatbot/venv/bin/python -m workers.worker_followup.iniciar_worker_followup
Restart=on-failure
RestartSec=5s
TimeoutStopSec=100s
KillSignal=SIGTERM
StandardOutput=journal
StandardError=journal
SyslogIdentifier=chatbot-worker-followup

NoNewPrivileges=true
PrivateDevices=true
PrivateTmp=true
ProtectControlGroups=true
ProtectHome=true
ProtectKernelLogs=true
ProtectKernelModules=true
ProtectKernelTunables=true
ProtectSystem=full
RestrictSUIDSGID=true
UMask=0027

[Install]
WantedBy=multi-user.target
```


---

# Parte 2 — Worker_flow: reação, repetição e reset

## Passo 14 — `workers/worker_flow/response_flow/repeticao_followup.py`

**Ação:** Criar.

Reutilizar os senders normais de cada etapa e suas mensagens dinâmicas. Selecionar um conteúdo para repetir não produz aresta, evento ou validação da reação.

```python
"""Repete conteúdo de etapa sem interpretar a reação nem resolver transições."""

from core.integrations.whatsapp.messages.componentes_compartilhados import (
    montar_texto_com_cabecalho,
)
from core.integrations.whatsapp.messages.followup_messages import (
    montar_saudacao_retomada_followup,
)
from core.integrations.whatsapp.pywa_functions.cliente import (
    aplicar_prefixo_mensagem_bot,
    usar_prefixo_mensagem_bot,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa1,
    etapa2,
    etapa3,
    etapa4,
    etapa5,
    etapa6,
    etapa7,
    etapa8,
    etapa9,
    etapa10,
    etapa11,
    etapa12,
    etapa13,
    etapa14,
    etapa15,
    etapa16,
    etapa17,
    etapa18,
    etapa19,
    etapa20,
    etapa21,
)

from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_1_NOME_CLIENTE,
    ETAPA_2_DESTINO_ATENDIMENTO,
    ETAPA_3_CONFIRMACAO_DESTINO,
    ETAPA_4_PROFISSAO,
    ETAPA_5_NOME_DEPENDENTE,
    ETAPA_6_IDADE_ALUNO,
    ETAPA_7_OFERTA_AULA,
    ETAPA_8_OFERTA_ADIADA,
    ETAPA_9_RETORNO_OFERTA,
    ETAPA_10_EMAIL,
    ETAPA_11_INTRODUCAO_TRIAGEM,
    ETAPA_12_TRIAGEM_PERGUNTA_1,
    ETAPA_13_TRIAGEM_PERGUNTA_2,
    ETAPA_14_TRIAGEM_PERGUNTA_3,
    ETAPA_15_TRIAGEM_PERGUNTA_4,
    ETAPA_16_TRIAGEM_PERGUNTA_5,
    ETAPA_17_TRIAGEM_PERGUNTA_6,
    ETAPA_18_AGENDAMENTO,
    ETAPA_19_PESQUISA_SATISFACAO,
    ETAPA_20_DECISAO_COMENTARIO,
    ETAPA_21_COMENTARIO_SATISFACAO,
)

SENDERS_SIMPLES = {
    ETAPA_4_PROFISSAO: etapa4.enviar_etapa4,
    ETAPA_5_NOME_DEPENDENTE: etapa5.enviar_etapa5,
    ETAPA_10_EMAIL: etapa10.enviar_etapa10,
    ETAPA_11_INTRODUCAO_TRIAGEM: etapa11.enviar_etapa11,
    ETAPA_20_DECISAO_COMENTARIO: etapa20.enviar_etapa20,
    ETAPA_21_COMENTARIO_SATISFACAO: etapa21.enviar_etapa21,
}
SENDERS_TRIAGEM = {
    ETAPA_12_TRIAGEM_PERGUNTA_1: (
        etapa12.enviar_etapa12_cliente,
        etapa12.enviar_etapa12_dependente,
    ),
    ETAPA_13_TRIAGEM_PERGUNTA_2: (
        etapa13.enviar_etapa13_cliente,
        etapa13.enviar_etapa13_dependente,
    ),
    ETAPA_14_TRIAGEM_PERGUNTA_3: (
        etapa14.enviar_etapa14_cliente,
        etapa14.enviar_etapa14_dependente,
    ),
    ETAPA_15_TRIAGEM_PERGUNTA_4: (
        etapa15.enviar_etapa15_cliente,
        etapa15.enviar_etapa15_dependente,
    ),
    ETAPA_16_TRIAGEM_PERGUNTA_5: (
        etapa16.enviar_etapa16_cliente,
        etapa16.enviar_etapa16_dependente,
    ),
    ETAPA_17_TRIAGEM_PERGUNTA_6: (
        etapa17.enviar_etapa17_cliente,
        etapa17.enviar_etapa17_dependente,
    ),
}


def _texto(dados, chave):
    valor = dados.get(chave)
    if not isinstance(valor, str) or not valor.strip():
        raise ValueError(f"Dado persistido ausente para repetição: {chave}")
    return valor.strip()


def _selecionar_sender(etapa, dados):
    dependente = dados.get("status_dependente")
    if not isinstance(dependente, bool):
        raise ValueError("Destino de atendimento ausente para repetição")
    if etapa in SENDERS_SIMPLES:
        return SENDERS_SIMPLES[etapa], ()
    if etapa in SENDERS_TRIAGEM:
        titular, dp = SENDERS_TRIAGEM[etapa]
        if not dependente:
            return titular, ()
        idade = dados.get("idade_dependente")
        if type(idade) is not int or not 4 <= idade < 100:
            raise ValueError("Idade do dependente inválida para triagem")
        return dp, (_texto(dados, "nome_dependente"), idade)
    if etapa == ETAPA_1_NOME_CLIENTE:
        return etapa1.enviar_etapa1, tuple(
            _texto(dados, k) for k in ("nome_unidade", "nome_agente", "genero")
        )
    if etapa == ETAPA_2_DESTINO_ATENDIMENTO:
        return etapa2.enviar_etapa2, (_texto(dados, "nome_cliente"),)
    if etapa == ETAPA_3_CONFIRMACAO_DESTINO:
        return etapa3.enviar_etapa3, (dependente,)
    if etapa == ETAPA_6_IDADE_ALUNO:
        return (
            (etapa6.enviar_etapa6_dependente, (_texto(dados, "nome_dependente"),))
            if dependente
            else (etapa6.enviar_etapa6_cliente, ())
        )
    if etapa == ETAPA_7_OFERTA_AULA:
        return (
            (etapa7.enviar_etapa7_dependente, (_texto(dados, "nome_dependente"),))
            if dependente
            else (etapa7.enviar_etapa7_cliente, (_texto(dados, "nome_cliente"),))
        )
    if etapa == ETAPA_8_OFERTA_ADIADA:
        return etapa8.enviar_etapa8, (dados.get("link_instagram"),)
    if etapa == ETAPA_9_RETORNO_OFERTA:
        nome = _texto(dados, "nome_cliente")
        return (
            (etapa9.enviar_etapa9_dependente, (nome, _texto(dados, "nome_dependente")))
            if dependente
            else (etapa9.enviar_etapa9_cliente, (nome,))
        )
    if etapa == ETAPA_18_AGENDAMENTO:
        return etapa18.enviar_etapa18, (_texto(dados, "link_agendamento"),)
    if etapa == ETAPA_19_PESQUISA_SATISFACAO:
        return etapa19.enviar_etapa19, (_texto(dados, "nome_cliente"),)
    raise ValueError(f"Etapa não repetível: {etapa}")


def enviar_repeticao_followup(contexto):
    resposta = contexto.get("resposta_bot_para_mensagem_atual")
    if resposta:
        return {
            "enviou": False,
            "resposta_ja_existia": True,
            "id_hash_msg_bot": resposta["id_hash_msg"],
            "id_etapa_resultante": contexto["id_etapa_atual"],
        }
    sender, extras = _selecionar_sender(
        contexto["id_etapa_atual"], contexto["dados_repeticao"]
    )
    mensagem = contexto["mensagem_cliente_atual"]
    saudacao = montar_saudacao_retomada_followup(
        contexto["dados_repeticao"].get("nome_cliente")
    )
    with usar_prefixo_mensagem_bot(saudacao):
        envio = sender(
            mensagem["cliente_telefone"], mensagem["id_phone_unidade"], *extras
        )
    # O cabeçalho já foi ao WhatsApp no corpo. O histórico recebe o mesmo texto.
    texto = envio["mensagem_bot"]
    if envio.get("cabecalho_mensagem"):
        texto = montar_texto_com_cabecalho(texto, envio["cabecalho_mensagem"])
    texto = aplicar_prefixo_mensagem_bot(texto, saudacao)
    return {
        "enviou": envio["enviou"],
        "resposta_ja_existia": False,
        "id_hash_msg_bot": envio["id_hash_msg_bot"],
        "mensagem_bot": texto,
        "tipo_mensagem": envio["tipo_mensagem"],
        "id_etapa_resultante": contexto["id_etapa_atual"],
    }
```

## Passo 15 — `workers/worker_flow/transacoes/retorno_followup.py`

**Ação:** Criar.

Registrar a reação e seu motivo, reconhecer a repetição já gravada em retries e confirmar o reset na mesma transação da resposta.

```python
"""Checkpoint de reação e persistência da repetição; nunca controla commits."""

import logging

from core.repositories.atendimento.conversas import atualizar_conversa_mensagem_cliente
from core.repositories.atendimento.followup import (
    buscar_contexto_repeticao,
    buscar_retomada,
    concluir_retomada,
    registrar_retomada,
)
from core.repositories.atendimento.historico import (
    buscar_resposta_bot_por_mensagem_cliente,
    inserir_historico_mensagem_cliente,
    inserir_historico_mensagem_bot,
)

logger = logging.getLogger("worker.retorno_followup")


def preparar_retorno_followup(mensagem, contexto_banco, cursor):
    conversa = contexto_banco["conversa"]
    id_conversa = conversa["id_conversa"]
    stage = conversa.get("followup_stage") or 0
    if stage < 0:
        raise ValueError("followup_stage negativo")
    retomada = buscar_retomada(id_conversa, mensagem, cursor)
    if stage == 0 and retomada is None:
        return None
    resposta = buscar_resposta_bot_por_mensagem_cliente(
        id_conversa,
        mensagem["id_mensagem"],
        mensagem["id_hash"],
        cursor,
    )
    # Uma resposta de turno normal já persistida tem prioridade sobre stage atual.
    if resposta and retomada is None:
        return None
    if retomada and retomada["concluida_em"] is not None and not resposta:
        raise ValueError(
            "Retomada concluída sem histórico correspondente; não reenviar"
        )
    if resposta and retomada["concluida_em"] is None:
        raise ValueError("Resposta sem confirmação atômica da retomada")
    if (
        retomada
        and not resposta
        and (
            stage != retomada["stage_anterior"]
            or conversa.get("followup_last_sent_at") != retomada["followup_em"]
            or conversa.get("id_etapa_atual") != retomada["id_etapa"]
        )
    ):
        raise ValueError("Retomada pendente pertence a outro contexto")

    dados = None
    if not resposta:
        etapa = conversa.get("id_etapa_atual")
        if type(etapa) is not int or not 1 <= etapa <= 21:
            raise ValueError("Retorno de follow-up sem etapa repetível")
        dados = buscar_contexto_repeticao(
            id_conversa, contexto_banco["id_unidade"], cursor
        )
        if retomada is None:
            registrar_retomada(conversa, mensagem, cursor)
            retomada = {
                "id_etapa": etapa,
                "stage_anterior": stage,
                "followup_em": conversa.get("followup_last_sent_at"),
                "concluida_em": None,
            }

    id_cliente_hist, recebido_em, etapa_cliente, inserido = (
        inserir_historico_mensagem_cliente(
            mensagem,
            id_conversa,
            retomada["id_etapa"],
            cursor,
        )
    )
    msg = {
        "id_mensagem": id_cliente_hist,
        "id_conversa": id_conversa,
        "id_etapa": etapa_cliente,
        "received_data_hora": recebido_em,
        "cliente_telefone": mensagem["cliente_telefone"],
        "conteudo_texto": mensagem["conteudo_texto"],
        "tipo_mensagem": mensagem["tipo_mensagem"],
        "id_hash_msg": mensagem["id_hash"],
        "id_mensagem_fila": mensagem["id_mensagem"],
        "id_phone_unidade": mensagem["id_phone_unidade"],
        "unidade_telefone": mensagem["unidade_telefone"],
    }
    if not resposta:
        atualizar_conversa_mensagem_cliente(id_conversa, recebido_em, cursor)
    resposta_normalizada = None
    if resposta:
        resposta_normalizada = {
            "id_mensagem": resposta[0],
            "received_data_hora": resposta[3],
            "id_hash_msg": resposta[7],
        }
    logger.info(
        "resposta_followup | conversa=%s unidade=%s stage=%s etapa=%s versao=%s recuperada=%s",
        id_conversa,
        contexto_banco["id_unidade"],
        retomada["stage_anterior"],
        retomada["id_etapa"],
        conversa["lock_version"],
        bool(resposta),
    )
    return {
        "retorno_followup": True,
        "id_conversa": id_conversa,
        "id_cliente": contexto_banco["id_cliente"],
        "id_unidade": contexto_banco["id_unidade"],
        "lock_version": conversa["lock_version"],
        "id_etapa_atual": retomada["id_etapa"],
        "id_etapa_cliente": etapa_cliente,
        "id_etapa_resposta": retomada["id_etapa"],
        "stage_anterior": retomada["stage_anterior"],
        "followup_em": retomada["followup_em"],
        "dados_repeticao": dados,
        "mensagem_cliente_atual": msg,
        "mensagem_cliente_inserida": inserido,
        "resposta_bot_para_mensagem_atual": resposta_normalizada,
    }


def persistir_retorno_followup(contexto, envio, cursor):
    resposta = contexto.get("resposta_bot_para_mensagem_atual")
    if resposta:
        # Replay não zera um possível ciclo novo nem altera last_interaction_at.
        id_bot, data_bot, inserido = (
            resposta["id_mensagem"],
            resposta["received_data_hora"],
            False,
        )
    else:
        if (
            not envio.get("enviou")
            or envio.get("id_etapa_resultante") != contexto["id_etapa_atual"]
        ):
            raise ValueError("Repetição não confirmada ou mudou de etapa")
        id_bot, data_bot, inserido = inserir_historico_mensagem_bot(
            contexto, envio, cursor
        )
        concluir_retomada(contexto, data_bot, cursor)
    return {
        "historico_bot_inserido": inserido,
        "resposta_ja_existia": bool(resposta),
        "id_hash_msg_bot": envio["id_hash_msg_bot"],
        "id_historico_bot": id_bot,
        "data_historico_bot": data_bot,
        "id_etapa_resultante": contexto["id_etapa_atual"],
        "movimento_conversa": "sem_avanco",
        "atualizar_conversa": False,
        "atualizar_last_from_bot": not bool(resposta),
        "intencao_encerramento": None,
    }
```

## Passo 16 — `workers/worker_flow/response_flow/flow_worker.py`

**Ação:** Alterar.

Integrar a bifurcação ao orquestrador existente. Reler a conversa sob lock, renovar a posse antes do envio e preservar a sequência de histórico, resposta, sent e unlock.

```python
import logging

import psycopg
from core.cache.cache_unidade import UnidadeNaoEncontrada
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.logging_config import short_value
from core.repositories.atendimento.conversas import tentar_lock_conversa
from core.repositories.atendimento.followup import (
    LockConversaPerdido,
    proteger_conversa,
    reler_conversa,
)
from workers.worker_flow.response_flow.repeticao_followup import (
    enviar_repeticao_followup,
)
from workers.worker_flow.transacoes.retorno_followup import (
    preparar_retorno_followup,
    persistir_retorno_followup,
)
from core.repositories.atendimento.fila import (
    pegar_mensagens_da_fila,
    reagendar_mensagem_sem_erro,
    vincular_mensagem_fila_a_conversa,
)
from workers.tratamento_erros_externos.erro_conexao import handle_erro_conexao
from workers.tratamento_erros_externos.erro_generico import handle_erro_generico
from workers.tratamento_erros_externos.exceptions import BancoFalhouAposEnvioMeta
from workers.tratamento_erros_externos.unidade_nao_encontrada import (
    handle_unidade_nao_encontrada,
)
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
    registrar_cache_bloqueio_apos_commit,
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

            if reagendar_se_houver_mensagem_anterior(
                mensagem,
                cursor_ciclo,
            ):
                conn_ciclo.commit()
                continue

            contexto_banco = validar_banco_mensagem(
                mensagem,
                cursor_ciclo,
            )
            atualizar_estado_com_contexto(estado_ciclo, contexto_banco)

            contexto_conversa = contexto_banco["conversa"]
            id_conversa = contexto_conversa["id_conversa"]

            conn_ciclo.commit()
            logger.debug(
                "contexto_banco_confirmado | acao=commit id_mensagem=%s id_conversa_calculada=%s estado=%s",
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
                reagendar_mensagem_sem_erro(
                    mensagem["id_mensagem"],
                    cursor_ciclo,
                    delay_seconds=5,
                )
                conn_ciclo.commit()
                continue

            linhas_vinculadas = vincular_mensagem_fila_a_conversa(
                mensagem["id_mensagem"],
                id_conversa,
                cursor_ciclo,
            )

            if linhas_vinculadas == 0:
                logger.critical(
                    "mensagem_conversa_vinculo_inconsistente | "
                    "motivo=historico_conflitante_ou_fila_ausente "
                    "acao=reagendar_sem_consumir_retry id_mensagem=%s "
                    "cliente=%s phone_number_id=%s "
                    "id_conversa_calculada=%s",
                    mensagem["id_mensagem"],
                    short_value(mensagem["cliente_telefone"]),
                    short_value(mensagem["id_phone_unidade"]),
                    id_conversa,
                )
                reagendar_mensagem_sem_erro(
                    mensagem["id_mensagem"],
                    cursor_ciclo,
                    delay_seconds=300,
                )
                conn_ciclo.commit()
                continue

            contexto_banco = reler_conversa(contexto_banco, lock_version, cursor_ciclo)
            contexto_conversa = contexto_banco["conversa"]
            contexto_historico = preparar_retorno_followup(
                mensagem,
                contexto_banco,
                cursor_ciclo,
            )
            if contexto_historico is None:
                contexto_historico = valida_historico(
                    mensagem, contexto_banco, cursor_ciclo
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

            proteger_conversa(id_conversa, lock_version, cursor_ciclo, renovar=True)
            conn_ciclo.commit()
            if contexto_historico.get("retorno_followup"):
                contexto_envio = enviar_repeticao_followup(contexto_historico)
            else:
                contexto_envio = flow_sender(contexto_historico)

            try:
                proteger_conversa(id_conversa, lock_version, cursor_ciclo)
                persistir = (
                    persistir_retorno_followup
                    if contexto_historico.get("retorno_followup")
                    else atualizar_banco_com_contexto_final
                )
                contexto_final = persistir(
                    contexto_historico, contexto_envio, cursor_ciclo
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
                "resposta_bot_contexto_final_ok | acao=commit id_mensagem=%s id_conversa=%s etapa=%s resposta_ja_existia=%s id_hash_msg_bot=%s tratamento=%s tipo_tratamento=%s",
                mensagem["id_mensagem"],
                id_conversa,
                contexto_final["id_etapa_resultante"],
                contexto_final["resposta_ja_existia"],
                contexto_final["id_hash_msg_bot"],
                contexto_envio.get("tratamento", False),
                contexto_envio.get("tipo_tratamento"),
            )

            proteger_conversa(id_conversa, lock_version, cursor_ciclo)
            resultado_encerramento = finalizar_mensagem_processada(
                mensagem,
                contexto_banco,
                lock_version,
                cursor_ciclo,
                contexto_final,
            )
            conn_ciclo.commit()

            registrar_cache_bloqueio_apos_commit(
                mensagem,
                resultado_encerramento,
            )

        except LockConversaPerdido:
            if conn_ciclo:
                conn_ciclo.rollback()
            # Não reescreve uma fila que pode estar sendo processada pelo novo dono.
            logger.warning(
                "lock_perdido | acao=aguardar_recuperacao_fila id_conversa=%s",
                estado_ciclo["id_conversa"],
            )

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
            if isinstance(erro.__cause__, LockConversaPerdido):
                conn_ciclo.rollback()
                logger.critical(
                    "meta_confirmou_com_lock_perdido | conversa=%s hash=%s risco=duplicidade",
                    erro.id_conversa,
                    erro.id_hash_msg_bot,
                )
                continue
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

        except psycopg.OperationalError as erro:
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


---

# Verificação e diagnóstico — arquivos completos

## Passo 17 — `tests/unit/test_worker_flow_runtime.py`

**Ação:** Alterar.

Preservar as verificações de ordem existentes e acrescentar o desvio para retorno de follow-up e a recusa de escrita por quem perdeu o lock.

```python
import unittest
from contextlib import ExitStack
from datetime import datetime
from unittest.mock import patch

from tests.helpers import FakeConn, FakeCursor
from workers.worker_flow.response_flow import flow_worker
from workers.worker_flow.suporte import estado_ciclo


class PararWorker(BaseException):
    pass


def registro_fila():
    return (
        7,
        "5571999999999",
        "Ola",
        "text",
        "123456",
        "5571000000000",
        datetime(2026, 6, 18, 10, 0),
        "wamid.cliente.7",
        1,
    )


def contexto_banco():
    return {
        "id_unidade": 2,
        "id_cliente": 6,
        "cliente_telefone": "5571999999999",
        "id_phone_unidade": "123456",
        "cliente_inserido": False,
        "cliente_cache_pendente": False,
        "conversa": {
            "id_conversa": 10,
            "estado": "ativa",
        },
    }


def contexto_historico():
    return {
        "id_conversa": 10,
        "id_etapa_atual": None,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": 1,
        "mensagem_cliente_inserida": True,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 7,
            "id_hash_msg": "wamid.cliente.7",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
        "retry_count": 1,
    }


def contexto_envio():
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
        "id_etapa_resultante": 1,
        "tipo_mensagem": "text",
    }


def contexto_final():
    return {
        "id_etapa_resultante": 1,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": "wamid.bot.7",
    }


class WorkerFlowRuntimeTests(unittest.TestCase):

    def test_reacao_followup_desvia_validadores_e_persistencia_normal(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            cx = dict(contexto_historico(), retorno_followup=True)
            stack.enter_context(
                patch.object(flow_worker, "preparar_retorno_followup", return_value=cx)
            )
            normal_historico = stack.enter_context(
                patch.object(flow_worker, "valida_historico")
            )
            normal_sender = stack.enter_context(
                patch.object(flow_worker, "flow_sender")
            )
            normal_persistencia = stack.enter_context(
                patch.object(flow_worker, "atualizar_banco_com_contexto_final")
            )
            repetir = stack.enter_context(
                patch.object(
                    flow_worker,
                    "enviar_repeticao_followup",
                    return_value=contexto_envio(),
                )
            )
            persistir = stack.enter_context(
                patch.object(
                    flow_worker,
                    "persistir_retorno_followup",
                    return_value=contexto_final(),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    return_value={"atendimento_encerrado": False},
                )
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        normal_historico.assert_not_called()
        normal_sender.assert_not_called()
        normal_persistencia.assert_not_called()
        repetir.assert_called_once()
        persistir.assert_called_once()
        finalizar.assert_called_once()

    def test_lock_perdido_nao_envia_nem_reescreve_fila(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "proteger_conversa",
                    side_effect=flow_worker.LockConversaPerdido,
                )
            )
            enviar = stack.enter_context(patch.object(flow_worker, "flow_sender"))
            reagendar = stack.enter_context(
                patch.object(flow_worker, "reagendar_mensagem_sem_erro")
            )
            finalizar = stack.enter_context(
                patch.object(flow_worker, "finalizar_mensagem_processada")
            )
            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()
        enviar.assert_not_called()
        reagendar.assert_not_called()
        finalizar.assert_not_called()
        self.assertEqual(conn.rollbacks, 1)

    def test_fila_vazia_aguarda_um_segundo_e_meio(self):
        with (
            patch.object(estado_ciclo.time, "sleep") as sleep,
            patch.object(estado_ciclo.logger, "debug") as log_debug,
        ):
            estado_ciclo.aguardar_fila_vazia()

        sleep.assert_called_once_with(1.5)
        log_debug.assert_called_once_with("fila_vazia | acao=aguardar segundos=1.5")

    def test_erro_operacional_psycopg3_reinicia_conexao(self):
        erro = flow_worker.psycopg.OperationalError("conexao indisponivel")

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[erro, PararWorker()],
                )
            )
            tratar_conexao = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_conexao",
                    return_value=10,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        tratar_conexao.assert_called_once_with(erro, 5)

    def test_fila_vazia_fecha_conexao_antes_de_aguardar(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[conn, PararWorker()],
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "pegar_mensagens_da_fila",
                    return_value=None,
                )
            )
            close = stack.enter_context(
                patch.object(
                    conn,
                    "close",
                    wraps=conn.close,
                )
            )

            def verificar_conexao_fechada():
                self.assertTrue(conn.closed)

            stack.enter_context(
                patch.object(
                    flow_worker,
                    "aguardar_fila_vazia",
                    side_effect=verificar_conexao_fechada,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        close.assert_called_once_with()
        self.assertEqual(conn.commits, 1)
        self.assertEqual(conn.rollbacks, 0)

    def _patch_fluxo_base(self, stack, conn, eventos):
        stack.enter_context(
            patch.object(
                flow_worker, "reler_conversa", side_effect=lambda contexto, *_: contexto
            )
        )
        stack.enter_context(patch.object(flow_worker, "proteger_conversa"))
        stack.enter_context(
            patch.object(flow_worker, "preparar_retorno_followup", return_value=None)
        )
        stack.enter_context(patch("builtins.print"))
        stack.enter_context(
            patch.object(
                flow_worker,
                "get_conn",
                side_effect=[conn, PararWorker()],
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "pegar_mensagens_da_fila",
                return_value=registro_fila(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "validar_banco_mensagem",
                side_effect=lambda *_args: eventos.append("validar_banco")
                or contexto_banco(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "vincular_mensagem_fila_a_conversa",
                side_effect=lambda *_args: eventos.append("vincular_conversa") or 1,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "confirmar_cache_cliente_se_pendente",
                return_value=False,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "tentar_lock_conversa",
                side_effect=lambda *_args: eventos.append("adquirir_lock") or (True, 4),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "reagendar_se_houver_mensagem_anterior",
                side_effect=lambda *_args: eventos.append("verificar_ordem") or False,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "valida_historico",
                side_effect=lambda *_args: eventos.append("persistir_cliente")
                or contexto_historico(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "flow_sender",
                side_effect=lambda *_args: eventos.append("enviar_meta")
                or contexto_envio(),
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "liberar_lock_conversa_se_necessario",
                side_effect=lambda *_args: eventos.append("liberar_lock") or True,
            )
        )
        stack.enter_context(
            patch.object(
                flow_worker,
                "handle_erro_generico",
            )
        )

    def test_mensagem_anterior_reagenda_antes_de_validar_banco(self):
        conn = FakeConn(FakeCursor())

        with ExitStack() as stack:
            stack.enter_context(patch("builtins.print"))
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "get_conn",
                    side_effect=[conn, PararWorker()],
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "pegar_mensagens_da_fila",
                    return_value=registro_fila(),
                )
            )
            barreira = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_se_houver_mensagem_anterior",
                    return_value=True,
                )
            )
            validar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "validar_banco_mensagem",
                )
            )
            lock = stack.enter_context(
                patch.object(
                    flow_worker,
                    "tentar_lock_conversa",
                )
            )
            vincular = stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        barreira.assert_called_once()
        validar.assert_not_called()
        lock.assert_not_called()
        vincular.assert_not_called()
        self.assertEqual(conn.commits, 2)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_ciclo_normal_persiste_resposta_antes_de_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    side_effect=lambda *_args: eventos.append("persistir_bot")
                    or contexto_final(),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=lambda *_args: (
                        eventos.append("marcar_sent")
                        or {"atendimento_encerrado": False}
                    ),
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(
            eventos,
            [
                "verificar_ordem",
                "validar_banco",
                "adquirir_lock",
                "vincular_conversa",
                "persistir_cliente",
                "enviar_meta",
                "persistir_bot",
                "marcar_sent",
                "liberar_lock",
            ],
        )
        finalizar.assert_called_once()
        self.assertEqual(conn.commits, 8)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_checkpoint_cache_e_atomicidade_vinculo_historico(self):
        conn = FakeConn(FakeCursor())
        eventos = []
        commits_observados = {}

        def confirmar_cache(*_args):
            commits_observados["cache"] = conn.commits
            return False

        def vincular_conversa(*_args):
            commits_observados["vinculo"] = conn.commits
            return 1

        def persistir_historico(*_args):
            commits_observados["historico"] = conn.commits
            return contexto_historico()

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "confirmar_cache_cliente_se_pendente",
                    side_effect=confirmar_cache,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                    side_effect=vincular_conversa,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "valida_historico",
                    side_effect=persistir_historico,
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    return_value=contexto_final(),
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    return_value={"atendimento_encerrado": False},
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        self.assertEqual(commits_observados["cache"], 2)
        self.assertEqual(commits_observados["vinculo"], 3)
        self.assertEqual(commits_observados["historico"], 3)

    def test_lock_recusado_reagenda_sem_consumir_retry(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "tentar_lock_conversa",
                    return_value=(False, None),
                )
            )
            reagendar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_mensagem_sem_erro",
                    return_value=1,
                )
            )
            vincular = stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                )
            )
            historico = stack.enter_context(
                patch.object(
                    flow_worker,
                    "valida_historico",
                )
            )
            enviar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "flow_sender",
                )
            )
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "liberar_lock_conversa_se_necessario",
                    return_value=None,
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        reagendar.assert_called_once_with(
            7,
            conn.cursor_obj,
            delay_seconds=5,
        )
        vincular.assert_not_called()
        historico.assert_not_called()
        enviar.assert_not_called()
        self.assertEqual(conn.commits, 4)
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_vinculo_inconsistente_reagenda_sem_enviar(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "vincular_mensagem_fila_a_conversa",
                    return_value=0,
                )
            )
            tratar_erro = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_generico",
                )
            )
            reagendar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "reagendar_mensagem_sem_erro",
                    return_value=1,
                )
            )
            aviso = stack.enter_context(
                patch.object(
                    flow_worker.logger,
                    "critical",
                )
            )
            persistir_bot = stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        tratar_erro.assert_not_called()
        persistir_bot.assert_not_called()
        finalizar.assert_not_called()
        reagendar.assert_called_once_with(7, conn.cursor_obj, delay_seconds=300)
        self.assertEqual(
            eventos,
            [
                "verificar_ordem",
                "validar_banco",
                "adquirir_lock",
                "liberar_lock",
            ],
        )
        aviso.assert_called_once()
        self.assertIn(
            "motivo=historico_conflitante_ou_fila_ausente",
            aviso.call_args.args[0],
        )
        self.assertEqual(conn.rollbacks, 0)
        self.assertTrue(conn.closed)

    def test_falha_do_banco_apos_meta_reagenda_sem_marcar_sent(self):
        conn = FakeConn(FakeCursor())
        eventos = []

        with ExitStack() as stack:
            self._patch_fluxo_base(stack, conn, eventos)
            stack.enter_context(
                patch.object(
                    flow_worker,
                    "atualizar_banco_com_contexto_final",
                    side_effect=RuntimeError("banco caiu apos envio"),
                )
            )
            finalizar = stack.enter_context(
                patch.object(
                    flow_worker,
                    "finalizar_mensagem_processada",
                    side_effect=lambda *_args: (
                        eventos.append("marcar_sent")
                        or {"atendimento_encerrado": False}
                    ),
                )
            )
            tratar_erro = stack.enter_context(
                patch.object(
                    flow_worker,
                    "handle_erro_generico",
                )
            )

            with self.assertRaises(PararWorker):
                flow_worker.worker_flow()

        finalizar.assert_not_called()
        tratar_erro.assert_called_once()
        self.assertNotIn("marcar_sent", eventos)
        self.assertEqual(conn.rollbacks, 1)
        self.assertEqual(conn.commits, 7)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
```

## Passo 18 — `tests/unit/test_followup.py`

**Ação:** Criar.

Exercitar o novo sender, os senders reais das etapas com HTTP substituído, reação, recuperação, persistência, falhas e parâmetros das consultas.

```python
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from core.repositories.atendimento import followup as repo
from core.integrations.whatsapp.pywa_functions.pywa_senders import followup as sender
from workers.worker_followup import followup_worker as worker
from workers.worker_flow.response_flow import repeticao_followup as repeticao
from workers.worker_flow.transacoes import retorno_followup as retorno

AGORA = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)


def banco(stage=1):
    return {
        "id_cliente": 2,
        "id_unidade": 3,
        "conversa": {
            "id_conversa": 1,
            "id_etapa_atual": 11,
            "status_ativa": True,
            "followup_stage": stage,
            "followup_last_sent_at": AGORA,
            "lock_version": 4,
        },
    }


def mensagem(tipo="text"):
    return {
        "id_mensagem": 5,
        "id_hash": "wamid.entrada",
        "cliente_telefone": "5511999999999",
        "id_phone_unidade": "123456",
        "unidade_telefone": "5511888888888",
        "conteudo_texto": "Começar triagem",
        "tipo_mensagem": tipo,
        "received_data_hora": AGORA,
    }


def dados():
    return {
        "nome_cliente": "Ana",
        "nome_dependente": "Bia",
        "idade_dependente": 12,
        "nome_unidade": "Unidade Teste",
        "nome_agente": "Suh",
        "genero": "feminino",
        "link_agendamento": "https://example.com/agendar",
        "link_instagram": "https://example.com/rede",
        "status_dependente": False,
    }


def contexto():
    return {
        "id_conversa": 1,
        "id_unidade": 3,
        "id_etapa_atual": 11,
        "lock_version": 4,
        "stage_anterior": 1,
        "followup_em": AGORA,
        "dados_repeticao": dados(),
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 5,
            "id_hash_msg": "wamid.entrada",
            "cliente_telefone": "5511999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": None,
    }


def candidato():
    return {
        "id_conversa": 1,
        "id_cliente": 2,
        "id_unidade": 3,
        "id_etapa": 11,
        "cliente_telefone": "5511999999999",
        "id_phone_unidade": "123456",
        "unidade_telefone": "5511888888888",
        "id_ancora": 8,
        "ancora_em": AGORA,
    }


class RetornoTests(unittest.TestCase):
    def preparar(
        self, stage=1, tipo="text", retomada=None, resposta=None, enviado_em=AGORA
    ):
        with ExitStack() as stack:
            mocks = {}
            valores = {
                "buscar_retomada": retomada,
                "buscar_resposta_bot_por_mensagem_cliente": resposta,
                "buscar_contexto_repeticao": dados(),
                "registrar_retomada": None,
                "inserir_historico_mensagem_cliente": (
                    6,
                    AGORA,
                    11,
                    not bool(resposta),
                ),
                "atualizar_conversa_mensagem_cliente": None,
            }
            for nome, valor in valores.items():
                mocks[nome] = stack.enter_context(
                    patch.object(retorno, nome, return_value=valor)
                )
            cx_banco = banco(stage)
            cx_banco["conversa"]["followup_last_sent_at"] = enviado_em
            result = retorno.preparar_retorno_followup(
                mensagem(tipo), cx_banco, MagicMock()
            )
        return result, mocks

    def test_zero_preserva_caminho_normal(self):
        result, mocks = self.preparar(stage=0)
        self.assertIsNone(result)
        mocks["inserir_historico_mensagem_cliente"].assert_not_called()

    def test_reacoes_nao_passam_por_validacao(self):
        for stage in (1, 2, 3, 9):
            for tipo in ("text", "interactive", "image", "audio", "unsupported"):
                with self.subTest(stage=stage, tipo=tipo):
                    result, mocks = self.preparar(stage=stage, tipo=tipo)
                    self.assertEqual(result["id_etapa_resposta"], 11)
                    self.assertTrue(result["retorno_followup"])
                    self.assertNotIn("transicoes_permitidas", result)
                    self.assertNotIn("saudacao_retorno", result)
                    self.assertEqual(
                        result["mensagem_cliente_atual"]["tipo_mensagem"], tipo
                    )
                    mocks["registrar_retomada"].assert_called_once()

    def test_stage_negativo_falha(self):
        with self.assertRaises(ValueError):
            self.preparar(stage=-1)

    def test_legado_com_stage_positivo_sem_data_de_envio_reapresenta_etapa(self):
        result, mocks = self.preparar(enviado_em=None)
        self.assertTrue(result["retorno_followup"])
        self.assertIsNone(result["followup_em"])
        self.assertEqual(result["id_etapa_resposta"], 11)
        mocks["registrar_retomada"].assert_called_once()

    def test_retry_nao_zera_ciclo_posterior(self):
        registro = {
            "id_etapa": 11,
            "stage_anterior": 1,
            "followup_em": AGORA,
            "concluida_em": AGORA,
        }
        resposta = (
            7,
            1,
            11,
            AGORA,
            "",
            "",
            "",
            "wamid.bot",
            5,
            "",
            "",
            "",
            "bot",
            "sent",
        )
        result, mocks = self.preparar(stage=1, retomada=registro, resposta=resposta)
        mocks["buscar_contexto_repeticao"].assert_not_called()
        mocks["atualizar_conversa_mensagem_cliente"].assert_not_called()
        with patch.object(retorno, "concluir_retomada") as concluir, patch.object(
            retorno, "inserir_historico_mensagem_bot"
        ) as inserir:
            final = retorno.persistir_retorno_followup(
                result, {"id_hash_msg_bot": "wamid.bot"}, MagicMock()
            )
        concluir.assert_not_called()
        inserir.assert_not_called()
        self.assertIsNone(final["intencao_encerramento"])

    def test_resposta_normal_existente_tem_prioridade(self):
        result, mocks = self.preparar(resposta=(1,))
        self.assertIsNone(result)
        mocks["registrar_retomada"].assert_not_called()

    def test_concluida_sem_historico_nao_reenvia(self):
        with self.assertRaises(ValueError):
            self.preparar(stage=0, retomada={"concluida_em": AGORA})

    def test_retorno_so_reseta_apos_historico(self):
        eventos = []
        envio = {
            "enviou": True,
            "id_etapa_resultante": 11,
            "id_hash_msg_bot": "wamid.bot",
        }
        with patch.object(
            retorno,
            "inserir_historico_mensagem_bot",
            side_effect=lambda *_: eventos.append("historico") or (7, AGORA, True),
        ), patch.object(
            retorno, "concluir_retomada", side_effect=lambda *_: eventos.append("reset")
        ):
            final = retorno.persistir_retorno_followup(contexto(), envio, MagicMock())
        self.assertEqual(eventos, ["historico", "reset"])
        self.assertNotIn("turnos_sem_avanco", final)
        self.assertNotIn("efeitos_transicao", final)
        self.assertIsNone(final["intencao_encerramento"])

    def test_falha_historico_nao_chega_ao_reset(self):
        envio = {"enviou": True, "id_etapa_resultante": 11}
        with patch.object(
            retorno, "inserir_historico_mensagem_bot", side_effect=RuntimeError
        ), patch.object(retorno, "concluir_retomada") as concluir:
            with self.assertRaises(RuntimeError):
                retorno.persistir_retorno_followup(contexto(), envio, MagicMock())
            concluir.assert_not_called()


class RepeticaoTests(unittest.TestCase):
    def test_todas_etapas_repetiveis_usam_senders_existentes(self):
        # Executa catálogos e senders reais; substitui somente o cliente HTTP.
        from core.integrations.whatsapp.pywa_functions import cliente

        for dependente in (False, True):
            for etapa in range(1, 22):
                with self.subTest(etapa=etapa, dependente=dependente):
                    cx = contexto()
                    cx["id_etapa_atual"] = etapa
                    cx["dados_repeticao"]["status_dependente"] = dependente
                    fake = MagicMock()
                    fake.send_message.return_value = SimpleNamespace(id="wamid.bot")
                    with patch.object(cliente, "WhatsApp", return_value=fake):
                        envio = repeticao.enviar_repeticao_followup(cx)
                    fake.send_message.assert_called_once()
                    self.assertEqual(envio["id_etapa_resultante"], etapa)
                    self.assertEqual(
                        envio["mensagem_bot"],
                        fake.send_message.call_args.kwargs["text"],
                    )
                    self.assertNotIn("evento_transicao", envio)
                    self.assertNotIn("tratamento", envio)
                    self.assertNotIn("Olá novamente", envio["mensagem_bot"])
                    self.assertTrue(
                        envio["mensagem_bot"].startswith(
                            "Que bom te ver novamente, Ana!\n\n"
                        )
                    )
                    self.assertEqual(
                        envio["mensagem_bot"].count("Que bom te ver novamente"), 1
                    )

    def test_sem_nome_usa_saudacao_generica_e_preserva_texto_enviado(self):
        from core.integrations.whatsapp.pywa_functions import cliente

        for nome in (None, "", "   "):
            with self.subTest(nome=nome):
                cx = contexto()
                cx["id_etapa_atual"] = 1
                cx["dados_repeticao"]["nome_cliente"] = nome
                fake = MagicMock()
                fake.send_message.return_value = SimpleNamespace(id="wamid.bot")
                with patch.object(cliente, "WhatsApp", return_value=fake):
                    with cliente.usar_prefixo_mensagem_bot(
                        "Olá novamente, Nome antigo!\n\n"
                    ):
                        envio = repeticao.enviar_repeticao_followup(cx)
                self.assertTrue(
                    envio["mensagem_bot"].startswith("Que bom te ver novamente!\n\n")
                )
                self.assertEqual(
                    envio["mensagem_bot"], fake.send_message.call_args.kwargs["text"]
                )
                self.assertNotIn("Olá novamente", envio["mensagem_bot"])

    def test_falha_sender_restaura_prefixo_anterior(self):
        from core.integrations.whatsapp.pywa_functions import cliente

        with patch.object(
            repeticao,
            "_selecionar_sender",
            return_value=(MagicMock(side_effect=RuntimeError("Meta")), ()),
        ):
            with cliente.usar_prefixo_mensagem_bot("prefixo anterior: "):
                with self.assertRaises(RuntimeError):
                    repeticao.enviar_repeticao_followup(contexto())
                self.assertEqual(
                    cliente.aplicar_prefixo_mensagem_bot("teste"),
                    "prefixo anterior: teste",
                )

    def test_retry_nao_chama_sender(self):
        cx = contexto()
        cx["resposta_bot_para_mensagem_atual"] = {"id_hash_msg": "wamid.bot"}
        with patch.object(repeticao, "_selecionar_sender") as selecionar:
            envio = repeticao.enviar_repeticao_followup(cx)
        selecionar.assert_not_called()
        self.assertFalse(envio["enviou"])

    def test_terminal_e_dado_ausente_falham_antes_da_meta(self):
        for etapa in (None, 0, 22, 23):
            with self.assertRaises(ValueError):
                repeticao._selecionar_sender(etapa, dados())
        cx = dados()
        cx["nome_dependente"] = None
        cx["status_dependente"] = True
        with self.assertRaises(ValueError):
            repeticao._selecionar_sender(12, cx)


class ProativoTests(unittest.TestCase):
    def test_texto_exato_e_numero_da_unidade(self):
        wa = MagicMock()
        wa.send_message.return_value = SimpleNamespace(id="wamid.bot")
        with patch.object(sender, "conta_wa", return_value=wa) as conta, patch.object(
            sender.httpx, "Client"
        ):
            result = sender.enviar_followup("5511999999999", "unidade-3")
        self.assertEqual(conta.call_args.args, ("unidade-3",))
        wa.send_message.assert_called_once_with(
            to="5511999999999", text="Você viu a minha mensagem?"
        )
        self.assertEqual(result["mensagem_bot"], "Você viu a minha mensagem?")

    def _processar(
        self, *, elegivel=True, lock=True, erro_envio=None, erro_banco=None, parar=False
    ):
        conn = MagicMock()
        stop = Event()
        if parar:
            stop.set()
        with ExitStack() as stack:
            stack.enter_context(patch.object(worker, "get_conn", return_value=conn))
            stack.enter_context(
                patch.object(worker, "tentar_lock_conversa", return_value=(lock, 4))
            )
            stack.enter_context(patch.object(worker, "proteger_conversa"))
            reler = stack.enter_context(
                patch.object(
                    worker,
                    "reler_elegivel",
                    return_value=candidato() if elegivel else None,
                )
            )
            enviar = stack.enter_context(
                patch.object(
                    worker,
                    "enviar_followup",
                    return_value={"enviou": True, "id_hash_msg_bot": "wamid.bot"},
                    side_effect=erro_envio,
                )
            )
            persistir = stack.enter_context(
                patch.object(
                    worker,
                    "persistir_followup",
                    return_value=(9, AGORA),
                    side_effect=erro_banco,
                )
            )
            unlock = stack.enter_context(patch.object(worker, "unlock_conversa"))
            result = worker.processar_candidato(candidato(), stop)
        return result, conn, enviar, persistir, reler, unlock

    def test_confirmacao_commit_e_unlock(self):
        ok, conn, enviar, persistir, _, unlock = self._processar()
        self.assertTrue(ok)
        enviar.assert_called_once()
        persistir.assert_called_once()
        unlock.assert_called_once()
        conn.close.assert_called_once()
        conn.rollback.assert_not_called()

    def test_cliente_chegou_antes_do_envio(self):
        ok, _, enviar, persistir, _, _ = self._processar(elegivel=False)
        self.assertFalse(ok)
        enviar.assert_not_called()
        persistir.assert_not_called()

    def test_lock_recusado_nao_envia_nem_libera_lock_alheio(self):
        ok, _, enviar, _, reler, unlock = self._processar(lock=False)
        self.assertFalse(ok)
        enviar.assert_not_called()
        reler.assert_not_called()
        unlock.assert_not_called()

    def test_falha_sender_nao_persiste_stage(self):
        ok, conn, _, persistir, _, _ = self._processar(erro_envio=RuntimeError("Meta"))
        self.assertFalse(ok)
        conn.rollback.assert_called_once()
        persistir.assert_not_called()

    def test_falha_persistencia_reverte(self):
        ok, conn, _, _, _, _ = self._processar(erro_banco=RuntimeError("banco"))
        self.assertFalse(ok)
        conn.rollback.assert_called_once()

    def test_sigterm_impede_proximo_despacho(self):
        _, _, enviar, _, _, _ = self._processar(parar=True)
        enviar.assert_not_called()


class LoteTests(unittest.TestCase):
    def test_falha_nao_interrompe_lote_e_volta_apos_fim_da_varredura(self):
        config = SimpleNamespace(lote=2, intervalo=60)
        parar = MagicMock()
        parar.is_set.return_value = False
        ids_processados = []
        primeiro = candidato()
        segundo = dict(primeiro, id_conversa=2)
        terceiro = dict(primeiro, id_conversa=3)

        def processar(item, _parar):
            ids_processados.append(item["id_conversa"])
            if len(ids_processados) == 1:
                raise RuntimeError("Conexão falhou antes do despacho")
            return True

        def esperar(_intervalo):
            if len(ids_processados) == 4:
                parar.is_set.return_value = True

        parar.wait.side_effect = esperar
        with patch.object(
            worker,
            "obter_lote",
            side_effect=[[primeiro, segundo], [terceiro], [primeiro]],
        ) as obter, patch.object(worker, "processar_candidato", side_effect=processar):
            worker.executar_worker(config, parar)
        self.assertEqual(ids_processados, [1, 2, 3, 1])
        self.assertEqual(
            [c.args for c in obter.call_args_list],
            [(2, None), (2, (AGORA, 2)), (2, None)],
        )
        self.assertEqual(
            [c.args for c in parar.wait.call_args_list], [(60,), (60,), (60,)]
        )


class SQLTests(unittest.TestCase):
    def test_fencing_recusa_dono_antigo(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = None
        with self.assertRaises(repo.LockConversaPerdido):
            repo.proteger_conversa(1, 3, cursor)
        self.assertIn("FOR UPDATE", cursor.execute.call_args.args[0])

    def test_reset_condicional_sem_limpar_data_auditoria(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (1,)
        cursor.rowcount = 1
        repo.concluir_retomada(contexto(), AGORA, cursor)
        sql, params = cursor.execute.call_args_list[1].args
        self.assertNotIn("followup_last_sent_at =", sql.split("WHERE")[0])
        self.assertIn("followup_stage = 0", sql)
        self.assertIn("lock_version = %s", sql)
        self.assertEqual(sql.count("%s"), len(params))

    def test_parametros_proativo_e_paginacao(self):
        cursor = MagicMock()
        cursor.fetchone.side_effect = [(1,), (9, AGORA)]
        cursor.rowcount = 1
        repo.persistir_followup(
            candidato(),
            {
                "enviou": True,
                "id_hash_msg_bot": "wamid.bot",
                "mensagem_bot": "Você viu a minha mensagem?",
            },
            4,
            cursor,
        )
        for chamada in cursor.execute.call_args_list:
            sql, params = chamada.args
            self.assertEqual(sql.count("%s"), len(params))
        insert = cursor.execute.call_args_list[1].args[0]
        self.assertIn("NULL, NULL", insert)
        cursor.reset_mock()
        cursor.fetchall.return_value = []
        repo.listar_elegiveis(cursor, 20, (AGORA, 1))
        sql, params = cursor.execute.call_args.args
        self.assertEqual(sql.count("%s"), len(params))


if __name__ == "__main__":
    unittest.main()
```

## Passo 19 — `tests/integration/__init__.py`

**Ação:** Criar.

Separar os testes que precisam de infraestrutura local descartável da suíte unitária.

```python
"""Testes opcionais em infraestrutura local descartável, nunca no RDS."""
```

## Passo 20 — `tests/integration/test_followup_postgres.py`

**Ação:** Criar.

Entregar testes executáveis de DDL, consultas, isolamento, unicidade, rollback e disputa de lock em PostgreSQL local. Não se conectam ao RDS nem usam as credenciais DB_HOST/DB_NAME.

```python
"""Contrato PostgreSQL real. Exige banco local vazio chamado test_chatbot_followup."""

import os
import unittest
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import bank_script
from core.repositories.atendimento import followup as repo
from core.repositories.atendimento.conversas import (
    tentar_lock_conversa,
    unlock_conversa,
)

DSN = os.environ.get("FOLLOWUP_TEST_DSN")
MIGRACAO = (
    Path(__file__).resolve().parents[2] / "deploy/migrations/followup_registros.sql"
)


@unittest.skipUnless(DSN, "Defina FOLLOWUP_TEST_DSN para PostgreSQL local descartável")
class FollowupPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parametros = conninfo_to_dict(DSN)
        if (
            parametros.get("host") not in {"127.0.0.1", "::1", "localhost"}
            or parametros.get("dbname") != "test_chatbot_followup"
        ):
            raise RuntimeError(
                "Teste exige host loopback e dbname=test_chatbot_followup"
            )
        cls.conn = psycopg.connect(DSN, connect_timeout=5)
        cls.cursor = cls.conn.cursor()
        cls.cursor.execute("SELECT to_regnamespace('chatbot')")
        if cls.cursor.fetchone()[0] is not None:
            cls.conn.close()
            raise RuntimeError(
                "Banco de teste não está vazio: schema chatbot já existe"
            )
        cls.cursor.execute(
            "CREATE SCHEMA chatbot; CREATE TABLE chatbot.auth_user (id SERIAL PRIMARY KEY);"
        )

        @contextmanager
        def transacao_local(*_):
            yield cls.cursor

        with patch.object(bank_script, "transacao_deploy", transacao_local):
            bank_script.criar_tabelas()
            bank_script.criar_funcoes_lock()
        # Colunas reais usadas nas barreiras; não simula o comportamento da Meta.
        cls.cursor.execute("""
            CREATE TABLE chatbot.cliente_bloqueado_meta
                (wa_id_cliente VARCHAR(100), phone_id_unidade VARCHAR(100));
            CREATE TABLE chatbot.webhook_flood_evento
                (wa_id_cliente VARCHAR(100), phone_id_unidade VARCHAR(100), received_at TIMESTAMPTZ);
            INSERT INTO chatbot.etapa(id_etapa, nome_etapa)
            SELECT etapa, 'Etapa de teste ' || etapa::text FROM generate_series(1, 22) AS etapa;
            INSERT INTO chatbot.cliente(id_cliente, waid_telefone, nome) VALUES (1, '5511999999999', 'Ana');
            INSERT INTO chatbot.unidade
                (id_unidade, nome_unidade, nome_agente, genero, cnpj, email_responsavel,
                 telefone, waba_id, phone_number_id, link_agendamento)
            VALUES (1, 'Unidade Teste', 'Suh', 'feminino', 'teste', 'teste@example.com',
                    '5511888888888', 'waba-teste', 'phone-teste', 'https://example.com/agendar');
            INSERT INTO chatbot.conversa(id_conversa, id_cliente, id_unidade, id_etapa_atual)
            VALUES (1, 1, 1, 11);
        """)
        cls.conn.commit()

    @classmethod
    def tearDownClass(cls):
        cls.conn.rollback()
        cls.cursor.execute("DROP SCHEMA chatbot CASCADE")
        cls.conn.commit()
        cls.conn.close()

    def setUp(self):
        self.conn.rollback()
        self.cursor.execute("SELECT clock_timestamp()")
        self.agora = self.cursor.fetchone()[0]
        self.ancora = self.agora - timedelta(hours=7, seconds=1)
        self.cursor.execute(
            """
            INSERT INTO chatbot.historico_mensagens
                (id_conversa, id_etapa, received_data_hora, cliente_telefone, conteudo_texto,
                 tipo_mensagem, id_hash_msg, id_phone_unidade, unidade_telefone, quem_enviou, status_envio)
            VALUES (1, 11, %s, '5511999999999', 'mensagem', 'text', 'wamid.cliente',
                    'phone-teste', '5511888888888', 'cliente', NULL),
                   (1, 11, %s, '5511999999999', 'Podemos começar?', 'text', 'wamid.bot',
                    'phone-teste', '5511888888888', 'bot', 'sent');
        """,
            (self.ancora - timedelta(minutes=1), self.ancora),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_message_from = 'bot', last_interaction_at = %s WHERE id_conversa = 1",
            (self.ancora,),
        )

    def tearDown(self):
        self.conn.rollback()

    def test_sete_horas_um_envio_e_reinicio_nao_duplica(self):
        dados = repo.reler_elegivel(1, self.cursor)
        self.assertIsNotNone(dados)
        ok, versao = tentar_lock_conversa(1, self.cursor)
        self.assertTrue(ok)
        envio = {
            "enviou": True,
            "mensagem_bot": "Você viu a minha mensagem?",
            "id_hash_msg_bot": "wamid.followup",
        }
        id_bot, data = repo.persistir_followup(dados, envio, versao, self.cursor)
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "SELECT followup_stage, followup_last_sent_at FROM chatbot.conversa WHERE id_conversa=1"
        )
        self.assertEqual(self.cursor.fetchone(), (1, data))
        self.cursor.execute(
            "SELECT id_mensagem_fila, id_hash_cliente_origem FROM chatbot.historico_mensagens WHERE id_mensagem=%s AND received_data_hora=%s",
            (id_bot, data),
        )
        self.assertEqual(self.cursor.fetchone(), (None, None))

    def test_antes_de_sete_horas_e_fora_da_janela_meta(self):
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='bot'",
            (self.agora - timedelta(hours=6),),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_interaction_at=%s",
            (self.agora - timedelta(hours=6),),
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='bot'",
            (self.ancora,),
        )
        self.cursor.execute(
            "UPDATE chatbot.conversa SET last_interaction_at=%s", (self.ancora,)
        )
        self.cursor.execute(
            "UPDATE chatbot.historico_mensagens SET received_data_hora=%s WHERE quem_enviou='cliente'",
            (self.agora - timedelta(hours=24),),
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))

    def test_fila_sem_vinculo_bloqueia_so_o_par_correto(self):
        self.cursor.execute(
            """
            INSERT INTO chatbot.fila_mensagens
                (received_data_hora, cliente_telefone, conteudo_texto, tipo_mensagem,
                 id_hash_msg, id_phone_unidade, unidade_telefone)
            VALUES (%s, '5511999999999', 'Olá', 'text', 'fila-test', 'outra-unidade', 'outro-numero');
        """,
            (self.agora,),
        )
        self.assertIsNotNone(repo.reler_elegivel(1, self.cursor))
        self.cursor.execute(
            "UPDATE chatbot.fila_mensagens SET id_phone_unidade='phone-teste'"
        )
        self.assertIsNone(repo.reler_elegivel(1, self.cursor))

    def test_bloqueios_stage_e_unidade_impedem_despacho(self):
        # Mesmo ativas e não terminais, as etapas a partir do agendamento são excluídas.
        for etapa in range(1, 23):
            with self.subTest(etapa=etapa):
                self.cursor.execute("SAVEPOINT faixa_etapa")
                self.cursor.execute(
                    "UPDATE chatbot.conversa SET id_etapa_atual=%s", (etapa,)
                )
                self.assertEqual(
                    repo.reler_elegivel(1, self.cursor) is not None, etapa < 18
                )
                self.assertEqual(
                    bool(repo.listar_elegiveis(self.cursor, 20)), etapa < 18
                )
                self.cursor.execute("ROLLBACK TO SAVEPOINT faixa_etapa")
        for sql in (
            "UPDATE chatbot.conversa SET followup_stage=1",
            "UPDATE chatbot.conversa SET followup_stage=2",
            "UPDATE chatbot.conversa SET followup_stage=-1",
            "UPDATE chatbot.conversa SET turnos_sem_avanco=12",
            "UPDATE chatbot.conversa SET status_ativa=FALSE",
            "UPDATE chatbot.unidade SET status_pagamento=FALSE",
            "INSERT INTO chatbot.cliente_bloqueado_meta VALUES ('5511999999999','phone-teste')",
        ):
            with self.subTest(sql=sql):
                self.cursor.execute("SAVEPOINT variacao")
                self.cursor.execute(sql)
                self.assertIsNone(repo.reler_elegivel(1, self.cursor))
                self.cursor.execute("ROLLBACK TO SAVEPOINT variacao")

    def test_unicidade_da_ancora_e_rollback_do_historico(self):
        dados = repo.reler_elegivel(1, self.cursor)
        _, versao = tentar_lock_conversa(1, self.cursor)
        envio = {
            "enviou": True,
            "mensagem_bot": "Você viu a minha mensagem?",
            "id_hash_msg_bot": "wamid.followup",
        }
        repo.persistir_followup(dados, envio, versao, self.cursor)
        self.cursor.execute("SAVEPOINT duplicado")
        with self.assertRaises(psycopg.errors.UniqueViolation):
            repo.persistir_followup(dados, envio, versao, self.cursor)
        self.cursor.execute("ROLLBACK TO SAVEPOINT duplicado")
        self.cursor.execute("SELECT count(*) FROM chatbot.followup_envio")
        self.assertEqual(self.cursor.fetchone()[0], 1)

    def test_reset_e_marcador_sao_atomicos(self):
        _, versao = tentar_lock_conversa(1, self.cursor)
        self.cursor.execute(
            "UPDATE chatbot.conversa SET followup_stage=1, followup_last_sent_at=%s",
            (self.agora,),
        )
        contexto = {
            "id_conversa": 1,
            "lock_version": versao,
            "id_etapa_atual": 11,
            "stage_anterior": 1,
            "followup_em": self.agora,
            "mensagem_cliente_atual": {
                "id_mensagem_fila": 10,
                "id_hash_msg": "wamid.reacao",
            },
        }
        self.cursor.execute("SAVEPOINT sem_marcador")
        with self.assertRaises(ValueError):
            repo.concluir_retomada(contexto, self.agora, self.cursor)
        self.cursor.execute("ROLLBACK TO SAVEPOINT sem_marcador")
        self.cursor.execute("SELECT followup_stage FROM chatbot.conversa")
        self.assertEqual(self.cursor.fetchone()[0], 1)
        self.cursor.execute(
            "INSERT INTO chatbot.followup_retomada(id_conversa,id_mensagem_fila,id_hash_cliente,id_etapa,stage_anterior,followup_em) VALUES(1,10,'wamid.reacao',11,1,%s)",
            (self.agora,),
        )
        repo.concluir_retomada(contexto, self.agora, self.cursor)
        self.cursor.execute(
            "SELECT followup_stage,followup_last_sent_at,turnos_sem_avanco,id_etapa_atual FROM chatbot.conversa"
        )
        self.assertEqual(self.cursor.fetchone(), (0, self.agora, 0, 11))

    def test_dois_processos_lock_recusa_e_fencing(self):
        # ROLLBACK remove apenas a fixture desta função. A conversa-base é confirmada.
        self.conn.rollback()
        ok, antiga = tentar_lock_conversa(1, self.cursor)
        self.assertTrue(ok)
        self.conn.commit()
        try:
            with psycopg.connect(DSN, connect_timeout=5) as outro:
                with outro.cursor() as cursor:
                    self.assertFalse(tentar_lock_conversa(1, cursor)[0])
                    cursor.execute(
                        "UPDATE chatbot.conversa SET processing_started_at=clock_timestamp()-INTERVAL '111 seconds' WHERE id_conversa=1"
                    )
                    ok, nova = tentar_lock_conversa(1, cursor)
                    self.assertTrue(ok)
                    self.assertGreater(nova, antiga)
            with self.assertRaises(repo.LockConversaPerdido):
                repo.proteger_conversa(1, antiga, self.cursor)
            self.assertFalse(unlock_conversa(1, antiga, self.cursor))
        finally:
            self.conn.rollback()
            self.cursor.execute(
                "UPDATE chatbot.conversa SET processing=FALSE, processing_started_at=NULL WHERE id_conversa=1"
            )
            self.conn.commit()


@unittest.skipUnless(DSN, "Defina FOLLOWUP_TEST_DSN para PostgreSQL local descartável")
class MigracaoLegadoPostgresTests(unittest.TestCase):
    def setUp(self):
        # Reutiliza a base real e as verificações de banco vazio/loopback.
        FollowupPostgresTests.setUpClass.__func__(type(self))
        self.addCleanup(self.limpar_banco)
        self.cursor.execute(
            "DROP TABLE chatbot.followup_envio, chatbot.followup_retomada, chatbot.followup_legado"
        )
        self.cursor.execute("""
            INSERT INTO chatbot.cliente(id_cliente, waid_telefone, nome)
            VALUES (2,'5511999999992','Bia'), (3,'5511999999993','Caio'), (4,'5511999999994','Davi');
            INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade,id_etapa_atual,status_ativa,followup_stage)
            VALUES (2,2,1,18,TRUE,NULL), (3,3,1,11,FALSE,0), (4,4,1,11,TRUE,2);
        """)
        self.conn.commit()

    def limpar_banco(self):
        FollowupPostgresTests.tearDownClass.__func__(type(self))

    def executar_migracao(self):
        self.cursor.execute(MIGRACAO.read_text(encoding="utf-8"), prepare=False)
        while self.cursor.nextset():
            pass

    def test_marca_ativas_preserva_dados_e_nao_reaplica(self):
        self.cursor.execute(
            "SELECT id_conversa, to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa"
        )
        antes = dict(self.cursor.fetchall())
        self.conn.commit()
        self.executar_migracao()
        self.cursor.execute(
            "SELECT id_conversa, to_jsonb(c) FROM chatbot.conversa c ORDER BY id_conversa"
        )
        depois = dict(self.cursor.fetchall())
        for id_conversa, original in antes.items():
            esperado = dict(original)
            if original["status_ativa"]:
                esperado["followup_stage"] = 1
            self.assertEqual(depois[id_conversa], esperado)
        self.cursor.execute(
            "SELECT id_conversa,stage_anterior FROM chatbot.followup_legado ORDER BY id_conversa"
        )
        self.assertEqual(self.cursor.fetchall(), [(1, 0), (2, None), (4, 2)])
        self.cursor.execute(
            "SELECT (SELECT COUNT(*) FROM chatbot.followup_envio), (SELECT COUNT(*) FROM chatbot.historico_mensagens)"
        )
        self.assertEqual(self.cursor.fetchone(), (0, 0))
        self.cursor.execute(
            "UPDATE chatbot.conversa SET followup_stage=0 WHERE id_conversa=1"
        )
        self.cursor.execute("""
            INSERT INTO chatbot.cliente(id_cliente,waid_telefone) VALUES(5,'5511999999995');
            INSERT INTO chatbot.conversa(id_conversa,id_cliente,id_unidade) VALUES(5,5,1);
        """)
        self.conn.commit()
        with self.assertRaises(psycopg.errors.DuplicateTable):
            self.executar_migracao()
        self.conn.rollback()
        self.cursor.execute(
            "SELECT id_conversa,followup_stage FROM chatbot.conversa WHERE id_conversa IN (1,5) ORDER BY id_conversa"
        )
        self.assertEqual(self.cursor.fetchall(), [(1, 0), (5, 0)])

    def test_legado_terminal_recusa_migracao_sem_marcar_ninguem(self):
        self.cursor.execute(
            "UPDATE chatbot.conversa SET id_etapa_atual=22 WHERE id_conversa=1"
        )
        self.conn.commit()
        with self.assertRaises(psycopg.errors.RaiseException):
            self.executar_migracao()
        self.conn.rollback()
        self.cursor.execute(
            "SELECT followup_stage FROM chatbot.conversa WHERE id_conversa=1"
        )
        self.assertEqual(self.cursor.fetchone(), (0,))
        self.cursor.execute("SELECT to_regclass('chatbot.followup_legado')")
        self.assertIsNone(self.cursor.fetchone()[0])


if __name__ == "__main__":
    unittest.main()
```

## Passo 21 — `utilitarios/verificar_followup.py`

**Ação:** Criar.

Entregar um diagnóstico somente leitura para a homologação e o deploy. Não adquire lock de conversa, não altera stage e não envia mensagens.

```python
"""Diagnóstico somente leitura. Não adquire lock de conversa nem envia mensagens."""

import json

from core.database.connection_aws import get_conn
from core.repositories.atendimento.followup import consultar_diagnostico


def main():
    with get_conn(application_name="verificar_followup", connect_timeout=10) as conn:
        with conn.cursor() as cursor:
            diagnostico = consultar_diagnostico(cursor)
    print(json.dumps(diagnostico, ensure_ascii=False))
    if diagnostico["stages_negativos"] or diagnostico["horarios_futuros"]:
        raise SystemExit("REVISAR_ANOMALIAS_ANTES_DE_ATIVAR")
    print("FOLLOWUP_CONSULTA_OK_SEM_ENVIO")


if __name__ == "__main__":
    main()
```


---

# Documentação da implementação — arquivos completos

## Passo 22 — `REGRAS_DE_NEGOCIO.md`

**Ação:** Alterar.

Acrescentar a exceção deliberada da reação ao follow-up e os invariantes do ciclo, conservando as regras atuais do restante do atendimento.

````markdown
# Regras de negócio do Chatbot - V1

## Finalidade

Este documento é a fonte de verdade para interpretar o comportamento do sistema.
Antes de classificar algo como bug ou alterar o worker, webhook, fila, histórico,
conversa, cache ou banco de dados, estas regras devem ser consultadas.

Uma proteção que aparentemente descarta, bloqueia ou repete um processamento pode
ser uma decisão deliberada da V1. Alterar uma dessas regras representa uma mudança
de produto, e não apenas uma refatoração técnica.

## Definições

- **Cliente:** identificado por `wa_id` ou `cliente_telefone`.
- **Unidade:** identificada por `phone_number_id` ou `id_phone_unidade`.
- **Turno:** interação do par `(cliente_telefone, id_phone_unidade)` que aguarda
  uma resposta do bot.
- **Mensagem aceita:** mensagem que passou pelas validações do webhook e foi
  persistida em `chatbot.fila_mensagens`.
- **Mensagem respondida:** mensagem da fila que possui histórico do bot com
  `status_envio = 'sent'`, vinculado ao seu `id_mensagem_fila` e ao hash da
  mensagem original do cliente.
- **Fonte de verdade:** dado persistido no PostgreSQL. O Redis acelera consultas,
  mas não substitui o banco de dados como fonte definitiva.

## 1. Um turno por vez

Para cada par `(cliente_telefone, id_phone_unidade)`, a V1 deve manter no máximo
uma mensagem aberta ainda sem resposta própria do bot. A decisão não depende
somente de `fila_mensagens.status`; ela combina filas abertas com a resposta do
bot especificamente vinculada a cada mensagem.

- A prioridade é determinada exclusivamente pela ordem de chegada, e não pelo
  tamanho, conteúdo ou aparente importância da mensagem.
- A primeira mensagem válida será persistida na fila.
- Enquanto essa primeira mensagem estiver `pending` ou `processing` e ainda não
  possuir sua própria resposta persistida do bot, qualquer mensagem posterior do
  mesmo cliente para a mesma unidade será descartada pelo webhook.
- A mensagem descartada não será inserida na fila nem no histórico. Para o banco,
  ela nunca existiu.
- Quando todas as filas `pending` ou `processing` já possuírem sua própria
  resposta do bot, o webhook poderá aceitar a primeira mensagem do próximo turno,
  mesmo que a limpeza da fila anterior ainda não tenha chegado ao commit de
  `fila_mensagens.status = 'sent'`.
- A decisão é serializada por `pg_advisory_xact_lock`, utilizando unidade e
  cliente como chaves.

Exemplo de comportamento esperado:

```text
cliente: oi
cliente: olá, quero solicitar determinada coisa
```

Nesse exemplo, `oi` chegou primeiro e é a única mensagem válida do turno. O bot
deverá responder somente a `oi`. A mensagem `olá, quero solicitar determinada
coisa` será descartada no webhook e não aparecerá na fila nem no histórico.

O objetivo não é escolher a mensagem mais completa ou mais útil. O objetivo é
garantir uma única entrada por turno e impedir que várias mensagens enviadas
antes da resposta do bot sejam interpretadas como etapas independentes.

### 1.1. Por que `fila_mensagens.status = 'sent'` não é a única fonte da decisão

`sent` continua sendo o estado terminal que confirma a conclusão administrativa
da fila. Porém, ele não é a única prova de que o turno funcional foi respondido.
A prova mais importante para recuperação é o histórico do bot vinculado à
mensagem específica por:

```text
id_conversa
id_mensagem_fila
id_hash_cliente_origem
```

Se a Meta confirmou o envio, o histórico do bot foi persistido e
`last_message_from` foi atualizado para `bot`, o cliente já recebeu a resposta.
O worker ainda pode cair antes do commit separado que altera a fila para `sent`.
Utilizar somente o status da fila faria o webhook descartar a resposta seguinte
do cliente durante essa janela, embora ela já pertença legitimamente ao próximo
turno.

O webhook atual usa o histórico específico do bot como prova de resposta. Ele não
libera uma mensagem apenas porque o `last_message_from` geral da conversa está
como `bot`; cada fila aberta precisa possuir sua própria resposta correspondente.

### 1.2. Recuperação detalhada entre resposta do bot e `sent`

#### Etapa 1 - A foi respondida, mas o worker caiu

```text
Fila A: processing
Histórico do cliente A: existe
Histórico do bot A: existe
last_message_from: bot
Lock da conversa: ocupado
```

O worker cai antes de marcar A como `sent`. A resposta já chegou ao WhatsApp do
cliente, mas A permanece `processing` por aproximadamente 2 minutos.

#### Etapa 2 - o cliente envia B

O webhook encontra A aberta, mas também encontra a resposta do bot vinculada
especificamente a A. B é a primeira mensagem do próximo turno e pode entrar:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 3 - outro ciclo seleciona B

Antes de resolver a conversa ou tentar seu lock, o worker procura uma mensagem
anterior ainda aberta para o mesmo cliente e unidade. Como A continua
`processing`, B é devolvida para `pending` por 30 segundos. Essa espera não
consome tentativa de erro.

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

#### Etapa 4 - o cliente envia C

O webhook examina individualmente todas as filas abertas:

| Fila | Status | Resposta própria do bot |
|---|---|---|
| A | `processing` | Sim |
| B | `pending` | Não |

Como B ainda não possui resposta própria:

```text
todas_abertas_respondidas = False
```

C é descartada e nunca entra no banco. O `last_message_from = 'bot'` deixado por
A não libera C, porque não existe histórico do bot vinculado especificamente a B.

#### Etapa 5 - B aguarda a recuperação de A

Enquanto A continuar aberta, cada claim de B repetirá a verificação de ordem e a
devolverá para `pending` por 30 segundos, sem tentar o lock da conversa:

```text
Fila A: processing, respondida
Fila B: pending, sem resposta
```

C e quaisquer mensagens posteriores continuarão bloqueadas por B.

#### Etapa 6 - A retorna após o timeout

Depois de aproximadamente 2 minutos:

1. A fica elegível novamente;
2. o lock antigo já expirou após 110 segundos;
3. outro worker adquire o lock;
4. encontra o histórico do bot vinculado a A;
5. não envia uma resposta duplicada;
6. marca A como `sent`;
7. libera o lock.

```text
Fila A: sent
Fila B: pending
```

#### Etapa 7 - B é processada

B já não encontra mensagem anterior aberta, resolve a conversa, adquire o lock e
segue normalmente. Se esse lock for recusado por outro motivo, B volta para
`pending` por 5 segundos, também sem consumir uma tentativa de erro.
Enquanto B não possuir sua própria resposta do bot, qualquer C será descartada.

Depois que a resposta de B for persistida, a primeira mensagem do próximo turno
poderá entrar, inclusive na pequena janela anterior ao commit de `sent` de B.

### 1.3. Limite prático de mensagens abertas

Na recuperação descrita, o sistema poderá manter temporariamente:

```text
1 mensagem antiga respondida, mas ainda processing
+
1 mensagem nova sem resposta
```

Isso não cria uma sequência ilimitada. Assim que B entra sem resposta própria,
C, D, E e todas as mensagens seguintes são descartadas pelo webhook. O advisory
lock do turno também impede que B e C sejam aceitas simultaneamente por uma
corrida entre requisições.

Implementação principal:

- `core/repositories/seguranca/turno_cliente.py`
- `callback/webhook/services/populating_fila_mensagens.py`

## 2. Idempotência na entrada do webhook

- `fila_mensagens.id_hash_msg` é único.
- A repetição do mesmo evento pela Meta não deve criar outra linha na fila.
- `ON CONFLICT DO NOTHING` é o comportamento esperado para o mesmo
  `id_hash_msg`.
- Uma mensagem nova possui outro hash e continua sujeita à regra de turno.

Ignorar um webhook duplicado não é bug.

## 3. Primeira mensagem do turno

A primeira mensagem válida deverá ser persistida na fila quando não existir outra
mensagem aberta sem resposta para o mesmo cliente e unidade.

É considerado bug quando a primeira mensagem, ou a única mensagem enviada no
turno, é ignorada sem que alguma regra explícita deste documento seja aplicável.

## 4. Estados e tentativas da fila

Estados utilizados:

- `pending`: aguardando processamento.
- `processing`: reservada por um worker.
- `sent`: processamento e resposta concluídos.
- `failed`: permitido pelo schema, mas não é o destino utilizado atualmente
  quando o limite de tentativas é atingido.

Regras da V1:

- O dequeue altera a mensagem para `processing` e incrementa `retry_count`.
- Uma mensagem `processing` abandonada poderá ser retomada depois de 2 minutos.
- Erros tratados reagendam a mensagem para 2 minutos depois, enquanto ainda
  houver tentativa disponível.
- O limite é de 3 tentativas de processamento.
- Ao identificar `retry_count >= 3`, a mensagem é excluída.
- Não existe uma quarta tentativa.

A exclusão ao atingir o limite de 3 tentativas é uma regra de negócio confirmada
da V1, e não um bug. Alterar esse comportamento para `failed`, dead-letter ou um
número maior de tentativas exige uma nova decisão de produto.

Implementação principal:

- `core/database/deploy_database/bank_script.py`, função `chatbot.dequeue_message()`
- `workers/tratamento_erros_externos/expection_process.py`
- `core/repositories/atendimento/fila.py`

## 5. Ordenação e exclusão mútua

- Uma conversa deve ser processada por apenas um worker por vez.
- O lock da conversa poderá ser retomado se estiver abandonado por mais de 110
  segundos.
- `lock_version` impede que um worker antigo libere o lock adquirido por um
  worker mais novo.
- Uma mensagem não poderá ultrapassar outra mensagem anterior ainda aberta na
  mesma conversa.
- A ordem utiliza `received_data_hora` e, em caso de empate, `id_mensagem`.
- Uma mensagem posterior que encontrar outra anterior aberta será reagendada sem
  consumir uma tentativa de erro.

Implementação principal:

- `core/database/deploy_database/bank_script.py`, funções `lock_conversa()` e
  `unlock_conversa()`
- `core/repositories/atendimento/conversas.py`
- `core/repositories/atendimento/fila.py`
- `workers/worker_flow/transacoes/lock_conversa.py`
- `workers/worker_flow/transacoes/ordem_turno.py`

## 6. Conversa ativa e bloqueio por 30 dias

- Poderá existir somente uma conversa ativa para o mesmo cliente e unidade.
- Essa garantia é protegida pelo índice parcial `idx_conversa_unica_ativa`.
- Uma conversa finalizada em etapa com `bloqueio_dias > 0` permanecerá
  bloqueada pelo prazo declarado na política.
- A etapa 2 registra a escolha inicial entre titular e dependente. A etapa 3
  aceita exclusivamente `Sim` ou `Não`, por clique nos botões ou pelo mesmo
  texto digitado. `Sim` mantém a escolha; `Não` seleciona o polo oposto.
  Os dois resultados seguem obrigatoriamente para a etapa 4. Mídia, dúvida
  sobre reforço escolar, pergunta financeira inequívoca ou qualquer outro
  conteúdo repetem a confirmação.
- A etapa 4 sempre coleta, em texto livre, a profissão. Somente depois de
  persistir esse dado ela consulta o `status_dependente` final: dependente
  segue para a etapa 5, que pergunta o nome; titular segue para a etapa 6,
  que pergunta a idade. Assim, nenhum fluxo novo pula a profissão.
- A profissão válida da etapa 4 é salva, na mesma transação, em dois níveis:
  `conversa.profissao` preserva o snapshot daquele atendimento e
  `cliente.profissao` é substituída pelo valor válido mais recente informado
  pelo cliente. Uma conversa posterior nunca reescreve a profissão das
  conversas anteriores.
- Antes dessa persistência, o validador rejeita como
  `profissao_fora_contexto` somente as oito respostas completas já observadas:
  `Pra minha filha na verdade`, `Não entendi`, `Para meu filho`,
  `Pra meu filho`, `Minha filha é autista e percebo q ela tem dificuldade no
  aprendizado , vcs atende autista tambem`, `não seria pra meu filho`,
  `Meu filho` e `Vc ouviu áudio ou ligação`. A comparação ocorre sobre a frase
  inteira normalizada, nunca pela presença isolada de palavras como `áudio`,
  `ligação`, `filho`, `filha` ou `autista`. Quando houver correspondência, a
  etapa 4 apenas reapresenta a pergunta, sem evento, avanço ou persistência e
  sem criar uma etapa de confirmação adicional.
- A etapa 11 introduz a triagem, as etapas 12 a 17 fazem as seis perguntas e a
  etapa 18 apresenta o agendamento. A etapa 18 torna a conversa elegível ao
  Funil, mas não encerra nem bloqueia o atendimento.
- Na etapa 11, o clique em `Começar triagem` e confirmações textuais inequívocas
  disparam o mesmo evento `triagem_iniciada`. A validação aceita variações de
  começar, iniciar e prosseguir, enquanto negativas e respostas ambíguas mantêm
  a conversa na etapa 11.
- As etapas 12 a 17 não mudam de ID nem de transição conforme a idade. Elas
  selecionam somente o texto da pergunta: titular usa sempre a versão adulta;
  dependente com menos de 18 anos usa a versão infantil; dependente com 18 anos
  ou mais usa a versão adulta com o nome persistido. O limite de entrada de 4
  anos em unidade com BPA e de 5 anos sem BPA continua pertencendo à validação
  de idade anterior à triagem.
- Cada unidade possui as políticas `suporte_idoso`, desativada por padrão, e
  `email_obrigatorio`, ativada por padrão. Esses defaults preservam o
  comportamento das unidades existentes.
- Na etapa 6, mídia, reforço escolar e financeiro continuam precedendo a
  validação de idade. Idades a partir de 100 anos preservam o encerramento
  existente. Depois dessas decisões, um titular de 60 a 99 anos em unidade com
  `suporte_idoso = TRUE` recebe o contato comercial e tem a conversa encerrada
  com `motivo_encerramento = 'encaminhado_suporte_idoso'`, sem bloqueio de 30
  dias e sem envio ao Funil. A idade informada é persistida. Dependentes nunca
  entram nessa exceção.
- O Admin só permite ativar `suporte_idoso` quando `numero_comercial` puder ser
  normalizado para um link brasileiro válido do WhatsApp.
- Na etapa 10, mídia, reforço escolar e financeiro continuam precedendo a
  coleta de e-mail. A exigência efetiva é a configuração da unidade, exceto
  para o titular de 60 a 99 anos, cujo e-mail é universalmente opcional quando
  o atendimento não tiver sido encerrado pelo suporte ao idoso. Dependentes
  seguem exclusivamente a configuração da unidade.
- Quando o e-mail é obrigatório, somente um endereço estruturalmente válido
  avança. Quando é opcional, um endereço válido é salvo; ausência declarada ou
  qualquer outra resposta comum aceita limpa `cliente.email` para `NULL` e
  avança sem tratamento de e-mail. A classificação da resposta permanece
  vinculada à conversa para que o Funil exiba `não tem` ou `não informado` sem
  inventar um endereço.
- A etapa 19 registra uma nota de satisfação de 1 a 5. Na etapa 20, o cliente
  escolhe se deseja comentar: a aceitação segue para a etapa 21 e a recusa
  salta diretamente para a etapa 22. A etapa 21 coleta o comentário. Nota e
  comentário são internos, não compõem o payload do Funil e não encerram nem
  bloqueiam o atendimento.
- A etapa 22 encerra a conversa, registra `foi_agendado` e aplica o bloqueio de
  30 dias.
- Durante esse período, novas mensagens para a mesma unidade não iniciarão outro
  atendimento.
- Depois dos 30 dias, o cliente poderá iniciar uma nova conversa com a mesma
  unidade.

Implementação principal:

- `core/database/deploy_database/bank_script.py`
- `core/repositories/atendimento/conversas.py`
- `core/repositories/fluxo/politicas.py`
- `workers/worker_flow/valida_banco.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`

### 6.1 Oportunidade no Funil de Vendas

- Uma conversa torna-se elegível ao entrar na etapa 18.
- As etapas 18 a 22 permanecem elegíveis. Assim, avançar na pesquisa antes do
  próximo ciclo do worker não remove a conversa da fila do Funil.
- `lead_no_funil = TRUE` é a confirmação que impede um segundo envio da mesma
  conversa; nota e comentário da pesquisa não fazem parte do snapshot enviado.
- O worker cria uma oportunidade por vez na coluna `Leads` do CRM.
- O snapshot exige nome, telefone, idade da pessoa atendida e as seis respostas
  canônicas da triagem. O e-mail pode estar ausente quando a política efetiva
  da conversa o tornou opcional; nesse caso, o contato é enviado sem endereço
  e as observações exibem `não tem` ou `não informado`, conforme a resposta.
- O resultado de e-mail pertence à conversa que chegou ao Funil. Ele é
  reconstruído pela mensagem do cliente na etapa 10 vinculada à resposta do
  bot na etapa 11; uma conversa posterior não pode alterar esse snapshot por
  meio do valor global de `cliente.email`.
- A profissão da conversa é exibida nas observações; o Funil não usa
  `cliente.profissao`, pois ela pode ter sido atualizada por outro atendimento.
  Conversas legadas podem apresentar a profissão como não informada.
- As observações apresentam as seis perguntas e suas respostas na ordem das
  etapas 12 a 17. O Funil usa o mesmo catálogo de perguntas do WhatsApp e não
  envia mais o resumo por quantidade de `Nunca`, `Às vezes` e
  `Frequentemente`.
- Em atendimento para dependente, a oportunidade mantém o cliente pagante como
  contato e inclui nome e idade do dependente nas observações.
- A resposta só é confirmada quando o HTTP não falha e o JSON contém
  `response = success`.
- Falha antes da confirmação externa devolve `funil_envios` para `pending` e
  não altera `lead_no_funil`.
- `funil_envios` usa claim com `FOR UPDATE SKIP LOCKED` e lease para recuperar
  itens abandonados em `processing`.
- O título segue `Chatbot Lead <nome_unidade>`. A conversa é identificada pelos
  dados do snapshot e pelo estado local de `funil_envios`; o CRM não recebe o ID
  interno da conversa no título.
- A V1 não cria atividade e não sincroniza atualizações posteriores do CRM.

O processo é desativado por padrão e só inicia com
`FUNIL_WORKER_ENABLED=True` depois do teste manual da unidade.

## 7. Histórico da mensagem do cliente

Depois que uma mensagem da fila for aceita pelo worker:

- Ela será registrada no histórico como `quem_enviou = 'cliente'`.
- Sua identificação lógica utilizará conversa, `id_mensagem_fila` e
  `id_hash_msg`.
- Durante um retry, o registro existente deverá ser reutilizado.
- A etapa persistida no histórico deverá ser reutilizada; o retry não poderá
  reinterpretar a mensagem em outra etapa.
- `last_message_from` deverá permanecer como `cliente` enquanto não existir uma
  resposta do bot persistida para aquela mensagem.
- `last_interaction_at` deverá utilizar o horário persistido da mensagem, e não o
  horário em que o retry ocorreu.

### Respostas da triagem cognitiva

- A triagem mantém exatamente seis perguntas nas etapas 12 a 17.
- A idade e o destino do atendimento são relidos do banco em cada ciclo. Isso
  preserva a mesma variante no retry e impede escolher silenciosamente uma
  pergunta quando idade, nome do dependente ou destino estiverem inconsistentes.
- A versão infantil sempre usa o nome do dependente. A versão adulta usa
  `você` para o titular e o nome para um dependente adulto.
- Cada pergunta aceita somente `Nunca`, `Às vezes` ou `Frequentemente`.
- Botão e texto digitado percorrem a mesma validação exata.
- Qualquer outro conteúdo recebe o tratamento de contexto e mantém a conversa
  na pergunta atual.
- A resposta canônica é registrada em `chatbot.respostas_desafios` com a
  conversa, a etapa da pergunta e o histórico da mensagem do cliente.
- A restrição única por conversa e etapa torna a gravação idempotente.
- Em retry, a resposta pode ser reconstruída pela mensagem original.

## 8. Histórico e idempotência da resposta do bot

A resposta do bot é vinculada à mensagem original por:

- `id_conversa`;
- `id_mensagem_fila`;
- `id_hash_cliente_origem`.

Se `resposta_bot_para_mensagem_atual` já existir:

- a Meta não deverá ser chamada novamente;
- o histórico do bot não deverá ser duplicado;
- o contexto da conversa deverá ser reparado a partir dos dados persistidos;
- `last_message_from` deverá terminar como `bot`;
- a fila poderá seguir para `sent`.

As proteções `if resposta_bot_atual`, presentes nos fluxos normais e de
tratamento, são regras essenciais de idempotência da V1.

Implementação principal:

- `workers/worker_flow/valida_historico.py`
- `workers/worker_flow/response_flow/flow_sender.py`
- `workers/worker_flow/response_flow/etapas/`
- `workers/worker_flow/transacoes/persistencia_resposta.py`

## 9. Semântica de `last_message_from`

- Mensagem do cliente persistida e ainda sem resposta: `cliente`.
- Resposta do bot persistida: `bot`.
- Retry sem resposta do bot mantém ou repara o campo para `cliente`.
- Retry com resposta do bot existente mantém ou repara o campo para `bot`.
- O campo representa o último lado com mensagem persistida para o estado atual;
  ele não é apenas uma marcação de que a conversa já foi iniciada.

## 10. Etapas da conversa

- `chatbot.etapa` representa os estados existentes da conversa.
- `chatbot.etapa_transicao` representa as arestas permitidas entre esses
  estados.
- Uma resposta válida produz um evento e somente poderá seguir para o destino
  cadastrado para a combinação `origem + evento`.
- Uma etapa poderá possuir mais de um destino, desde que cada evento identifique
  uma única transição.
- Avanços, saltos e o retorno controlado `9 + retorno_adiado -> 8` são permitidos
  somente quando existe uma aresta explícita.
- Um exemplo de salto autorizado é
  `20 + comentario_satisfacao_recusado -> 22`.
- A atualização utilizará a origem persistida no histórico da mensagem e será
  revalidada no `UPDATE` da conversa.
- Um retry com resposta do bot existente reutilizará a etapa do histórico do
  bot e reconstruirá o evento pela origem e pelo destino.
- Tratamentos que apenas orientam o cliente poderão responder sem avançar a
  etapa e não produzirão evento de transição.

Qualquer transição sem aresta cadastrada é bug. A ordem numérica dos IDs serve
para organização e não define navegação.

## 11. Tipos de mensagem na V1

- `text` e `interactive` são tipos suportados pelo fluxo normal de validação.
- Mídias e anexos não são respostas suportadas pelo fluxo normal da V1.
- Uma mídia recebida deverá ser registrada no histórico.
- O bot enviará uma orientação para o cliente continuar por texto.
- Essa orientação não avançará a etapa, mas alterará `last_message_from` para
  `bot` depois de ser persistida.
- Texto com intenção de preço, custo, mensalidade ou investimento recebe
  tratamento próprio e não deve ser interpretado como resposta comum da etapa.
- Depois que a etapa 1 já foi apresentada, respostas de nome com números,
  caracteres inválidos, repetição artificial ou termos pejorativos recebem
  tratamento de contexto e não avançam a conversa.

Desconsiderar o conteúdo da mídia para fins de avanço de etapa não é bug.

### 11.1. Conversa iniciada por texto

Quando a conversa ainda não possui etapa atual persistida, qualquer mensagem de
texto comum poderá iniciar o atendimento e receber a saudação normal da etapa 1.

Essa regra vale mesmo que o texto inicial seja estranho, curto, tenha símbolos ou
pareça fora de contexto. Nessa primeira interação, o objetivo é apresentar o
agente virtual configurado para a unidade e pedir o nome do cliente.

A exceção é texto com intenção financeira. Nesse caso, o sistema já responde a
dúvida sobre valores e, na mesma mensagem, apresenta a etapa 1.

Nas mensagens iniciais padrão, de mídia, de intenção financeira e de tratamento
de reforço escolar, a apresentação é formada exclusivamente pelos dados
persistidos em `chatbot.unidade`:

- `nome_unidade`: nome público da unidade;
- `nome_agente`: nome público do agente virtual;
- `genero`: seleciona `Sou o {nome_agente}` para `masculino` e
  `Sou a {nome_agente}` para `feminino`.

Esses campos não alteram evento, transição, turno, retry ou transação. Eles são
apenas dados de apresentação lidos pelo contexto da etapa 1. As demais mensagens
mantêm seus textos próprios.

### 11.2. Exceção para conversa iniciada com mídia

Quando a primeira mensagem de uma conversa for uma mídia, ainda não existirá
uma etapa atual persistida. Nesse caso:

1. o bot enviará saudação da etapa 1 junto com o aviso de mídia não suportada;
2. a mensagem solicitará o nome do cliente por texto;
3. o tratamento registrará a etapa 1 como apresentada;
4. a próxima interação válida será interpretada como resposta da etapa 1 e
   poderá direcionar o fluxo para a etapa 2.

Mensagem esperada, usando uma das duas primeiras linhas conforme o gênero do
agente:

```text
Masculino: Bom dia/Boa tarde/Boa noite! Sou o {nome_agente}, atendente virtual do {nome_unidade}! ☺️
Feminino:  Bom dia/Boa tarde/Boa noite! Sou a {nome_agente}, atendente virtual do {nome_unidade}! ☺️
Olha não reconhecemos ainda mensagem com mídia, apenas texto.
Me diz, qual o seu nome?
```

Para qualquer etapa já apresentada, a regra geral será diferente. Se a conversa
estiver na etapa N e o cliente enviar uma mídia:

1. o bot enviará o tratamento de tipo de mensagem não suportado;
2. o tratamento poderá repetir a pergunta da etapa atual quando essa
   reapresentação estiver implementada;
3. o tratamento não alterará a etapa persistida;
4. a interação seguinte por texto será interpretada como resposta da etapa N;
5. uma resposta válida produzirá o evento que aponta para o destino cadastrado;
6. a mensagem normal da etapa N não precisará ser enviada de novo em separado.

Na etapa 1 já apresentada, a resposta esperada para mídia será:

```text
Olha não reconhecemos ainda mensagem com mídia, apenas texto.
Me diz, qual o seu nome?
```

Para etapas ainda sem tratamento específico, a mensagem poderá ser mais genérica:

```text
Recebi uma mídia, mas nesta etapa eu preciso que você responda por texto ou use os botões disponíveis.

Envie uma mensagem de texto para continuarmos.
```

Em ambos os casos:

1. o tratamento não avança etapa;
2. a interação seguinte por texto será interpretada como resposta da etapa N;
3. uma resposta válida seguirá a transição cadastrada para a etapa N.

Portanto, o tratamento de mídia não avança etapa já apresentada. A exceção é
somente a conversa iniciada com mídia, porque a própria mensagem de tratamento
também apresenta a etapa 1.

### 11.3. Tratamento financeiro

Quando o cliente enviar texto perguntando sobre valor, custo, preço,
mensalidade, investimento ou termo equivalente:

1. a mensagem do cliente será registrada no histórico;
2. o bot responderá que valores são apresentados no atendimento presencial após
   a aula gratuita;
3. a mensagem também reapresentará a pergunta da etapa atual;
4. a conversa não avançará por causa da pergunta de valor;
5. `last_message_from` será atualizado para `bot` depois da resposta persistida.

Se a conversa iniciar com pergunta de valor, a resposta esperada usará uma das
duas primeiras linhas conforme o gênero do agente:

```text
Masculino: Bom dia/Boa tarde/Boa noite! Sou o {nome_agente}, atendente virtual do {nome_unidade}! ☺️
Feminino:  Bom dia/Boa tarde/Boa noite! Sou a {nome_agente}, atendente virtual do {nome_unidade}! ☺️
Olha demais informações como valores são apresentados no atendimento presencial após sua aula gratuita.
Me diz, qual o seu nome?
```

Nesse caso, a etapa 1 fica registrada como apresentada, e a próxima resposta em
texto será interpretada como resposta da etapa 1.

Se a etapa 1 já tiver sido apresentada e o cliente responder perguntando sobre
valor, a mensagem esperada será:

```text
Olha demais informações como valores são apresentados no atendimento presencial após sua aula gratuita.
Me diz, qual o seu nome?
```

Esse tratamento é financeiro, não tratamento de contexto. Ele possui fluxo e
sender próprios para evitar misturar dúvida comercial com resposta fora do
contexto da etapa.

### 11.4. Tratamento de dúvida sobre reforço escolar

Nas mesmas etapas que oferecem tratamento financeiro, o sistema também deverá
identificar dúvidas que confundam o Supera com serviços escolares tradicionais,
como reforço escolar, banca, supletivo, cursinho, aula particular ou ensino de
matérias específicas.

O reconhecimento é universal e possui o seguinte contrato:

1. mídia ou tipo não suportado continua tendo prioridade sobre o texto;
2. a dúvida sobre reforço escolar tem prioridade sobre o tratamento financeiro;
3. a mensagem do cliente e a resposta do bot são registradas normalmente;
4. a resposta é marcada com `tipo_tratamento='duvida_reforco_escolar'`;
5. nenhuma transição é produzida e a conversa permanece na etapa atual;
6. a pergunta ou chamada da etapa é reapresentada de forma neutra, preservando
   botões, rodapés, links e as variantes de titular ou dependente aplicáveis.

Assim, uma pergunta como `Quanto custa o reforço escolar?` recebe este
tratamento antes do financeiro. Já uma mídia que contenha texto ou legenda
continua recebendo tratamento de mídia.

Expressões inequívocas de serviço escolar podem ser reconhecidas diretamente.
Nomes de matérias, como matemática ou português, exigem também contexto de
ensino, aula, ajuda ou procura pelo serviço. A palavra isolada não é suficiente,
pois respostas legítimas como `Sou professora de matemática` devem continuar
pertencendo à etapa que coleta a profissão.

Na etapa 4, declarações claras de profissão ou vínculo de trabalho com banca,
cursinho, supletivo ou reforço também são respostas profissionais válidas. Por
exemplo, `Trabalho em um cursinho`, `Sou diretora de um supletivo` e
`Sou professora de matemática em uma banca` não acionam este tratamento. A
exceção é contextual e não altera o reconhecimento nas demais etapas.

Mensagem esperada:

```text
Olha, o Supera não é reforço escolar.
Nós trabalhamos a raiz da aprendizagem, desenvolvendo habilidades como atenção, concentração, memória e raciocínio — o alicerce necessário para aprender melhor em qualquer matéria. 🧠✨

Mas bora lá:

(retomada neutra da etapa atual)
```

### 11.5. Tratamento de contexto para nome inválido

Depois que a etapa 1 já foi apresentada, a resposta esperada do cliente é o nome.
Se o cliente responder com texto que pareça fora do contexto de nome, como
caracteres inválidos, números, repetição artificial ou termo pejorativo, o bot
deverá tratar sem avançar a conversa.

Mensagem esperada:

```text
Olha sua mensagem parece estar fora do contexto e também não aceitamos nomes e apelidos pejorativos.
Me diz, qual o seu nome?
```

Esse tratamento é diferente do financeiro e do tipo não suportado. Ele existe
para preservar a etapa atual e pedir novamente um nome utilizável.

### 11.6. Coerência semântica ao reapresentar a etapa

Quando um tratamento reapresentar a pergunta da etapa atual, ele não deverá
concatenar automaticamente a mensagem padrão completa. A pergunta ou chamada
principal pode ser reutilizada, mas aberturas que pressuponham resposta válida,
confirmação, apresentação ou avanço — como `Entendi`, `Certo`, `Perfeito`,
`Maravilha` e `Prazer` — deverão ser omitidas ou substituídas por uma retomada
neutra.

A mensagem final deverá ser lida como uma única fala semanticamente coerente.
Depois de informar que uma resposta não foi compreendida ou aceita, o bot não
deverá elogiar, confirmar entendimento nem pressupor que a conversa avançou.
Essa regra vale para tratamentos de mídia, financeiro, contexto e qualquer
tratamento futuro que reapresente conteúdo da etapa.

### 11.7. Saudação de retorno após inatividade

Depois que o cliente já informou o nome na etapa 1, uma nova mensagem recebida
na mesma conversa pelo menos três horas após o último envio confirmado do bot
deverá fazer a resposta começar com `Olá novamente, {nome}!`.

O intervalo é inclusivo (`>= 3 horas`) e deve comparar o horário original do
evento atual do cliente com a última linha `sent` do bot no histórico da mesma
`id_conversa`. A atividade do mesmo cliente em outra unidade ou conversa não
participa desse cálculo. A própria mensagem em que o nome é informado na etapa
1 ainda não recebe a saudação; a regra começa nas mensagens seguintes, quando o
nome já está validado e persistido.

A saudação é somente um prefixo da resposta que o fluxo já produziria:

- resposta válida: saudação mais a mensagem da etapa resultante;
- resposta inválida: saudação mais o tratamento e a repetição da etapa atual.

Ela não cria etapa, evento de transição, envio separado nem uma segunda linha de
histórico. A barreira idempotente continua sendo executada antes dos resolvers:
se o retry já encontrar a resposta exata do bot persistida para aquela mensagem
do cliente, nenhum novo envio ou prefixo será produzido. Nome, último envio ou
timestamps ausentes/incompatíveis apenas desativam a saudação para aquele evento
e nunca impedem a resposta normal do fluxo.

## 12. Flood, payload e assinatura

- A regra atual de rajada curta considera 15 eventos em 5 segundos.
- Redis é a primeira fonte de avaliação de flood.
- Banco e memória funcionam como fallbacks previstos.
- Um cliente identificado como flood poderá ser bloqueado na Meta e não deverá
  ser enfileirado.
- Conversas explicitamente bloqueadas também não serão enfileiradas.
- Payload acima de `WEBHOOK_MAX_BODY_BYTES` deverá ser rejeitado com HTTP 413
  antes de parse, flood, cache ou banco.
- Assinatura Meta inválida deverá ser rejeitada com HTTP 403 antes de qualquer
  confiança no conteúdo do payload.

Payload grande e assinatura inválida bloqueiam a requisição na entrada, mas não
devem bloquear diretamente um cliente na Meta. Um atacante poderia montar um
payload inválido utilizando o `wa_id` de um cliente real. Bloquear esse número
atingiria a vítima informada pelo atacante, e não necessariamente a origem da
requisição.

Portanto, HTTP 413 ou 403 sem bloqueio Meta é o comportamento final e esperado da
V1, e não uma implementação parcial.

Implementação principal:

- `callback/webhook/services/post_flow.py`
- `callback/webhook/services/flood_guard.py`
- `core/cache/runtime/cache_flood_redis.py`
- `core/cache/cache_flood_memoria.py`

## 13. Commits e estados intermediários do worker

O worker possui checkpoints duráveis separados:

1. claim da fila como `processing`;
2. cliente, conversa e vínculo da mensagem;
3. lock da conversa;
4. histórico do cliente e `last_message_from = 'cliente'`;
5. histórico do bot, etapa e `last_message_from = 'bot'`;
6. fila marcada como `sent`;
7. unlock da conversa.

Uma queda entre checkpoints normalmente deixa informações suficientes para que
o timeout e o retry reconheçam o estado intermediário. O objetivo é evitar a
perda da mensagem aceita, mesmo admitindo duplicidade rara.

As decisões de `commit`, `rollback` e `close` da conexão do ciclo pertencem ao
`flow_worker.py`. Repositórios e módulos internos executam operações utilizando a
conexão ou o cursor recebido, sem assumir a propriedade da transação.

## 14. Duplicidade aceita como exceção rara

O sistema busca entrega pelo menos uma vez, e não exatamente uma vez.

A principal janela aceita de duplicidade é:

```text
Meta confirmou ou efetivou o envio
        -> worker caiu ou perdeu a confirmação
        -> histórico do bot ainda não foi confirmado no banco
```

Nesse intervalo, o retry não encontra uma resposta persistida e poderá enviar
novamente. Depois do commit do histórico do bot, o retry deverá reconhecer a
resposta e não repetir o envio.

Duplicidade frequente, determinística ou ocorrida depois de a resposta do bot já
estar persistida é bug. Duplicidade excepcional na janela externa entre Meta e
banco é um trade-off conhecido e aceito na V1.

O Funil possui uma janela externa equivalente:

```text
Funil confirmou a oportunidade
        -> banco caiu antes de marcar lead_no_funil
        -> lease expirou
        -> retry pode criar outra oportunidade
```

O estado local `processing` e o snapshot persistido tornam o caso rastreável, mas
não existe exatamente uma vez sem consulta de reconciliação suportada pelo CRM.

## 15. O que é bug na V1

São bugs, entre outros:

- a primeira ou única mensagem válida do turno ser ignorada sem uma regra
  aplicável;
- uma mensagem aceita desaparecer antes de concluir a política prevista de
  tentativas;
- o bot enviar novamente quando a resposta atual já estiver persistida;
- `last_message_from` permanecer como `cliente` quando a resposta atual do bot já
  estiver persistida, ou como `bot` quando ainda não existir resposta persistida;
- uma etapa mudar sem a aresta `origem + evento -> destino` autorizada;
- duas mensagens do mesmo turno avançarem a conversa como se fossem turnos
  independentes;
- uma mensagem posterior ultrapassar outra anterior ainda aberta na conversa;
- uma falha prevista encerrar permanentemente o worker sem tentativa de
  recuperação.

## 16. O que não é bug na V1

Não são bugs:

- ignorar qualquer segunda mensagem quando a primeira mensagem do mesmo cliente e
  unidade ainda estiver aberta e sem resposta própria do bot;
- ignorar a repetição do mesmo webhook ou `id_hash_msg`;
- reutilizar histórico existente durante um retry;
- responder a uma mídia com orientação sem avançar etapa já apresentada;
- apresentar a etapa 1 junto com o aviso quando a conversa for iniciada com
  mídia;
- responder pergunta sobre valor sem tratar esse texto como nome ou avanço de
  etapa;
- excluir a mensagem ao atingir a terceira tentativa;
- aguardar os timeouts da fila ou do lock antes de um novo processamento;
- uma duplicidade extremamente rara na janela entre Meta e commit do bot;
- rejeitar payload grande ou assinatura inválida sem bloquear o número informado
  na Meta.

## 17. Falhas operacionais do webhook e reentrega da Meta

Quando uma mensagem válida chega à transação da fila, mas conexão, inserção ou
commit falham:

- a transação será revertida com rollback;
- o webhook registrará `insert_exception`;
- a resposta será HTTP 503 com `status = 'unavailable'`;
- a Meta poderá tratar a entrega como malsucedida e reenviar o evento;
- a repetição continuará protegida pela unicidade de `id_hash_msg`.

Também é HTTP 503 quando o webhook não consegue validar a unidade porque Redis e
banco estão indisponíveis no mesmo ponto do fluxo. Nesse caso:

- o webhook registrará `unit_validation_unavailable`;
- a mensagem não será tratada como unidade inativa;
- a Meta poderá reenviar o evento quando o endpoint voltar a responder com
  sucesso.

Esse HTTP 503 é reservado para falhas operacionais que impedem o sistema de
decidir ou persistir uma mensagem válida com segurança. Mensagens descartadas
intencionalmente por turno aberto, duplicidade, flood, unidade inativa, conversa
bloqueada ou payload sem mensagem processável continuam seguindo seus contratos
de `ignored` e não devem ser transformadas em indisponibilidade.

O retry da Meta protege a chegada ao webhook e não substitui o retry interno do
worker. Depois que a fila foi persistida e o webhook respondeu HTTP 200, qualquer
falha de processamento ou envio da resposta pertence à política de tentativas do
worker.

## 18. Cache, fallback e autocura

Tabelas e consultas de baixa volatilidade ou alta frequência devem priorizar
Redis e possuir fallback para a fonte de verdade no banco quando o cache estiver
indisponível, inválido ou inconsistente de maneira detectável.

Princípios obrigatórios:

- Redis é um acelerador; o banco continua sendo a fonte de verdade.
- Uma falha do Redis não deverá interromper o fluxo quando houver fallback seguro
  no banco.
- Depois de consultar o banco por fallback, o sistema deverá tentar reparar o
  Redis com os dados atuais.
- Uma falha na tentativa de reparo do cache não deverá apagar dados válidos do
  banco.
- Quando um valor stale causar erro de integridade, ele deverá ser removido ou o
  cache completo deverá ser recarregado para que o próximo retry consulte o banco
  e se recupere.
- Operações administrativas que exijam banco e cache coerentes deverão ser
  bloqueadas se o Redis não puder ser validado ou atualizado.

### 18.1. Cache de unidades

- Utiliza hash Redis, quantidade esperada e versão mantida em
  `chatbot.cache_controle`.
- Webhook e worker conferem periodicamente a versão do Redis contra a versão do
  banco e recarregam o cache quando encontram divergência.
- O Django Admin incrementa a versão e recria o cache depois de salvar ou excluir
  uma unidade.
- Se o Redis falhar, webhook e worker utilizam fallback no banco e tentam
  recarregar o cache.
- Se um `id_unidade` stale causar violação de FK no worker, o cache de unidades é
  recarregado antes do retry.

### 18.2. Cache de clientes

- Relaciona `wa_id` ao `id_cliente` e possui TTL.
- Miss, valor inválido ou Redis indisponível levam a consulta ao banco.
- Um cliente criado ou encontrado no banco será salvo no cache somente depois do
  commit que confirmar sua existência.
- Se um `id_cliente` stale causar violação de FK, a chave será removida para que o
  retry reconstrua o valor correto pelo banco.

### 18.3. Cache de conversas bloqueadas

- O bloqueio de 30 dias utiliza Redis com TTL calculado a partir de
  `finalizou_em`.
- Quando o Redis falha, o banco é consultado e o cache é criado ou removido para
  refletir o resultado persistido.
- Quando o worker encontra uma conversa bloqueada que ainda não estava no cache,
  ele registra a chave com o TTL restante e remove a mensagem da fila.
- Depois de expirado o período, a chave não deverá mais bloquear o cliente.
- Esse cache possui mecanismo próprio de reparo e não deverá ser incluído nos
  reparos de FK de cliente e unidade do `flow_worker.py`.

### 18.4. Escopo da autocura

- A autocura cobre falhas detectadas, versão divergente de unidades e erros FK
  de cliente ou unidade.
- Em produção, alterações manuais diretamente no banco são proibidas. Dados que
  afetam cache devem ser modificados pelos fluxos oficiais da aplicação ou pelo
  Django Admin.
- Edições manuais no banco são permitidas somente em desenvolvimento. Nesse
  ambiente, atrasos de sincronização poderão ser corrigidos pelo reset de cache
  destinado a DEV.
- O sistema não precisa comparar banco e Redis em toda leitura para detectar uma
  edição manual que viole o contrato de produção.

Dentro desse contrato, a autocura implementada atende às regras da V1. Suporte a
edições manuais silenciosas em produção não é requisito.

Implementação principal:

- `core/cache/cache_unidade.py`
- `core/cache/runtime/cache_cliente.py`
- `core/cache/runtime/cache_conversas_bloqueadas.py`
- `core/repositories/unidades/cache_control.py`
- `workers/worker_flow/suporte/cache_repair.py`

## 19. Regras do Django Admin

O Django Admin é uma superfície operacional controlada, e não uma forma livre de
editar as tabelas do fluxo.

### 19.1. Tabelas somente para visualização

Cliente, dependente, etapa, conversa, fila, histórico, respostas de desafio,
eventos de flood e controle de cache utilizam administração somente leitura:

- não permitem adicionar;
- não permitem alterar;
- não permitem excluir;
- exibem os campos somente para consulta operacional.

### 19.2. Clientes bloqueados na Meta

- `cliente_bloqueado_meta` representa a intenção persistente de bloquear o par
  `wa_id_cliente + phone_id_unidade`, além dos bloqueios já confirmados pela
  Meta.
- Um contato identificado manualmente pode ser registrado nessa tabela mesmo
  quando a janela da Meta ainda não permite confirmar o bloqueio.
- Toda nova mensagem desse par é interceptada antes do flood, da validação da
  unidade e da fila.
- O webhook tenta bloquear novamente na Meta e sempre ignora a mensagem, tanto
  no sucesso quanto na falha. Uma mensagem futura provoca uma nova tentativa.
- Falha ao consultar a lista retorna HTTP 503 para a Meta reenviar o evento;
  nenhuma mensagem é enfileirada sem que essa validação seja concluída.
- A consulta sempre inclui `wa_id_cliente` e `phone_id_unidade`, preservando o
  isolamento multi-WABA.
- Bloqueios automáticos detectados pelo sistema registram e confirmam primeiro
  a intenção local no banco; somente depois do commit tentam o bloqueio na
  Meta, sem manter transação aberta durante a chamada externa.
- Se a Meta recusar o bloqueio, a linha local permanece autoritativa: a
  mensagem atual é ignorada e uma mensagem futura provoca nova tentativa.
- Se a intenção local não puder ser persistida por indisponibilidade do banco,
  o webhook não chama a Meta, não enfileira a mensagem e retorna HTTP 503 para
  permitir reentrega.
- O Django Admin continua sem permitir a criação livre de registros enquanto
  não existir uma interface específica para classificar bots manualmente.
- O administrador poderá somente desbloquear, removendo individualmente um
  registro existente.
- Desbloqueio em massa é proibido.
- No desbloqueio, a ordem obrigatória é Meta primeiro, banco depois.
- Se o desbloqueio na Meta falhar, o registro deverá permanecer no banco.
- Não existe chave Redis equivalente: a própria tabela é consultada de forma
  autoritativa pelo webhook.

### 19.3. Unidades

- Cada unidade possui um `waba_id` único e obrigatório e um
  `phone_number_id` único e obrigatório.
- A criação valida primeiro, pela Graph API, se o `phone_number_id` pertence
  ao `waba_id` informado.
- Depois da validação, o App assina a WABA e registra o número na Meta.
- Se a Meta falhar, a unidade não será criada no banco.
- Antes da alteração no banco, o Redis deverá passar pelo preflight.
- Depois do save, a versão das unidades será incrementada e o cache recarregado.
- A exclusão desassina a WABA e desregistra o número na Meta antes de remover
  a unidade do banco.
- Se a Meta falhar durante a exclusão, a unidade permanecerá no banco.
- Se o Redis falhar depois de a Meta responder, o banco deverá permanecer sem
  alteração e o administrador deverá receber uma mensagem para tentar novamente.
- Exclusão em massa de unidades é proibida.
- `suporte_idoso` e `email_obrigatorio` são editáveis no Admin; a ativação do
  suporte exige um número comercial válido. `waba_id` e `phone_number_id` ficam
  somente leitura depois da criação.

### 19.4. Papel de `status_pagamento`

`status_pagamento` não representa vinculação ou desvinculação do número no WABA.

- O campo é o controle atual de admissão da unidade: somente registros com
  `status_pagamento = TRUE` entram no cache de unidades ativas e são localizados
  pelo webhook e worker.
- Uma futura tabela `payment` poderá automatizar essa decisão, mas ela não faz
  parte da V1.
- Na V1, pagamentos e contratos poderão ser controlados manualmente, contrato por
  contrato.
- Alterar `status_pagamento` deverá atualizar banco e cache de unidades, mas não
  deverá registrar ou remover o número na Meta.

O fato de uma edição de `status_pagamento` não chamar a Meta é comportamento esperado,
e não uma lacuna.

### 19.5. Desvinculação definitiva de uma unidade

Para encerrar o vínculo de uma unidade com o sistema:

1. solicitar a exclusão individualmente pelo Django Admin;
2. o sistema remove a assinatura do App na WABA;
3. o sistema desregistra o `phone_number_id`;
4. somente após as duas confirmações Meta conclui a exclusão no banco e
   atualiza o cache de unidades.

A exclusão administrativa continua protegida pela validação Meta-first do código
e pelo preflight do Redis. A exclusão em massa permanece proibida.

Implementação principal:

- `callback/webhook/admin.py`
- `core/integrations/whatsapp/tools/validando_phone_waba.py`
- `core/integrations/whatsapp/tools/ativando_waba_id.py`
- `core/integrations/whatsapp/tools/desativa_waba_id.py`
- `core/integrations/whatsapp/tools/ativando_numero.py`
- `core/integrations/whatsapp/tools/desativando_numero.py`

### 19.6. Contas de monitoramento por unidade

- `chatbot.unidade.id_usuario_monitoramento` referencia `chatbot.auth_user.id`.
  O vínculo é opcional e único: cada usuário pode monitorar no máximo uma
  unidade e cada unidade pode possuir no máximo uma conta de monitoramento.
  Várias unidades podem manter o campo `NULL`, sem acesso de monitoramento.
- Login, hash da senha e ativação da conta pertencem à autenticação do Django;
  a unidade armazena somente a referência. No Admin, crie a conta em **Usuários**
  e selecione-a no campo **Usuário de monitoramento** do cadastro da unidade.
- Contas de monitoramento não possuem `is_staff` nem `is_superuser`. O formulário
  recusa contas administrativas e a autorização também confere esses estados
  diretamente no banco, além de `is_active`.
- A identidade vem de `request.user`; usuário/unidade informados pelo navegador
  não definem o escopo. Sem sessão válida, vínculo ou conta habilitada, o acesso
  é negado. Erro de banco não autoriza leitura.
- Conversas são autorizadas por `conversa.id_unidade`; mensagens, pela unidade
  de sua conversa. O cadastro global de cliente não concede acesso às conversas
  dele em outras unidades. Se conversa e mensagem forem informadas juntas, a
  mensagem deve pertencer àquela conversa.
- O vínculo é consultado a cada requisição, sem cache nem bypass administrativo.
  Remover o vínculo, desativar a conta ou mudar sua unidade afeta a próxima
  consulta. `status_pagamento` continua com sua finalidade de admissão do bot;
  não é um novo bloqueio do monitoramento.
- Excluir um usuário limpa a referência por `ON DELETE SET NULL`, preservando
  a unidade, suas conversas e seu histórico. Excluir a unidade pelo fluxo
  administrativo existente não exclui a conta Django. Limpar somente o campo
  de monitoramento revoga o acesso sem excluir entidades.
- O login usa o par `username`/senha da mesma conta e o verificador de hash
  nativo do Django. Antes de criar a sessão, exige conta habilitada, comum e
  vinculada a uma unidade. Usuário inexistente e senha incorreta recebem o
  mesmo aviso. Não há cadastro, recuperação/troca de senha ou bloqueio após
  três tentativas no portal; o proprietário administra as contas pelo Admin.
- Login e logout usam CSRF; logout somente por POST. O destino após autenticar
  é fixo, sem aceitar redirecionamento escolhido pelo navegador. A senha fica
  mascarada e não volta preenchida após erro. Falhas de banco não liberam acesso.
- O acesso bem-sucedido abre o painel em `/`. A página e todas as rotas de dados
  usam `exigir_acesso_monitoramento` e mantêm cada SELECT limitado à unidade
  retornada. A autorização não filtra automaticamente outros SQLs ou QuerySets.
- O painel é somente leitura. Suas rotas de dados aceitam apenas GET; não há
  envio de mensagens, cadastro, edição nem exclusão de informações.
- O período padrão cobre a primeira mensagem de cliente registrada na unidade
  até o instante da consulta. Também são aceitas janelas de 24 horas, 7 e 30
  dias, 2, 3 e 6 meses e 1 ano. Uma janela finita compara seus indicadores com
  a janela imediatamente anterior de igual duração.
- Conversas técnicas do mesmo cliente são consolidadas somente dentro da unidade
  autorizada. Os filtros locais são Todas, Continuações, Funil e Avaliadas; os
  perfis visuais são Menor de 18, Adulto, 60+ e Dependente. Na lista de
  conversas, as etiquetas ao lado da data preservam a relação entre faixa
  etária e destino nas formas abreviadas DP -18, DP 18–59, DP 60+, 18–59 e
  60+; a descrição completa permanece disponível como informação acessível.
- O navegador consulta conversas a cada 10 segundos e relatórios a cada 30
  segundos quando a página está visível. Voltar à aba força uma leitura. Esse
  polling usa o mesmo serviço Django/Gunicorn do webhook e não cria worker ou
  serviço systemd adicional.
- As opções `suporte_idoso`, `email_obrigatorio` e `bpa_ativo` são lidas da
  unidade. Elas controlam as informações e interpretações exibidas, inclusive a
  idade mínima do dependente e os casos em que envio ao Funil não se aplica.
- O relatório mostra métricas, comparação, demanda ao longo do tempo, perfis,
  satisfação e a etapa atual da conversa mais recente de cada contato que teve
  atividade no período. Cada contato conta uma vez. A etapa é um retrato atual;
  o banco não permite reconstruir em qual etapa a conversa estava em uma data
  passada.
- O histórico armazena texto e tipo da mensagem, mas não o payload exato dos
  botões enviados. Para mensagens interativas, o painel mostra os botões do
  catálogo atual daquela etapa como referência visual, sempre desabilitados.
- Os quatro indicadores agregados ficam na seção Relatórios. A seção Conversas
  prioriza a visualização da lista e do histórico, mantendo filtros e período.
- O CSV completo inclui todos os contatos ativos no período e deixa campos
  ausentes vazios. O CSV elegível exige nome, e-mail estruturalmente válido e
  telefone normalizado. Ambos usam
  cabeçalhos compatíveis com importação no Google Contatos e nunca alteram o
  banco.
- Há também duas exportações de dados essenciais, para todos os contatos ou
  apenas elegíveis, com somente Nome, E-mail e Telefone. Mantêm o nome completo
  em uma coluna, sem acrescentar rótulos ou datas, e reutilizam as mesmas regras
  de período, unidade, normalização e elegibilidade dos arquivos Google CSV.

## 20. Disponibilidade e recuperação automática

“O sistema não deve cair nunca” é um requisito de resiliência operacional e
recuperação automática. Isso não significa afirmar que o interpretador Python, a
máquina ou a rede jamais poderão falhar.

Sempre deverá existir uma camada capaz de conter a falha e manter ou restaurar o
serviço:

- falha do Redis utiliza fallback quando existe uma fonte segura no banco;
- falha de uma mensagem não encerra o processamento das demais;
- o worker captura falhas, preserva ou reagenda o estado quando possível e
  continua o loop;
- o worker do Funil isola erros por lead e reinicia falhas globais com espera
  linear de 5 a 60 segundos;
- `flow_worker.py` mantém o loop de consumo e os tratamentos por tipo de exceção;
- se `worker_flow()` escapar com uma exceção, `iniciar_flow_worker.py` registra a falha,
  aguarda 5 segundos e inicia outro loop;
- o webhook responde de maneira controlada a entradas inválidas e falhas
  conhecidas;
- chamadas externas à Meta falham de forma controlada, sem confirmar no banco
  uma operação recusada pela Meta;
- caches degradam para fallback ou negam uma operação administrativa que
  produziria inconsistência.

Na produção atual, webhook, worker de atendimento e worker do Funil são serviços
systemd independentes, todos com `Restart=always` e espera de 5 segundos. As
camadas de recuperação são complementares:

```text
operação individual falha
    -> exception ou fallback trata
    -> flow_worker continua
    -> iniciar_flow_worker reinicia o fluxo se ele escapar
    -> systemd reinicia o processo se ele encerrar
```

A URL pública e os serviços de produção devem permanecer disponíveis 24x7.
Falhas previstas não poderão produzir encerramento permanente do serviço nem
corrupção silenciosa. Os loops e fallbacks da aplicação atuam antes da supervisão
dos processos pelo sistema operacional.

Implementação principal:

- `workers/worker_flow/iniciar_flow_worker.py`
- `workers/worker_flow/response_flow/flow_worker.py`
- `workers/worker_funil/funil_worker.py`
- `workers/worker_funil/iniciar_worker_funil.py`
- `core/cache/redis_client.py`
- `callback/webhook/services/post_flow.py`
- `deploy/systemd/chatbot-webhook.service`
- `deploy/systemd/chatbot-worker-flow.service`
- `deploy/systemd/chatbot-worker-funil.service`

## 21. Matriz de aderência conferida no código

| Regra | Estado atual | Observação |
|---|---|---|
| Somente a primeira mensagem sem resposta do turno é válida | Implementada | As demais não entram na fila nem no histórico enquanto existir uma fila aberta sem resposta própria do bot. |
| Liberar o próximo turno por resposta específica do bot | Implementada | O histórico vinculado à fila permite recuperação antes de `fila.status='sent'`, sem liberar uma sequência ilimitada. |
| Bloqueio de 30 dias depois da etapa final | Implementada | Banco e cache utilizam janela ou TTL de 30 dias. |
| Flood acima da métrica | Implementada | Redis, banco e memória formam a cadeia de avaliação; flood pode bloquear na Meta. |
| Payload grande | Implementada conforme a regra | Retorna HTTP 413 e não bloqueia a identidade informada no payload. |
| Assinatura inválida | Implementada conforme a regra | Retorna HTTP 403 e não confia no payload nem bloqueia possível vítima informada nele. |
| Falha operacional do webhook com mensagem válida | Implementada | Inserção/commit da fila e validação de unidade indisponível retornam HTTP 503 para permitir reentrega; descartes de negócio continuam HTTP 200. |
| Cache Redis com fallback para banco | Implementada nos caches principais | Unidades, clientes e conversas bloqueadas possuem estratégias de fallback. |
| Autocura Redis/banco | Implementada no contrato da V1 | Cobre falhas detectáveis e FK stale; edição direta no banco é proibida em produção. |
| Admin majoritariamente somente leitura | Implementada | As exceções operacionais são unidade (incluindo seu usuário de monitoramento), integração com o Funil e desbloqueio individual. |
| Admin somente desbloqueia clientes | Implementada | Meta primeiro; falha preserva o registro no banco. |
| Unidade Meta-first na criação e exclusão | Implementada | Falha da Meta impede a alteração do banco. |
| `status_pagamento` sem chamada Meta | Implementada conforme a regra | O valor controla a admissão da unidade, mas não registra nem remove o número na Meta. |
| Desvinculação definitiva da unidade | Definida operacionalmente | Remover do WABA oficial e excluir individualmente pelo Admin. |
| Worker continua ou reinicia depois de falha | Implementada em camadas | `funil_worker.py` recupera banco e agenda os ciclos; `iniciar_worker_funil.py` recria o worker após falha crítica. `iniciar_flow_worker.py` mantém a supervisão do atendimento. |
| Conversa elegível vira oportunidade no Funil | Implementada e desativada por padrão | Etapas 18–22, `funil_envios`, claim com lease e confirmação lógica da ApiCarrossel. |
| Uma falha de lead não interrompe o lote do Funil | Implementada | O item volta para `pending`; os demais continuam no mesmo ciclo. |
| Supervisão dos três processos | Implementada | Os serviços systemd usam `Restart=always`; Nginx encaminha o endpoint público ao webhook. |

## 22. Orientação para futuras alterações

Antes de modificar o fluxo:

1. identificar qual regra deste documento está envolvida;
2. classificar a mudança como correção, refatoração ou alteração de produto;
3. preservar turno único, idempotência e limite de tentativas quando a tarefa não
   solicitar explicitamente o contrário;
4. mapear quedas antes e depois de cada commit;
5. testar fluxo normal, retry antes do bot, retry depois do bot e finalização da
   fila;
6. não tratar um comportamento esperado da V1 como bug apenas por ele parecer
   conservador ou incompleto.

## Follow-up de inatividade e reação do cliente

O worker proativo envia somente `Você viu a minha mensagem?` depois de sete horas
sem reação à última resposta comum confirmada do bot. NULL equivale a stage zero.
O envio exige conversa ativa em etapa 1–17, unidade válida e adimplente, ausência
de bloqueios, de entrada posterior no histórico e de fila pending/processing do
mesmo par cliente/unidade, mesmo se ainda não vinculada à conversa. Uma fila
respondida mas ainda aberta também adia o proativo até sua finalização.

O canal exige janela aberta desde a última mensagem do cliente; este envio em texto
livre não usa template. A implementação reserva um minuto antes de completar 24h
para evitar despacho na borda. Isso não altera o limiar de sete horas do bot.

O worker produz apenas 0 → 1 e não zera o ciclo. Stage positivo permanece até uma
reação do cliente. Não há segundo ou terceiro lembrete, nem fechamento pelo silêncio.
A primeira entrada aceita com stage positivo é armazenada, mas seu conteúdo não é
interpretado como resposta da etapa. A repetição começa com `Que bom te ver novamente,
<nome>!` ou `Que bom te ver novamente!` quando não há nome persistido. Essa saudação
independe do tempo de retorno e não se soma a `Olá novamente`. Não há tratamento,
transição, alteração de turnos_sem_avanco, funil ou encerramento.

A migração inicial marca followup_stage = 1 para todas as conversas ativas antigas,
incluindo etapas 18–21, e registra seus IDs, stages anteriores e a data da marcação
em followup_legado. Não envia lembrete, não encerra conversas, não inventa recibo
nem altera followup_last_sent_at. Stage positivo passa a indicar retomada pendente,
por envio real ou marcação inicial; somente o histórico/recibo comprova envio.
Novas conversas continuam com stage zero. O setup limpo não marca conversas.

Histórico da repetição, marcação da retomada e reset para zero pertencem ao mesmo
commit. followup_last_sent_at permanece como auditoria. Um retry de retomada
concluída usa a resposta já persistida, sem zerar um ciclo posterior. A mensagem
seguinte é interpretada normalmente; outro período de sete horas pode iniciar um
novo ciclo somente nas etapas 1–17 e com as demais condições de envio atendidas.
Stage maior que um segue a mesma recuperação; negativo falha fechado.

Essa desconsideração semântica é uma exceção deliberada à interpretação normal da
entrada. Stage zero preserva os validadores, o mapa e a saudação reativa de três horas.
O registro proativo não possui fila nem hash de cliente de origem e não prova que
uma fila A/B/C foi respondida. Os recibos próprios identificam a conversa e a âncora
do ciclo; registros de retomada identificam a entrada ignorada para recuperação.

Os dois workers compartilham o lock de 110 segundos e seu fencing. Entrada aceita
após o último teste pré-envio pode cruzar com a chamada da Meta: confirmamos o
lembrete e o flow lê stage positivo quando obtiver o lock. A janela entre aceite
externo e commit local continua sujeita à duplicidade rara já aceita na V1.
````

## Passo 23 — `workers/README.md`

**Ação:** Alterar.

Documentar o quarto processo, os novos módulos e o checkpoint de renovação da posse.

````markdown
# Workers

Camada assíncrona responsável pelo atendimento no WhatsApp e pela publicação
periódica de oportunidades no Funil de Vendas.

- [Portal do projeto](../README.md)
- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)
- [Rotina de implementação de etapas](../ROTINA_IMPLEMENTACAO_ETAPAS.md)

## Estrutura

```text
workers/
├── worker_flow/
│   ├── iniciar_flow_worker.py
│   ├── valida_banco.py
│   ├── valida_historico.py
│   ├── tratar_bloqueio.py
│   ├── response_flow/
│   │   ├── flow_worker.py
│   │   ├── flow_sender.py
│   │   ├── etapas/
│   │   │   ├── validadores_universais/
│   │   │   └── validadores_contexto/
│   │   └── transicoes/
│   │       ├── contexto_transicao.py
│   │       ├── eventos.py
│   │       └── resolver_transicao.py
│   ├── transacoes/
│   │   ├── efeitos_transicao.py
│   │   ├── encerramento_atendimento.py
│   │   ├── persistencia_resposta.py
│   │   ├── movimento_conversa.py
│   │   ├── finalizacao_fila.py
│   │   ├── lock_conversa.py
│   │   └── ordem_turno.py
│   └── suporte/
│       ├── cache_repair.py
│       └── estado_ciclo.py
├── worker_funil/
│   ├── iniciar_worker_funil.py
│   ├── config.py
│   ├── funil_worker.py
│   ├── processamento.py
│   └── exceptions.py
└── tratamento_erros_externos/
```

## Ciclo principal

`worker_flow/iniciar_flow_worker.py` supervisiona o processo. Se
`worker_flow()` escapar com uma exceção, registra o traceback, aguarda e
reinicia o fluxo.

`worker_flow/response_flow/flow_worker.py` é o orquestrador do ciclo:

```text
dequeue
-> respeitar mensagem anterior
-> validar cliente, unidade e conversa
-> barrar conversa com bloqueio vigente
-> adquirir lock
-> vincular fila à conversa
-> persistir histórico do cliente
-> rotear e enviar resposta
-> persistir histórico/contexto do bot
-> marcar fila como sent
-> liberar lock e fechar conexão
```

## Propriedade transacional

Conexão, `commit`, `rollback` e `close` do ciclo pertencem ao `flow_worker.py`.
Os commits intermediários são checkpoints recuperáveis:

1. claim da fila;
2. espera por mensagem anterior, quando necessária;
3. validação do banco;
4. lock e vínculo com a conversa;
5. histórico do cliente;
6. histórico e contexto do bot;
7. status `sent`;
8. unlock.

Uma função auxiliar pode executar uma operação com o cursor recebido, mas não
deve decidir a transação fora do orquestrador.

### Vínculo da fila com a conversa

O vínculo `fila_mensagens.id_conversa` é uma anotação de integridade e
ordenação; ele não é o lock de turno e não substitui a resolução atual por
`(cliente, unidade)`.

O repositório preenche o vínculo quando ele está vazio ou já aponta para a mesma
conversa. Um vínculo legado divergente só é reparado quando a fila ainda não tem
histórico. Se nenhuma linha puder ser vinculada com segurança, o worker falha
fechado: devolve a mensagem para `pending` por 300 segundos, sem consumir uma
tentativa de erro e sem enviar resposta.

Se a conversa anterior continuar ativa, a mensagem permanece na mesma conversa
e segue a etapa já atualizada. Se o encerramento tiver bloqueio vigente, a
mensagem é removida como conversa bloqueada. Uma conversa nova só é resolvida
quando o encerramento permite recomeço imediato (`bloqueio_dias = 0`) ou quando
o bloqueio já expirou.

As barreiras que continuam decidindo o atendimento são:

- advisory lock do turno por cliente e unidade no webhook;
- lock versionado da conversa no worker;
- verificação de mensagem anterior ainda aberta;
- `resposta_bot_para_mensagem_atual`, que impede novo envio em um retry.

## Retry e recuperação

- dequeue incrementa `retry_count`;
- `processing` abandonado volta a ser elegível após o timeout do banco;
- falhas tratadas usam `tratamento_erros_externos/expection_process.py`;
- o limite atual é de três tentativas;
- ao atingir o limite, a mensagem é excluída;
- retry com histórico do bot existente não chama a Meta novamente.

O worker mantém a fila sem `sent` quando envio ou persistência final falham.
Depois de uma resposta do bot persistida, o retry repara contexto e conclui a
fila sem duplicar o envio.

## Locks e ordenação

- apenas um worker processa a conversa por vez;
- `lock_version` impede unlock por proprietário antigo;
- uma mensagem posterior não ultrapassa outra anterior aberta;
- a verificação de mensagem anterior ocorre logo depois do claim, antes de
  resolver conversa e tentar seu lock;
- espera por mensagem anterior (30 segundos) ou lock recusado (5 segundos) não
  consome tentativa de erro.

## Response flow

- `flow_worker.py`: transação, checkpoints e handlers.
- `flow_sender.py`: preserva `resposta_bot_atual` e seleciona o resolver da
  etapa atual;
- `etapas/resolver_etapa<n>.py`: valida a resposta, aplica tratamentos e
  encaminha para o destino autorizado;
- `etapas/validadores_universais/`: mídia, financeiro, nome, opções da triagem
  e outras validações reutilizáveis;
- `etapas/validadores_contexto/`: respostas específicas de cada pergunta;
- `transicoes/contexto_transicao.py`: transforma o resultado da consulta em
  origem e mapa explícitos no contexto histórico;
- `transicoes/resolver_transicao.py`: decide `origem + evento -> destino`.

Textos e chamadas PyWa não pertencem a essa pasta. Use
`core/integrations/whatsapp/messages` e
`core/integrations/whatsapp/pywa_functions/pywa_senders`.

Tratamentos não produzem evento e permanecem na etapa atual. Respostas válidas
utilizam a tabela `chatbot.etapa_transicao`; o destino não é calculado com
`id_etapa + 1`.

Validadores universais mantêm o mesmo significado em todas as etapas e não
escolhem entre arestas diferentes. Quando uma resposta pode gerar destinos
distintos, o validador é contextual e devolve diretamente o evento daquela
origem, mesmo que outra etapa reconheça os mesmos textos com eventos próprios.

### Regras atuais das etapas

- Etapa 4: profissão válida é persistida em `conversa.profissao` e atualiza
  também `cliente.profissao`. O snapshot da conversa preserva o atendimento
  anterior quando o cadastro do cliente muda.
- Etapa 6: `suporte_idoso=True` encaminha somente o próprio titular entre 60 e
  99 anos ao número comercial da unidade. O worker persiste a idade e encerra
  na própria etapa 6 com `encaminhado_suporte_idoso`, sem bloqueio de dias.
  Dependentes não entram nessa regra; idade de 100 anos ou mais conserva o
  encerramento próprio por idade inválida. Com suporte desativado, o titular
  de 60 a 99 anos segue para a oferta.
- Etapa 7: confirmações de aceite geram `oferta_aceita` (`7 -> 10`);
  `Talvez mais tarde` gera `oferta_adiada` (`7 -> 8`). Pedidos como
  `quero mais informações` ou `quero saber mais` não são aceite; assim como
  negativas livres, recebem tratamento sem avançar.
- Etapa 10: a política parte de `email_obrigatorio` da unidade, mas o próprio
  titular de 60 a 99 anos fica dispensado quando chega a essa etapa. A exceção
  não se aplica ao dependente nem à idade do responsável. Mídia, reforço e
  financeiro são tratados antes da coleta. Com e-mail opcional, a resposta
  pode avançar como endereço válido, ausência declarada ou não informado;
  os três casos usam `email_valido` (`10 -> 11`). Sem endereço, o efeito grava
  `cliente.email = NULL`, sem manter um e-mail de atendimento anterior.

No retry já respondido, o resultado aceito do e-mail e o encaminhamento de
suporte são reconstruídos pelo histórico original, sem nova chamada à Meta
nem reavaliação da decisão pela configuração atual da unidade.

### Saudação de retorno

Após a etapa 1, `valida_historico.py` compara o horário da mensagem atual do
cliente com o último envio do bot confirmado como `sent` na mesma conversa.
Com intervalo de pelo menos três horas e nome disponível, `flow_sender.py`
prefixa a resposta com `Olá novamente, <nome>!`, inclusive quando ela é um
tratamento. O texto enviado e o histórico recebem o mesmo prefixo uma vez.

Essa saudação não é follow-up nem disparo por inatividade: depende de uma nova
mensagem do cliente, não cria mensagem separada e não altera a transição. A
etapa 1, dados de nome/data ausentes ou incompatíveis e retries com resposta
persistida não geram uma nova saudação.

## Persistência de transições

As responsabilidades estão divididas assim:

- `transacoes/persistencia_resposta.py`: orquestra a persistência final;
- `transacoes/movimento_conversa.py`: classifica e persiste inicialização,
  transição ou permanência;
- `transacoes/efeitos_transicao.py`: exibe cada ponte como
  `origem + evento -> destino` e grava seus efeitos específicos;
- `transacoes/encerramento_atendimento.py`: resolve e aplica encerramentos,
  inclusive a reconstrução do encaminhamento ao suporte no retry.

Fluxo:

```text
histórico do bot
-> movimento da conversa e confirmação da aresta no PostgreSQL
-> efeitos específicos da transição
```

O `flow_worker.py` continua dono do commit e rollback. Os repositórios recebem o
cursor e não controlam a transação.

## Worker do Funil

`worker_funil` é independente do atendimento. Ele não consome
`fila_mensagens`, não envia WhatsApp e não altera o mapa de transições.

`funil_worker.py` possui o laço operacional interno: executa um ciclo completo,
aguarda `FUNIL_INTERVALO_SEGUNDOS` depois do sucesso (padrão: 1.800 segundos,
30 minutos) e recupera indisponibilidade esperada do
banco com espera linear de 5 em 5 segundos, limitada a 60. O arquivo
`iniciar_worker_funil.py` possui o laço supervisor externo. Se uma falha crítica
escapar do worker, ele aguarda 5 segundos fixos e cria o worker novamente.

```text
materializar conversas em etapas elegíveis
-> claim de um funil_envios com FOR UPDATE SKIP LOCKED
-> commit da reserva
-> montar snapshot do cliente/dependente/triagem
-> encerrar a transação de leitura
-> criar uma oportunidade na ApiCarrossel
-> marcar lead_no_funil e funil_envios=sent no mesmo commit local
-> repetir até o limite do lote
-> aguardar FUNIL_INTERVALO_SEGUNDOS
```

Cada lead é isolado. Falha de payload ou API volta o item para `pending`, agenda
a próxima tentativa e permite processar os demais. Indisponibilidade operacional
do banco é recuperada pelo laço interno; defeitos críticos escapam para o
supervisor externo.

O claim possui lease: um item abandonado em `processing` volta a ser elegível
depois de `FUNIL_LEASE_SEGUNDOS`. Isso permite recuperação de processo morto e
protege múltiplas instâncias com `SKIP LOCKED`.

Não existe transação distribuída entre PostgreSQL e Funil. Se o CRM confirmar e
o banco cair antes do commit local, o item permanece `processing` e poderá ser
reenviado após o lease. O título atual é `Chatbot Lead <nome_unidade>` e não
contém o ID da conversa; ele não identifica sozinho um envio nem impede
duplicidade externa. Não há reconciliação automática com o CRM.

O processo nasce desativado. `FUNIL_WORKER_ENABLED=True` deve ser configurado
somente depois do teste manual da unidade. O ponto de entrada é
`python -m workers.worker_funil.iniciar_worker_funil`; o serviço de produção
está em
[`deploy/systemd/chatbot-worker-funil.service`](../deploy/systemd/chatbot-worker-funil.service).

## Testes relacionados

- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`;
- `tests/unit/test_validador_profissao.py`;
- `tests/unit/test_valida_etapa7.py`;
- `tests/unit/test_sondas_funil.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../tests/README.md).

## Worker de follow-up

`worker_followup/iniciar_worker_followup.py` é o quarto serviço da VM. Seu laço
seleciona candidatos pelo PostgreSQL e chama `followup_worker.py`, proprietário
da conexão e dos commits proativos. Não faz dequeue nem chama validadores de etapas.
`FOLLOWUP_WORKER_ENABLED` é falso por padrão em execução manual; a unit systemd
o habilita explicitamente. Lote padrão: 20; intervalo entre lotes: 60 segundos.
As candidatas são processadas uma por vez, com lock e transações independentes.
Somente etapas 1–17 admitem novos lembretes; etapas 18–22 são inelegíveis.
A paginação visita candidatos posteriores mesmo quando os primeiros falham.
Uma falha individual não interrompe o lote. A candidata pode ser tentada novamente
quando a paginação voltar ao início, depois de revalidar todas as condições; não
há promessa de retry no lote imediatamente seguinte ou de reenvio fora da janela Meta.

No flow, o contexto é relido depois do lock. `transacoes/retorno_followup.py` registra
a reação e recupera a prova de repetição. `response_flow/repeticao_followup.py`
chama os senders normais da etapa, sem resolvers de negócio. A renovação do lock
antes do envio acrescenta um checkpoint; persistência final e finalização da fila
validam a posse antes de alterar dados. Repositórios não controlam commits.
Stage positivo, por lembrete ou migração inicial, prefixa a repetição com
`Que bom te ver novamente, <nome>!` ou `Que bom te ver novamente!` sem nome salvo.
O histórico guarda exatamente o texto enviado. Stage zero mantém `Olá novamente`
na regra existente de três horas.

Deploy: preparar banco e código, reiniciar flow compatível, então iniciar follow-up.
Rollback: parar o proativo primeiro e manter flow compatível enquanto houver stage
positivo ou retomadas pendentes. Desligar o serviço não limpa esses registros.
````

## Passo 24 — `core/repositories/README.md`

**Ação:** Alterar.

Documentar as tabelas internas e a responsabilidade de persistência sem controle da transação.

````markdown
# Repositorios

SQL de runtime da aplicacao. Os modulos sao agrupados por dominio e entidade,
nao pelo consumidor nem pelo tipo de comando SQL.

- [Portal do projeto](../../README.md)
- [Padroes de arquitetura](../../PADROES_DE_ARQUITETURA.md#sql-e-repositórios)
- [Banco e deploy](../database/README.md)

## Estrutura

```text
core/repositories/
|-- atendimento/
|   |-- clientes.py
|   |-- conversas.py
|   |-- dependentes.py
|   |-- fila.py
|   `-- historico.py
|-- fluxo/
|   |-- contextos/
|   |-- pesquisa_satisfacao.py
|   |-- politicas.py
|   |-- transicoes.py
|   `-- triagem.py
|-- unidades/
|   |-- consultas.py
|   `-- cache_control.py
|-- seguranca/
|   |-- bloqueio_meta.py
|   |-- suspeita_bot.py
|   `-- turno_cliente.py
|-- monitoramento/
|   |-- acessos.py
|   `-- painel.py
`-- funil/
    |-- integracao.py
    |-- envios.py
    `-- leads.py
```

`atendimento` persiste as entidades centrais da conversa. `fluxo` consulta e
registra regras do mapa de etapas. `unidades` concentra consultas e versao do
cache. `seguranca` guarda as barreiras de turno e bloqueio. `funil` cobre a
configuracao por unidade e o estado dos envios ao CRM.

`monitoramento/acessos.py` consulta `unidade.id_usuario_monitoramento`, o vínculo
1:1 opcional entre conta e unidade, revalidando a conta no banco. Sem referência
não há acesso. Opcionalmente verifica conversa e mensagem na
mesma leitura, sempre pela unidade da conversa. Recebe o ID do usuário da sessão
por meio do serviço HTTP; não aceita um ID de unidade fornecido pelo navegador.
Retorna `AcessoMonitoramento` ou `None`. Não lê credenciais nem concede acesso
especial a superusuários.

`monitoramento/painel.py` contém somente SELECTs para unidade, conversas,
mensagens, métricas, perfis, satisfação, etapas, atividade e contatos. Todas as
funções exigem o `id_unidade` já obtido pelo guard e repetem o escopo no próprio
SQL. O navegador não fornece esse identificador.

No domínio `funil`:

- `integracao.py` lê widget, link e canal da unidade;
- `leads.py` reúne cliente, dependente e triagem, preservando a profissão da
  conversa e a resposta histórica de e-mail;
- `envios.py` materializa, reivindica, reagenda e confirma a fila
  `chatbot.funil_envios`.

O repositório não executa HTTP. O `workers/worker_funil` controla commits e
chama `core/integrations/funil` depois de encerrar a transação de leitura.

## Contextos e histórico do atendimento

- `fluxo/contextos/etapa6.py` lê `suporte_idoso`, `bpa_ativo` e número comercial
  da unidade; `fluxo/contextos/etapa10.py` lê `email_obrigatorio`, destino do
  atendimento e idade do titular. Os repositórios validam a integridade dos
  dados, mas o resolver aplica a regra de atendimento.
- `atendimento/conversas.py` grava `conversa.profissao`, o snapshot capturado
  na etapa 4; `atendimento/clientes.py` também atualiza o cadastro corrente.
  O Funil usa a profissão da conversa, nunca `cliente.profissao` como fallback.
- `funil/leads.py` busca o e-mail pela mensagem do cliente na etapa 10 ligada
  ao envio confirmado do bot na etapa 11, na mesma conversa, fila e mensagem
  de origem. `cliente.email` só é fallback para legado sem esse vínculo;
  a classificação do valor ocorre fora do SQL, em `core/validacoes/email.py`.
- `atendimento/historico.py` fornece o nome e o último bot `sent` da conversa
  para a saudação de retorno. O repositório não decide o intervalo de três
  horas nem dispara mensagens.

## Contrato

Uma funcao de repositorio deve:

- receber `cursor`;
- usar SQL parametrizado;
- retornar linha, tupla, booleano, quantidade afetada ou uma representacao
  simples do resultado;
- validar invariantes persistidas quando necessario;
- deixar excecoes de persistencia chegarem ao orquestrador.

Uma funcao de repositorio nao deve:

- chamar `get_conn`;
- executar `commit`, `rollback` ou `close`;
- decidir retry;
- retornar resposta HTTP;
- acessar Redis, Meta ou outro servico externo;
- escolher a proxima etapa do atendimento.

## Mapeamento de resultados

Converter uma linha SQL em `dict`, tupla nomeada ou dataclass pertence ao
repositorio quando isso apenas nomeia os dados consultados. Decisoes de negocio,
montagem de mensagens, retry e efeitos externos continuam fora desta pasta.

## Propriedade da transacao

```text
worker_flow  -> flow_worker.py
worker_funil -> funil_worker.py e processamento.py
webhook      -> post_flow.py, flood_guard.py ou bloqueio_meta_guard.py
scripts      -> proprio ponto de entrada
```

O repositorio nao anuncia rollback que nao executou. Ele propaga a excecao para
o dono real da transacao registrar e decidir a recuperacao.

## Idempotencia e concorrencia

- `seguranca/turno_cliente.py` usa advisory lock por cliente e unidade;
- `atendimento/fila.py` preserva a ordem por timestamp Meta e ID;
- `atendimento/historico.py` reutiliza os vinculos da mensagem original;
- `fluxo/transicoes.py` carrega somente as arestas permitidas para a origem;
- updates de conversa exigem origem, evento e destino compativeis;
- reaplicacao idempotente aceita somente a origem ou o destino exato.

## Ao criar um repositorio

Acrescente a operacao ao modulo da entidade correspondente. Crie um novo modulo
quando houver um dominio real e coeso; nao crie `utils.py` generico e nao mova
DDL para esta pasta.

## Testes relacionados

- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../../tests/README.md).

## Registros de follow-up

`atendimento/followup.py` concentra seleção, releitura, fencing e recibos de envio
proativo e retomada. Recebe cursor; não abre conexão, não faz commit e não importa
worker. O histórico permanece particionado; a unicidade do ciclo fica na tabela
não particionada `followup_envio`, pela chave composta conversa + ID/data da âncora.
`followup_retomada` permite reconstruir a reação ignorada em retries após o reset.
`followup_legado` audita a marcação inicial de todas as conversas ativas com stage 1,
preservando ID, stage anterior e horário da migração. Esse registro não é um envio.
As tabelas são internas, sem ações no monitoramento ou no admin.
````

## Passo 25 — `core/integrations/whatsapp/README.md`

**Ação:** Alterar.

Documentar catálogo, sender proativo e sessão opcional sem misturar envio e regras de negócio.

````markdown
# Integração WhatsApp

Comunicação com a Meta WhatsApp Cloud API por meio da biblioteca PyWa.

- [Portal do projeto](../../../README.md)
- [Regras de negócio](../../../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../../../PADROES_DE_ARQUITETURA.md#whatsapp-e-pywa)
- [Integrações externas](../README.md)

## Estrutura

```text
core/integrations/whatsapp/
├── exceptions.py
├── numero_comercial.py
├── messages/
│   ├── etapa1_messages.py ... etapa22_messages.py
│   ├── componentes_compartilhados.py
│   ├── tratamentos_universais.py
│   └── triagem_componentes.py
├── pywa_functions/
│   ├── cliente.py
│   ├── saudacao.py
│   ├── resposta_envio.py
│   ├── ferramentas.md
│   └── pywa_senders/
│       ├── etapa1.py ... etapa22.py
│       └── triagem_base.py
└── tools/
    ├── ativando_numero.py
    ├── ativando_waba_id.py
    ├── config.py
    ├── desativando_numero.py
    ├── desativa_waba_id.py
    ├── usuarios.py
    └── validando_phone_waba.py
```

## Direção das dependências

```text
worker -> pywa_functions -> messages
                      |--> cliente PyWa
                      `--> Meta
```

`messages` não importa PyWa. `pywa_senders` pode importar `messages`, cliente e
exceções da integração. Nenhum deles controla banco, fila, transição ou retry.

## Messages

Catálogo de conteúdo enviado:

- textos;
- títulos de botão;
- callbacks;
- funções puras de montagem.

Textos de WhatsApp não devem ser escritos diretamente no worker. Alterar uma
mensagem não deve mover a responsabilidade de envio para `messages`.

Cada etapa de 1 a 22 mantém seu próprio arquivo `etapaN_messages.py`.

As apresentações inicial padrão, de mídia, financeira e de tratamento de
reforço escolar da etapa 1 recebem `nome_unidade`, `nome_agente` e `genero` como
argumentos já validados pelo worker. `messages` apenas escolhe `o` ou `a` e
formata o texto; não consulta o banco nem conhece a conversa.

`componentes_compartilhados.py` também monta `Olá novamente, <nome>!` quando
o cliente retorna pelo menos três horas após o último envio confirmado do bot
na mesma conversa. A etapa 1 fica fora da regra; nome ou datas ausentes ou
incompatíveis não interrompem o atendimento e não produzem prefixo.

O worker fornece o contexto histórico e aplica a saudação à resposta corrente,
inclusive tratamentos, sem mudar o destino. Não é follow-up, mensagem separada
ou disparo automático após três horas de inatividade. No retry com resposta
persistida, não há novo envio.

## PyWa functions

Concentra a criação do cliente PyWa e o transporte das mensagens do fluxo. Os
senders são o local normal para chamadas de envio; operações compartilhadas de
bloqueio e desbloqueio ficam em `tools/usuarios.py`, que reutiliza a mesma
fábrica de cliente em `pywa_functions/cliente.py`.

- `cliente.py`: normaliza `phone_id`, cria `WhatsApp` e aplica o prefixo de
  retorno somente no escopo do envio corrente;
- `saudacao.py`: seleção de bom dia, boa tarde ou boa noite pelo horário do
  atendimento inicial, distinta da saudação de retorno;
- `resposta_envio.py`: extrai o ID confirmado pela Meta e falha se ele faltar;
- `pywa_senders/etapaN.py`: mensagens normais e tratamentos específicos da
  etapa N.

Cada sender escolhe conteúdo, legenda e lista de botões, realiza a chamada PyWa
e devolve um contexto técnico com o ID da Meta e a etapa da mensagem enviada.
O sender não escolhe origem, evento ou destino da transição.

O encaminhamento de suporte ao idoso é um sender da etapa 6 com botão para o
número comercial, normalizado por `numero_comercial.py`. A decisão de usar
`suporte_idoso`, validar a faixa de 60 a 99 anos e encerrar o atendimento é do
worker. Da mesma forma, a política `email_obrigatorio` e a distinção entre
aceite da oferta e pedido de informações não pertencem aos senders.

Uma função de mídia envia somente um arquivo. Lotes e álbuns exigem um contrato
futuro capaz de persistir vários IDs e tratar sucesso parcial.

Os senders devolvem contexto simples para o worker. Falhas são encadeadas com
`ErroEnvioMeta`, permitindo rollback e retry sem esconder a causa original.

## Tools

Operações Meta compartilhadas e ferramentas administrativas usadas pelo
Django Admin e pelo webhook:

- registrar/desregistrar número;
- validar o vínculo entre WABA e phone ID;
- ativar/desativar a inscrição WABA;
- bloquear e desbloquear usuários na Meta.

Relatórios conscientes e somente leitura ficam em
[`utilitarios/monitoring/blocked_users.py`](../../../utilitarios/monitoring/blocked_users.py).
Eles comparam bloqueios pela chave completa
`(waba_id, phone_id_unidade, wa_id_cliente)` e reconciliam registros Cloud API.

`tools/usuarios.py` é a primitiva única de bloqueio e desbloqueio consumida pelo
webhook e pelo Admin. Os demais módulos deste diretório atendem às operações de
configuração da conta e do número. Eles podem reutilizar a fábrica de cliente,
mas não devem duplicar envio de etapa nem assumir responsabilidades de banco,
fila ou transação.

`tools/config.py` centraliza a configuração operacional da integração Meta, mas
os valores são lidos por `core/config_env.py` a partir de variáveis de ambiente:

```text
META_ACCESS_TOKEN
META_GRAPH_API_VERSION
META_HTTP_CONNECT_TIMEOUT_SECONDS
META_HTTP_READ_TIMEOUT_SECONDS
META_PHONE_REGISTRATION_PIN
```

`META_GRAPH_API_VERSION` usa o formato `26.0`, sem o prefixo `v`. Essa versão é
aplicada ao cliente PyWa e a todas as URLs diretas da Graph API. Se uma versão
nova apresentar incompatibilidade, a variável pode retornar manualmente para a
última versão estável validada.

Não adicione token ou outro valor sensível diretamente nesse arquivo. WABA ID e
phone number ID são dados por unidade e devem vir do banco/cache.
`META_PHONE_REGISTRATION_PIN` também é segredo operacional e só é necessário
para a operação administrativa de registro do número; não deve ser exibido em
logs, documentação ou mensagens.

## Limites

Esta integração não deve:

- executar SQL ou Redis;
- decidir etapa persistida;
- marcar fila como `sent`;
- escolher quantidade ou intervalo de retries;
- executar commit, rollback ou close;
- importar módulos de `callback` ou `workers`.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../../../tests/README.md).

## Lembrete de follow-up

`messages/followup_messages.py` também monta a saudação de retomada com stage
positivo: `Que bom te ver novamente, <nome>!` ou `Que bom te ver novamente!`.
O nome vem do cadastro persistido; não é extraído da reação que será desconsiderada.
O prefixo é aplicado no corpo da etapa repetida, preservado no histórico e removido
do escopo ao sair do sender, inclusive em falhas. O proativo continua sem saudação.

`messages/followup_messages.py` contém o único texto aprovado.
`pywa_senders/followup.py` envia texto sem botões, sem saudação de retorno e sem
id_mensagem_fila fictício. Usa sessão HTTP com timeout e sem retry automático;
recebe destinatário e phone_id da unidade. `conta_wa` aceita sessão opcional sem
alterar os clientes existentes. Stage e persistência pertencem ao worker/repositório.
````

## Passo 26 — `tests/README.md`

**Ação:** Alterar.

Documentar os testes novos, a execução padrão e a condição explícita para testes PostgreSQL.

````markdown
# Testes do projeto

Esta pasta reúne a suíte unitária e de contrato do projeto. Além do núcleo
transacional, ela cobre regras e utilitários já implementados:

- cenário completo de turno A/B/C;
- retry, requeue, ordem da fila e fencing por `lock_version`;
- persistência idempotente, avanço e não avanço de etapa;
- checkpoints, commits, rollback e conclusão da fila no worker.
- suporte ao idoso e obrigatoriedade do e-mail;
- validação da oferta, início da triagem, profissão e saudação após inatividade;
- montagem dos relatórios semanais e totais;
- payloads e sondas manuais do Funil;
- vínculo 1:1 opcional de monitoramento e autorização de conversas/mensagens por unidade;
- login nativo, par username/senha, sessão, CSRF e revogação do acesso ao portal;
- painel somente leitura, períodos, consultas por unidade, botões históricos,
  indicadores e arquivos Google CSV.

Para executar a suíte completa a partir da raiz:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py"
```

Organização atual:

```text
tests/unit/test_fluxo_turno_abc.py
tests/unit/test_retry_essencial.py
tests/unit/test_persistencia_essencial.py
tests/unit/test_worker_flow_runtime.py
tests/unit/test_suporte_idoso_email_obrigatorio.py
tests/unit/test_saudacao_retorno.py
tests/unit/test_valida_etapa7.py
tests/unit/test_valida_etapa11.py
tests/unit/test_validador_profissao.py
tests/unit/test_gerar_monitoramento_unidades.py
tests/unit/test_metricas_perfis_relatorios.py
tests/unit/test_sondas_funil.py
tests/unit/test_monitoramento_unidade.py
tests/unit/test_monitoramento_login.py
tests/unit/test_monitoramento_painel.py
```

Os testes usam fakes e mocks para fronteiras externas: a descoberta da suíte não
deve chamar Meta, Funil, Redis, RDS nem outro serviço real. Um utilitário manual
não deve ser executado como forma de testar sua importação.

Novos testes pertencem a `tests/unit/`; dados e classes auxiliares exclusivos de
teste ficam em `tests/`, nunca nos módulos de produção.

O teste de monitoramento executa o SQL de autorização em SQLite em memória,
adaptando apenas os placeholders, com um cliente compartilhado por duas
unidades. Cobre isolamento por conversa/mensagem, revogação do vínculo,
desativação de conta, várias unidades sem conta, exclusividade do usuário,
exclusão da conta com preservação da unidade, sessão inválida e falha de banco.
Não acessa o RDS. `fixtures/unidade_monitoramento_legado.sql` representa apenas
a proposta anterior para testar a transferência dos vínculos; não é uma
migração de produção.

`test_monitoramento_login.py` usa o backend, hashes de senha e sessões reais do
Django com usuários fictícios e SQLite em memória. Cobre senha de outra conta,
contas não autorizadas, erros, expiração de CSRF, logout, rotação de sessão,
redirecionamento fixo e escape de HTML. Substitui somente a conexão da thread
durante o teste e restaura-a ao terminar; não cria usuários nem tabelas no RDS.

`test_monitoramento_painel.py` valida as rotas privadas, métodos permitidos,
propagação obrigatória da unidade autorizada, quantidade de parâmetros dos SQLs,
consolidação de perfis, 22 etapas, períodos comparáveis e os quatro downloads
CSV (Google e essencial, todos e elegíveis). Cobre todos os períodos, unidade
autorizada, revogação de acesso, acentos, campos vazios e proteção contra fórmulas
nos dados textuais. Seus payloads vivem em `fixtures/monitoramento_painel.py` e
são fictícios.

## Follow-up

`unit/test_followup.py` cobre envio exato, reação, etapas e botões reais com HTTP
substituído, recuperação, falta de lock, falhas e parâmetros SQL. O teste de runtime
do flow cobre o novo caminho sem chamar validadores ou persistência de transição.
Cobre saudação com e sem nome, texto enviado igual ao histórico, isolamento do
prefixo sob exceção, retorno legado sem data de envio e falha sem interromper o lote.

`integration/test_followup_postgres.py` exige explicitamente FOLLOWUP_TEST_DSN com
host loopback e banco vazio chamado `test_chatbot_followup`. Ele cria e remove seu
próprio schema chatbot, recusando schema preexistente. Sem essa variável é pulado.
Executa DDL canônico, consultas reais, unicidade em histórico particionado, rollback,
fila sem vínculo e dois proprietários do lock. Nunca aponta para DB_HOST/DB_NAME.
Também executa o SQL integral de migração sobre uma base antiga descartável:
marca somente ativas, audita os valores anteriores, preserva os demais dados,
não produz histórico/envio, recusa reaplicação e reverte diante de legado terminal.
Meta permanece simulada; a confirmação de entrega real exige homologação manual.
````

## Passo 27 — `deploy/README.md`

**Ação:** Alterar.

Documentar migração, diagnóstico, ativação dependente do flow e desligamento sem apagar ciclos existentes.

````markdown
# Implantacao no Lightsail

Os arquivos assumem a aplicacao em `/opt/chatbot/app`, o ambiente virtual em
`/opt/chatbot/venv` e as variaveis em `/etc/chatbot/chatbot.env`. Os tres
processos da aplicacao sao independentes e escrevem seus logs no journald. O
portal de monitoramento faz parte do processo web `chatbot-webhook`; ele não
cria um quarto serviço.

## Preparar a aplicacao

Clone a branch `prod` como o usuario `ubuntu` e instale as dependencias:

```bash
git clone --branch prod --single-branch git@github.com:Levi-cell/Chatbot.git /opt/chatbot/app
python3 -m venv /opt/chatbot/venv
/opt/chatbot/venv/bin/pip install --upgrade pip
/opt/chatbot/venv/bin/pip install -r /opt/chatbot/app/requirements.txt
```

Crie `/etc/chatbot/chatbot.env` conforme o procedimento em
[`regras_deploy/modificando_env_e_banco_em_prod.md`](../regras_deploy/modificando_env_e_banco_em_prod.md),
sem registrar segredos no repositorio. Em producao, use `DJANGO_DEBUG=False`,
configure o dominio em `DJANGO_ALLOWED_HOSTS` e mantenha o arquivo restrito:

```bash
sudo chown root:chatbot /etc/chatbot/chatbot.env
sudo chmod 0640 /etc/chatbot/chatbot.env
```

Defina `FUNIL_WORKER_ENABLED=True`, configure o RDS com TLS e informe o
endpoint do Redis remoto em `REDIS_HOST`. A aplicacao nao usa nem exige um
`redis-server` local na VM. Mantenha `PGSSLCERTMODE=disable` quando o RDS
autenticar por usuario/senha. Essa opcao desativa apenas o certificado TLS de
cliente; use `DB_SSLMODE=verify-full` e `DB_SSLROOTCERT` para continuar
validando o certificado do servidor.

Se o banco estiver vazio, crie antes o schema de destino no DBeaver:

```sql
CREATE SCHEMA IF NOT EXISTS chatbot;
```

Depois, prepare o Django. Suas migrations criam `chatbot.auth_user`, necessária
antes do DDL de negócio por causa do vínculo de monitoramento:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py migrate --noinput'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
```

`EnvironmentFile` é carregado automaticamente somente pelo systemd. Uma sessão
SSH comum não recebe essas variáveis; os comandos manuais acima carregam o mesmo
arquivo privado dos serviços sem exibir seu conteúdo.

Em uma instalação vazia, após as migrations do Django, siga o
[setup do banco de negócio](../core/database/README.md#setup) antes de iniciar
os serviços. Na atualização de um banco existente, use a migração incremental
específica, sem executar novamente o setup como substituto da migração.

## Instalar os servicos

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now chatbot-webhook chatbot-worker-flow chatbot-worker-funil
```

```bash
systemctl status chatbot-webhook chatbot-worker-flow chatbot-worker-funil
journalctl -u chatbot-webhook -u chatbot-worker-flow -u chatbot-worker-funil -f
```

## Habilitar o Nginx e HTTPS

Instale o template, substitua `__DOMAIN__` pelo dominio real e habilite o site.
O Gunicorn escuta somente em `127.0.0.1:8000`; apenas o Nginx recebe trafego
publico.

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/nginx/chatbot.conf /etc/nginx/sites-available/chatbot
sudoedit /etc/nginx/sites-available/chatbot
sudo ln -sfn /etc/nginx/sites-available/chatbot /etc/nginx/sites-enabled/chatbot
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

Com o DNS apontando para o IP estatico e as portas 80/443 abertas, deixe o
Certbot criar a configuracao HTTPS somente depois de emitir o certificado:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx --redirect -d SEU_DOMINIO
sudo certbot renew --dry-run
```

Somente depois de o HTTPS funcionar, ative no ambiente
`DJANGO_TRUST_X_FORWARDED_PROTO=True`, `DJANGO_SECURE_SSL_REDIRECT=True`,
`DJANGO_SESSION_COOKIE_SECURE=True` e `DJANGO_CSRF_COOKIE_SECURE=True`, e
reinicie o webhook. O Nginx sobrescreve `X-Forwarded-Proto`; o Django nao confia
em um valor enviado diretamente pelo cliente.

## Atualizacao rotineira da branch prod

O procedimento canonico esta em
[`regras_deploy/rotina_deploy.md`](../regras_deploy/rotina_deploy.md).

Na atualizacao comum, somente `chatbot-worker-flow` e
`chatbot-worker-funil` sao parados. O webhook continua recebendo e enfileirando,
mas precisa receber `HUP` depois do `git pull`: o Gunicorn de producao nao possui
auto-reload. Alteracao de `.env` ou da unit do webhook exige `restart` e segue
[`modificando_env_e_banco_em_prod.md`](../regras_deploy/modificando_env_e_banco_em_prod.md).

## Migracoes incrementais do banco de negocio

Os scripts SQL revisáveis para o RDS existente ficam em `deploy/migrations/`.
Eles não são executados por `manage.py migrate` nem pelo setup de instalação
limpa. Siga os pré-requisitos, as validações e a orientação de rollback do
próprio arquivo antes de publicar o código que depende do novo estado.

Para o cadastro de monitoramento, execute
`deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql` inteiro no DBeaver
antes de publicar o Admin atualizado. Requer `chatbot.unidade` e
`chatbot.auth_user`. O script adiciona `unidade.id_usuario_monitoramento`, com
`UNIQUE` e FK `ON DELETE SET NULL`. Se `unidade_monitoramento` já existir,
valida e transfere os vínculos antes de removê-la, sem `CASCADE`. O SQL anterior
de criação da tabela foi substituído e não deve ser executado.

É uma migração de aplicação única: coluna já existente causa erro. Em caso de
falha, execute `ROLLBACK`; investigue a causa antes de repetir. `ALTER TABLE`
fica somente nesta migração, enquanto o DDL de instalação limpa já contém a
coluna em seu `CREATE TABLE`. Depois da migração, não publique novamente o
código que depende da tabela antiga. Uma reversão exige preservar os vínculos
atuais e preparar um SQL específico antes de voltar o código.

## Operacao dos servicos e do Redis remoto

Os comandos individuais para iniciar e parar cada processo, limpar somente os
bloqueios no Redis remoto e remover o servidor Redis local da VM estao em
[`regras_deploy/servicos_e_redis_remoto.md`](../regras_deploy/servicos_e_redis_remoto.md).

Nao exponha a porta `6379` e nao use `FLUSHDB` ou `FLUSHALL` em producao.

## Ativação do follow-up

Esta alteração exige migração manual `migrations/followup_registros.sql` antes do
flow novo. Instalação limpa utiliza `followup_script.py`, chamado por `bank_script`.
As colunas followup_stage/last_sent_at já existentes não são recriadas. Com o flow
parado e o follow-up desligado, a migração registra em followup_legado todas as
conversas ativas e marca followup_stage = 1, inclusive nas etapas 18–21. O horário
last_sent_at, o histórico, a etapa e a finalização permanecem como estavam.
O script é único e transacional; não reaplicar nos próximos deploys. O setup limpo
cria as três tabelas e não marca conversas. A marcação não comprova envio de mensagem.
Conversa ativa terminal/inconsistente recusa toda a migração: concluir a recuperação
pendente do flow e revisar a anomalia antes de tentar de novo, sem encerrar em massa.

Instalar `systemd/chatbot-worker-followup.service` e executar daemon-reload não
inicia envios. A unit habilita FOLLOWUP_WORKER_ENABLED; se essa chave já existir no
EnvironmentFile, conferir a precedência antes da ativação. Nenhum segredo novo é necessário.
Reiniciar primeiro chatbot-worker-flow.service. Somente após validar o flow e a
consulta sem envio, habilitar e iniciar chatbot-worker-followup.service.

`python -m utilitarios.verificar_followup` faz leitura e mostra IDs de uma amostra.
Não é uma execução do worker e não envia mensagens. Um resultado vazio é válido.

Para interromper os lembretes, parar e desabilitar a unit de follow-up. Isso mantém
o flow apto a tratar retornos de lembretes ou do legado marcado. Não apagar recibos, resetar
stages em massa nem reverter o flow incompatível enquanto existirem ciclos positivos.
````

---

# Homologação e aplicação — sequência operacional

As seções abaixo explicam quando executar os arquivos já descritos. Não são novos
arquivos nem etapas faltantes de código. A implantação real deverá ocorrer depois
da revisão e da aprovação da versão que materializar este plano.

## Verificações já realizadas nesta preparação

Na preparação inicial, em cópia temporária isolada da base, com os arquivos propostos materializados:

- 19 arquivos Python passaram por parsing/compilação sintática e formatação.
- 53 statements/consultas SQL passaram pelo parser PostgreSQL, incluindo a consulta
  completa de candidatas. Parsing não comprova execução, índices ou concorrência.
- A suíte encontrou **195 testes: 188 passaram e sete de PostgreSQL foram pulados**.
- Os testes de repetição exercitam os senders reais das etapas 1–21 nos caminhos
  titular/dependente, substituindo o cliente HTTP. Comparam o texto enviado com o
  histórico proposto e verificam que não há evento de transição.
- Os testes de runtime verificam que o ramo de reação não chama validação,
  sender normal ou persistência de transição; os contratos anteriores de ordem e
  checkpoints continuam cobertos.

Não houve conexão ao RDS, Redis, Funil ou Meta; não houve mensagem real enviada.
Na revisão de migração e saudação, **36 testes unitários de follow-up/runtime
passaram e nove testes PostgreSQL foram pulados**. Os testes cobrem saudação com e
sem nome, corpo enviado igual ao histórico, retorno legado sem data de envio,
escopo do prefixo sob erro e continuação do lote após falha. Os testes PostgreSQL
incluem seleção/releitura nas etapas 1–22 e execução integral da migração sobre
legado descartável, mas ainda não foram executados. Os 27 blocos completos,
seus hashes e a sintaxe Python/SQL foram conferidos.
Os testes PostgreSQL estão entregues, mas **a execução deles permanece como gate de
homologação**. Não há alegação de teste com dois processos reais de produção ou de
medição de desempenho no RDS nesta preparação.

## Executar a suíte sem serviços externos

Na raiz da cópia em que todos os passos tenham sido materializados:

```bash
python -m unittest discover -s tests -t . -p 'test_*.py'
```

Os testes do projeto configuram seus ambientes fictícios. Sem `FOLLOWUP_TEST_DSN`,
o conjunto PostgreSQL permanece explicitamente pulado; isso não equivale a passar
o gate de integração.

## Executar o gate PostgreSQL local

Preparar um banco **local, vazio e descartável**, chamado `test_chatbot_followup`,
com autenticação local configurada para o usuário de teste. Exemplo em terminal
Bash de desenvolvimento com PostgreSQL instalado:

```bash
createdb -h 127.0.0.1 -U postgres test_chatbot_followup
export FOLLOWUP_TEST_DSN='host=127.0.0.1 port=5432 dbname=test_chatbot_followup user=postgres'
python -m unittest tests.integration.test_followup_postgres -v
unset FOLLOWUP_TEST_DSN
```

O teste recusa host que não seja loopback, outro nome de banco e schema `chatbot`
preexistente. Cria seu schema e o remove ao terminar. Não reutilizar o banco da
aplicação para esse teste. A senha local, se necessária, deve vir da configuração
de autenticação desse PostgreSQL de desenvolvimento.

Além da suíte, a homologação precisa percorrer estas fronteiras:

| Cenário | Evidência exigida |
|---|---|
| Instalação limpa | Setup canônico cria recibos e índices uma única vez. |
| Banco existente | SQL integral cria as três estruturas, marca todas as ativas e audita stages anteriores; erro reverte tudo. Encerradas e novas conversas são preservadas. |
| Reaplicação da migração | Recusada sem remarcar conversas que já retornaram ou foram criadas depois. |
| Legado terminal/inconsistente | Migração recusada integralmente; recuperar/revisar a pendência sem fechamento em massa. |
| 6h59 e exatamente 7h | Nenhum envio antes do limiar; elegibilidade inclusiva depois dele. |
| Stage 1 com silêncio prolongado | Nenhum segundo lembrete nem encerramento. |
| Reação por texto, botão ou mídia | Histórico da entrada existe; saudação com/sem nome e pergunta/botões atuais são repetidos; zero somente após commit. |
| Falha em candidata | Próximas candidatas continuam; a falha volta à seleção após fechar a varredura, apenas se elegível. |
| Falha depois do envio e antes do commit | Alerta da janela externa residual; nenhuma afirmação de sucesso local sem prova. |
| Queda depois do commit e antes de sent | Retry encontra marcador concluído e histórico; não reenviar nem interpretar a reação. |
| Nova fila durante o HTTP | Comprovar que o lembrete confirmado é gravado e o flow lê stage 1 ao obter o lock. |
| A/B/C e duas instâncias concorrentes | Ordem e prova de resposta própria de cada fila continuam decidindo o turno. |
| Takeover e dono antigo | Fencing barra atualização/reset/finalização/unlock do proprietário antigo. |
| Outra unidade | Fila, bloqueio ou ciclo da unidade B não interfere na unidade A. |
| Consulta real em volume | Executar EXPLAIN em homologação com volume representativo; medir antes de propor índice adicional. |
| Monitoramento | Lembrete como mensagem de texto, sem botões inventados; contagem geral atualizada e acesso isolado. |
| Reinício/SIGTERM | Parar de selecionar/despachar; concluir ou registrar falha do trabalho já iniciado e liberar recursos. |

Um teste com entrega real deve usar número e unidade de homologação. Não iniciar
o worker de produção como forma de descobrir se a migração ou o sender funcionam.

## Preparar e ativar na VM

O deploy anterior só alterava o painel. **Este deploy é diferente:** acrescenta
tabelas, altera o processamento do flow e introduz um quarto serviço. Os workers
de webhook/Gunicorn não são o novo worker de follow-up.

Depois de publicar no Git a implementação revisada e homologada, a sequência é:

1. Manter o follow-up desligado. Se a unit já estiver instalada, pará-la antes de
   qualquer nova atualização. Interromper o `chatbot-worker-flow.service` para que
   o processo seja substituído integralmente depois da atualização.
2. Conferir checkout limpo e atualizar `prod` por fast-forward. Comparar o hash da
   VM com o hash da nova versão aprovada, não com o hash-base deste documento.
3. Aplicar uma única vez o arquivo completo `deploy/migrations/followup_registros.sql`
   no banco da aplicação, com a role usada para criar suas tabelas. Não executar
   o setup de instalação limpa sobre o RDS e não usar `makemigrations` para esses recibos.
   Conferir a contagem `conversas_ativas_marcadas` e a auditoria. Todas as ativas
   entram em stage 1; não existe corte de data configurável nem encerramento em massa.
   O script recusa ativas terminais/inconsistentes; resolver a recuperação pendente
   do flow antes de migrar novamente. Reaplicações após sucesso são recusadas.
4. Instalar a unit nova e recarregar a configuração do systemd, sem iniciá-la.
5. Carregar o ambiente atual e executar o diagnóstico somente leitura. Conferir
   acesso às tabelas novas com a role da aplicação e revisar eventuais anomalias.
6. Iniciar o flow atualizado, conferir estado e logs e comprovar sua operação.
7. Só então habilitar e iniciar o novo worker; acompanhar os primeiros ciclos.

Comandos de referência, executados na etapa correspondente, não como um bloco
automático que pule as verificações:

```bash
sudo systemctl stop chatbot-worker-flow.service
cd /opt/chatbot/app
git status --short
git fetch origin
git checkout prod
git pull --ff-only origin prod
git rev-parse HEAD
```

Depois da migração SQL confirmada:

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/chatbot-worker-followup.service /etc/systemd/system/chatbot-worker-followup.service
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/chatbot-worker-followup.service
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python -m utilitarios.verificar_followup'
```

Uma amostra sem candidatas é válida. `FOLLOWUP_CONSULTA_OK_SEM_ENVIO` confirma a
consulta, não um envio ou uma entrega da Meta. Revisar stages negativos, datas
futuras e recibos inconsistentes antes da ativação; não corrigir com reset em massa.

Depois de validar o diagnóstico:

```bash
sudo systemctl start chatbot-worker-flow.service
systemctl is-active chatbot-worker-flow.service
sudo journalctl -u chatbot-worker-flow.service --since '5 minutes ago' -n 80 --no-pager
```

Depois de confirmar que o flow compatível está funcionando:

```bash
sudo systemctl enable --now chatbot-worker-followup.service
sudo systemctl show chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service chatbot-worker-followup.service -p Id -p ActiveState -p SubState -p NRestarts --no-pager
sudo journalctl -u chatbot-worker-followup.service --since '5 minutes ago' -n 80 --no-pager
```

Não é necessário alterar os assets do painel, executar `collectstatic`, renovar
certificados ou criar outro domínio por causa deste plano. A ativação do serviço
é a ação que habilita os envios reais; instalar seu arquivo apenas prepara o systemd.

## Desligamento e rollback operacional

Para interromper novos lembretes mantendo a capacidade de atender quem já recebeu um:

```bash
sudo systemctl disable --now chatbot-worker-followup.service
systemctl is-active chatbot-worker-followup.service
```

O resultado esperado do último comando é `inactive` (e seu código de saída pode
ser diferente de zero por esse motivo). **Manter o flow compatível em execução.**
Não remover tabelas/recibos, não zerar stages e não restaurar automaticamente um
flow antigo que desconhece a reação de follow-up.

Uma reversão integral de código só pode ser planejada após revisar ciclos positivos,
retomadas abertas e filas em andamento, para que ninguém perca a regra de retorno.
Parar o proativo é o rollback operacional desta primeira entrega. O schema aditivo
permanece; não há SQL inverso destrutivo nem limpeza de histórico neste plano.

# Manifesto de integridade dos arquivos

Hashes SHA-256 calculados sobre UTF-8 com finais de linha LF. `sha256_base_lf = null`
significa arquivo novo. O hash proposto corresponde ao bloco integral do respectivo
passo, incluindo a quebra de linha final. Este manifesto não inclui credenciais,
arquivos temporários de validação ou o `VERSIONAMENTO.txt` local.

```json
{
  "base_commit": "84735aeaa521cfcf3a8bb13b2a8eddeb126fa1df",
  "arquivos": [
    {
      "passo": 1,
      "arquivo": "core/database/connection_aws.py",
      "acao": "alterar",
      "sha256_base_lf": "ce3e17ce25a02869a59df64e9d9b0a4ec42fc49915d96179b5eab42ee434ba32",
      "sha256_proposto_lf": "1802c27ec9f79138b891399973fe419ac4ae258c0e0614a058db2dbcf2803cc3"
    },
    {
      "passo": 2,
      "arquivo": "core/database/deploy_database/followup_script.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "c3d20f5aee77419e746dbf3d5e46a18ed6f3229b0562257f00122d0aa6c93b14"
    },
    {
      "passo": 3,
      "arquivo": "core/database/deploy_database/bank_script.py",
      "acao": "alterar",
      "sha256_base_lf": "972c6988fd1d049becd71965e48520c4cb494dacd01e57a3cb08072cb16740a0",
      "sha256_proposto_lf": "8b36d09fc704b9a2c63a70344462d0d7c6496c93d04e2c6c1b6c1dcc0c6afb8c"
    },
    {
      "passo": 4,
      "arquivo": "deploy/migrations/followup_registros.sql",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "801d9a81a2d3499979b2cd09ef6b871992a1920d6a2d26d095351d2d49a90370"
    },
    {
      "passo": 5,
      "arquivo": "core/repositories/atendimento/followup.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "e7dfbc1ea8c96032a280eefd55fa513803ef86e5b750849062d17da9f9730fd3"
    },
    {
      "passo": 6,
      "arquivo": "core/integrations/whatsapp/messages/followup_messages.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "88bb708dc04fc635c06f82908165dec8d3892a31c041125a17be47e10f2d5fe4"
    },
    {
      "passo": 7,
      "arquivo": "core/integrations/whatsapp/pywa_functions/cliente.py",
      "acao": "alterar",
      "sha256_base_lf": "694da243a08f26c5686d4537c12f1a006dfde1100e5e35cc7882a33578809269",
      "sha256_proposto_lf": "56c1cd11dfbb6785ac03301fa422dce2b7ed8dcc34a9236265e0bbac7cf0f894"
    },
    {
      "passo": 8,
      "arquivo": "core/integrations/whatsapp/pywa_functions/pywa_senders/followup.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "ef5500f35480a6755417075b4cb39b5e2a9be528ae78a425d566901824329a08"
    },
    {
      "passo": 9,
      "arquivo": "workers/worker_followup/__init__.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "5d3e9cb1f65a41537956792bd7bf4bf229875d2212d1b13b47f8fb42e4c92de7"
    },
    {
      "passo": 10,
      "arquivo": "workers/worker_followup/config.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "1cc7d9bb841f542652f3471ab2c2c80f2b67da3f6adcff4a836f56c74c2bf3b9"
    },
    {
      "passo": 11,
      "arquivo": "workers/worker_followup/followup_worker.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "fedbc5e239f9b3afa3cd675125b15dec9c33aaec88af8d80754902d001fed4d3"
    },
    {
      "passo": 12,
      "arquivo": "workers/worker_followup/iniciar_worker_followup.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "ffa68cca11503d811ebc259374387ff415ac96efaa50ae52bdab707eac082190"
    },
    {
      "passo": 13,
      "arquivo": "deploy/systemd/chatbot-worker-followup.service",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "e63a2ebfdfdec7c208366199143717616d33baaac621cf50cca6decf61ec6a60"
    },
    {
      "passo": 14,
      "arquivo": "workers/worker_flow/response_flow/repeticao_followup.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "1d0e0784fd5787061aed618f50077c0fc25891a2f1ff3a5466b06d124da4474b"
    },
    {
      "passo": 15,
      "arquivo": "workers/worker_flow/transacoes/retorno_followup.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "1306f0c40f889dba132a85e1912dc8a6a15c261235d6d3402dc05a6677b3a1cc"
    },
    {
      "passo": 16,
      "arquivo": "workers/worker_flow/response_flow/flow_worker.py",
      "acao": "alterar",
      "sha256_base_lf": "0c5f114efdd1ee4308d42f6db82fa32dc9e3bd583d185710e8151efbfc248b1d",
      "sha256_proposto_lf": "764470f990164fdb3b4d2940295b026b68a43b1ff63b74a9fe2b0d6c4cd0d721"
    },
    {
      "passo": 17,
      "arquivo": "tests/unit/test_worker_flow_runtime.py",
      "acao": "alterar",
      "sha256_base_lf": "21f87b1488d6483622fe28e4a11f98639d40e069bbb095351118d1677d3c7044",
      "sha256_proposto_lf": "23ae78a57dc0688eefe584cda8ae6672d4bbfb843ed1acccf3a630c9d582ece0"
    },
    {
      "passo": 18,
      "arquivo": "tests/unit/test_followup.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "cdb3a0eb108c60c11813f478974f267c5c233c5ed09385ffce73d7f5761930a5"
    },
    {
      "passo": 19,
      "arquivo": "tests/integration/__init__.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "c1cddc5ca94ac9c148a4c284bf0c105c8ea547ba2febc982740cf576357e2594"
    },
    {
      "passo": 20,
      "arquivo": "tests/integration/test_followup_postgres.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "c8d26c88047da493d2b71b8f1690b50036da6ca7877db86e8fee9dd2c3b68d30"
    },
    {
      "passo": 21,
      "arquivo": "utilitarios/verificar_followup.py",
      "acao": "criar",
      "sha256_base_lf": null,
      "sha256_proposto_lf": "765b5a5a776421a76b3b67a222964480e61ba31e1b6e99ac0536f8f905ae75b5"
    },
    {
      "passo": 22,
      "arquivo": "REGRAS_DE_NEGOCIO.md",
      "acao": "alterar",
      "sha256_base_lf": "64f457197d7eb0bcdd463dff378b49ecacea4ce1b77d2b4ec267d55f5cdb82ab",
      "sha256_proposto_lf": "fa9c868ed5a9ea540b31b8ded0059daa1ce131c8503edc427aeba5a61948bf09"
    },
    {
      "passo": 23,
      "arquivo": "workers/README.md",
      "acao": "alterar",
      "sha256_base_lf": "17d33ac8e0e7d462caa5fa2d2b31c8f9877675684e083eea703570efeb447891",
      "sha256_proposto_lf": "066f764559f48de8725b4e2ef69028b7e4f780a91ee47089227400ad38f83427"
    },
    {
      "passo": 24,
      "arquivo": "core/repositories/README.md",
      "acao": "alterar",
      "sha256_base_lf": "209d22bfc68de5436244da6824093b8e0d0896049e4a0405d59fd3ad10ca22e2",
      "sha256_proposto_lf": "3e81d93222412721796f090585a38f3201adb510f9588a6a9d701408a79ccbd3"
    },
    {
      "passo": 25,
      "arquivo": "core/integrations/whatsapp/README.md",
      "acao": "alterar",
      "sha256_base_lf": "5c69b72b4d172fb53b4d6144d04b4f69363e007e3507c282e5349edda78c4c02",
      "sha256_proposto_lf": "1afd6efacf0b40926def8a95b4c9833a2d62410985b549016212b1465f3cda28"
    },
    {
      "passo": 26,
      "arquivo": "tests/README.md",
      "acao": "alterar",
      "sha256_base_lf": "7a782e5b114ad5dc51e8390750395914eb57423619ab81f68e0117c55f8ec5c9",
      "sha256_proposto_lf": "68607bb0a2e94aa29c0111c21465cfbaecf61fa2fef72766425961e48069300f"
    },
    {
      "passo": 27,
      "arquivo": "deploy/README.md",
      "acao": "alterar",
      "sha256_base_lf": "03c9d71ac59c2b469c85190fed83ce26c2b03c2dc5c4560c0d86e1547f1914ff",
      "sha256_proposto_lf": "96ea244d2ce0c29e3bab19fdfcde27225cc45f9cf8a803622538dc4f310df4e0"
    }
  ]
}
```
