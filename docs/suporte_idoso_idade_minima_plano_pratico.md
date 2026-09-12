# Plano prático — suporte por idade mínima e encaminhamentos ao comercial

Documento irmão do [plano teórico](suporte_idoso_idade_minima_plano_teorico.md).

**Base:** V1.2.0, commit `ec74d26398724e192f798397d71b189ed08c805c`, mais o estado
local da documentação conferido na preparação. **Preparado em:** 11/09/2026.
**Status:** plano para implementação e homologação; não aplicado ao runtime,
ao banco ou à VM. Este documento não atribui um número à próxima versão.

São **38 arquivos completos**, um por passo, distribuídos em seis partes.
Os blocos incluem o conteúdo que já existia nos arquivos alterados: substituir
apenas trechos não é necessário. A preparação e os testes ocorreram numa cópia
temporária isolada; somente este plano foi criado no projeto principal.

## Contrato consolidado

- `idade_minima_suporte`: NULL (desativado), 50, 60, 70, 80 ou 90; nenhuma outra opção.
- A nova política atende apenas o titular e é decidida na etapa 6. O limite é
  inclusivo; o encaminhamento salva a idade e encerra a conversa na mesma etapa,
  com `encaminhado_suporte_idoso`, sem bloqueio de dias ou envio ao Funil.
- Pessoas de 100+ mantêm o tratamento atual para titular ou dependente, mesmo
  com suporte desativado. Menores e idade mínima do dependente conservam suas regras.
- E-mail do titular 60+ continua opcional; demais casos continuam seguindo
  `email_obrigatorio`. O limite de suporte não participa dessa decisão.
- Tags 18–59, 60+ e de dependentes permanecem fixas. A alteração de tags foi descartada.
- O card **Encaminhados ao comercial** aparece somente em Relatórios, abaixo
  dos quatro indicadores e antes de Evolução da demanda. Conta clientes únicos
  da unidade com encerramento por suporte de idade no período de `finalizou_em`.
  Inclui históricos, preserva o recorte semiaberto e não depende da idade ou
  configuração atuais, nem de mensagens recebidas naquele período.
- O card não inclui 100+, outros motivos, encerramentos pendentes ou envios
  falhos. Não comprova clique, atendimento humano, matrícula, venda ou Funil.
- As cinco faixas dos relatórios continuam fixas e conservam os envios reais
  ao Funil. O semanal e o total apresentam o limite como nota de política.
- Os quatro CSVs, inclusive os essenciais sem 55, permanecem iguais.
- Não há alteração de `.env`, systemd, mapa de etapas, follow-up, IA, tracker,
  novas tabelas de negócio ou planos futuros de `user_id`.

## Recuperação e fronteiras

O contexto da etapa 6 já é lido do banco também no retry por `valida_historico.py`.
Esse mecanismo fornece o limite atual; não será criado um snapshot da configuração.
O reconhecimento das cinco variantes oficiais identifica o tipo da resposta já
enviada, sem extrair do texto uma política anterior.

Se um envio ainda não tiver sido persistido, a nova avaliação usa o limite atual.
Se a resposta de suporte já existir, a barreira de idempotência impede novo envio.
Nesse caso, só reconstruir o encerramento de suporte se a idade ainda satisfizer
a política atual. Se não satisfizer ou estiver desativada, o retry não fecha por
essa política, não reescreve a resposta e não inventa avanço: a conversa permanece
na etapa 6 para uma próxima entrada normal. Não há tratamento especial de troca
de faixa ou preservação do limite antigo.

Histórico e idade continuam no checkpoint de persistência da resposta; encerramento
e conclusão da fila seguem o checkpoint do flow. Nenhum helper, sender ou repositório
ganha `commit()`/`rollback()`. A repetição após reação ao follow-up continua usando
seu caminho próprio, sem interpretar a reação como idade.

## Como aplicar este documento

1. Conferir o manifesto abaixo antes de substituir arquivos. Ele representa o
   estado local usado na preparação, não apenas o HEAD do Git. Se um arquivo tiver
   evoluído, reconciliar essa evolução antes de aplicar o conteúdo completo.
2. Materializar todos os passos, na ordem. **Criar os arquivos SQL não significa
   executar a migração.** Nenhum consumidor novo deve rodar contra o schema antigo.
3. Revisar o diff, executar testes e homologar o SQL no PostgreSQL descartável.
4. Publicar código e schema na janela descrita no último passo. Ele avisa o ponto
   exato para executar o SQL integral do passo 3 no DBeaver.
5. Atualizar o versionamento somente quando a entrega e o commit forem definidos.

Arquivos fora dos passos permanecem com seu conteúdo atual. Em especial, a
migração histórica de 29/08/2026 não é editada; banco novo usa o DDL final e banco
V1.2.0 recebe o SQL incremental. `total.py` reutiliza o semanal e não precisa de
um segundo conjunto de cálculos. Os senders e validadores de e-mail, o flow
principal e os módulos de follow-up permanecem intactos.

## Verificação feita durante a preparação

- A suíte completa na cópia isolada passou: 217 testes descobertos, 202 executados
  e 15 pulados por dependerem de PostgreSQL explícito. Após acrescentar os dois
  cenários de reversão, a rodada focada passou com 10 testes executados e os sete
  cenários SQL de suporte pulados. Esses cenários permanecem no passo de integração.
- A contagem real foi exercitada em SQLite em memória, adaptando somente os
  placeholders. Cobre duplicação, unidade, início inclusivo/fim exclusivo, históricos,
  conversa posterior, outros motivos, NULL, status ativo e zero real.
- Código Python proposto passou pela análise de sintaxe e o JavaScript pelo
  `node --check`.
- O painel proposto foi carregado em Chrome isolado, com template e estáticos
  reais e respostas de API fictícias, em 1366×900, 390×844, 844×390 e 320×568.
  O novo card exibiu o total correto, sem erros JavaScript ou largura excedente.
- **Migração e reversão ainda exigem execução em PostgreSQL descartável antes do
  deploy.** Não foram executadas contra banco local, RDS ou produção nesta preparação.
  O plano fornece os testes e os comandos; testes pulados não equivalem a homologação.

## Manifesto e índice dos passos

SHA-256 calculado sobre texto UTF-8 com quebras normalizadas para LF. O hash de
origem protege alterações locais; o hash final permite conferir o arquivo extraído
do bloco. `Novo` significa que o arquivo ainda não existia na preparação.

| Passo | Arquivo | Ação | SHA-256 de origem | SHA-256 final |
|---|---|---|---|---|
| 1 | `core/validacoes/suporte_por_idade.py` | Criar | `Novo` | `aca8d4608e265690cac25475b546b87cbd902debc845af482516f40b29bb02ed` |
| 2 | `core/database/deploy_database/bank_script.py` | Alterar | `8b36d09fc704b9a2c63a70344462d0d7c6496c93d04e2c6c1b6c1dcc0c6afb8c` | `eb4f5f87ef6863fc8e6275425e8b2783767f3050eb9e8b299be81b3cc0c0e027` |
| 3 | `deploy/migrations/20260911_idade_minima_suporte.sql` | Criar | `Novo` | `f1164aabf6bc171c2459164397f8cc73ad3fffbe32db40f219104b3a5e89fc34` |
| 4 | `deploy/rollback/20260911_idade_minima_suporte.sql` | Criar | `Novo` | `04c117de4513cf8b30c0655d8638b1722a3c04413e469a4b06e9d241155ed5fe` |
| 5 | `callback/webhook/models.py` | Alterar | `7fa11fc4e76324e997984324fb8abdadb1f980e855d25a8b0b001d3770b38195` | `5e2f77be77792a021216f1a3b6f416d67fc7409de18a432112e74fab39396f69` |
| 6 | `callback/webhook/admin.py` | Alterar | `9bfba26478e682c3e0855ecf4df4a22de27f311de5c86f48032dda2db3ade7f2` | `2d6b5ebd9e43194c0ad7cdeec4d0794f4ddc00baf386965234f34ae78b8eda76` |
| 7 | `core/repositories/fluxo/contextos/etapa6.py` | Alterar | `85f792bb39bf7c265f176dea928c35a4e35525a3c493aeb0ac64107832baf926` | `fb765fdfe9026340db696ffdbf5a3e2a00f3e30ff2edfad7f21d5d2260fafcf2` |
| 8 | `core/integrations/whatsapp/messages/etapa6_messages.py` | Alterar | `dfb189f3719cb5115f4f237e9b82d337287ea8eb4ec972356329bce907ba2a82` | `a8b99a1e3a365f4bdac8b414b0096548ba06de43a5b15be456830fd1ab6f066d` |
| 9 | `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa6.py` | Alterar | `fb3040598cc43ca5f21e3a263178f93ad20ee6e308a4f0e3b609b7922c4912cf` | `ae771839f7a2c499f250345882b5adb9dfadec7e49c262fba28f1ac76b591e08` |
| 10 | `workers/worker_flow/response_flow/etapas/resolver_etapa6.py` | Alterar | `59ed8eab59a2f0991a30fa4b574ad01c82c69eb56ebc4933ae057c5e37b60eba` | `065bd9b13053cd06fbb99e29a86153fccf6e25893e933bbddf7296af64f0c582` |
| 11 | `workers/worker_flow/transacoes/efeitos_transicao.py` | Alterar | `05d78551fde5f7963a8f99b47bfb07543b944c4ba4697609db53595bddad8ecd` | `e8684d7c365d06411a3538ba4fb094c26ac9181332586acbafbf0d4f88209f09` |
| 12 | `workers/worker_flow/transacoes/encerramento_atendimento.py` | Alterar | `56b70caccb06afe853809fac7692c0f69a4e75f47671386b444ad585f7e0f8ac` | `0ebad71eacc14176d454c1a8b5cdfea225eedb9823c1773a771c411941eac326` |
| 13 | `core/repositories/monitoramento/painel.py` | Alterar | `650ce5c51a99fed5c613becec4a95fd98fcdba874f457d4c31d264eaa2c1f968` | `ab3efc350941a65bf144be5d728c5d0cd0d4b434f96998a3d952d6a20d9c077f` |
| 14 | `callback/monitoramento/services.py` | Alterar | `e2df5b27a777b408a45447c4706ac3710a7a2e59726867cd0c27ace6f562f40d` | `77349fb1c4b20cc589362dfe4c77809f53fa3dd946043eba27372899e12dd1b8` |
| 15 | `callback/monitoramento/apresentacao.py` | Alterar | `7708c482561e90e79bbab9e7d2a6623b41e23172bb6d81d1f3c9578627f2a527` | `239ca39835fd01d1a9f5df077cf010a3ae4765d25cc42c95e97633d14202397e` |
| 16 | `callback/monitoramento/static/monitoramento/js/painel.js` | Alterar | `44569d0d786c07d672907e454ca61fe060ea4ad645b840fc2eda16b098abb801` | `ce5ad75e68d39811c982918a9af2af0ff1e2bfea2148e372ce56094cf2c544d9` |
| 17 | `callback/monitoramento/static/monitoramento/css/painel.css` | Alterar | `da5b61e72a58710a75020b410d105497adc5ad4ed94d8d825b404b221ffc043d` | `57df0f0d7468b65a8c57d07856d335c2dbf7215487e5d2bb0edf780d07e80d2e` |
| 18 | `callback/monitoramento/templates/monitoramento/painel.html` | Alterar | `11723274f59a9b66b0e701c1d3475f14d3252b2763f0e3adfcf9d8dfad63ec37` | `106b47181e00463d5f9ef0e12dc0780901b7d914ebda07e9bb84ddcb4722b709` |
| 19 | `utilitarios/reports_functions/weekly.py` | Alterar | `b1be42b2249dce3212216e2095ec0d3c8fe57a2986f3e00d1701fc0dde5919f4` | `29a36d4d573a1addc688cf80deb0f28626eead6b404cc7478008f14d40e5969d` |
| 20 | `tests/fixtures/monitoramento_painel.py` | Alterar | `43858b75bfc8e21b346a61caaf73f2461c282f066e32b901686ddff011ff2191` | `a96d89e4a384cd2e7feff5b4383eb2b1b69e33b73dc8297affb7ef07617d50fe` |
| 21 | `tests/unit/test_suporte_idoso_email_obrigatorio.py` | Alterar | `b21fd86896b713177c0a8e4f5db09bc4835a3134b5390781f3553f3ad48aac4f` | `c7cf897e45457185be7556a5ab8b3942c8ebc11e20b45b99504040cf75cc4f8f` |
| 22 | `tests/unit/test_monitoramento_painel.py` | Alterar | `2a47fa9feef7fda0705aee290e6fd13cee6b66f8c2630fd7ed38f4fada220cd3` | `c292d2005a02d02039e542bfb799cdfdd24c27fc4cce3d80d06bc4612eaca6d5` |
| 23 | `tests/unit/test_metricas_perfis_relatorios.py` | Alterar | `bdbabee963d339873c14e4beee4a1a36c8421422352e5df6856252bf4621bb5f` | `7586b9fb573467d166fa588f5f47c22f17c0036c28d2a63bbcc6b35d3c5aced6` |
| 24 | `tests/unit/test_gerar_monitoramento_unidades.py` | Alterar | `72422bcdd0da716647d62fc1c94d863a0543e42de640d6504284d3cc8090a678` | `a5db6695464688658c33f7e47098bc6d9f9e540d335f7de32ec99c76f04bd98f` |
| 25 | `tests/unit/test_suporte_por_idade.py` | Criar | `Novo` | `457a563f3be805f751184b260541ad7aa11f0cc7687a0c4b5fedda755066709a` |
| 26 | `tests/integration/test_suporte_por_idade_postgres.py` | Criar | `Novo` | `1a67fc55851c62100ba8e9cbaa559d7700951d3de1d4ae03f07aac2c8df1e181` |
| 27 | `REGRAS_DE_NEGOCIO.md` | Alterar | `187ccf1e7885f553772392c530153f62852dc30e5ed64622ea4794118698b19b` | `91496dbe30ac0c0391ad4dcefe13425716f54dd6470c429837142aff4e240fcd` |
| 28 | `PADROES_DE_ARQUITETURA.md` | Alterar | `b0f6f4415d1e9485aa8d135f310ae149734721e2e796b7ae77800bc34fac0901` | `6b3733f9bfd9e1db8d6e2e78e6745658a50d5cb26770297212245eb714c61d81` |
| 29 | `core/README.md` | Alterar | `e2c54f7c7dbc3e43a0eb3bd70190dbf7b0acf39d5a1a9977d2aee7a198340fe7` | `2a0e062de26ad1a1184217a7c8c33cf38c3d1b6651d6942aca9384309bb9c426` |
| 30 | `core/database/README.md` | Alterar | `7b0e22ff0a152f8df514ac2ec6917e5ff123c5d6925dab64f238f57a8e608c25` | `eb42ae6e7ebf0c9fcca002037c17567a054687fa7a6d86afd2ea7cd63fbe4eba` |
| 31 | `core/repositories/README.md` | Alterar | `5df7e63f22eaa003befaea692395cb7a04635ab185dc62eed3948e3f7f8cc9b4` | `ebad86fe709e406303ccbe7ce9f7dd9faf69fd367340151322ff3013239e386d` |
| 32 | `core/integrations/whatsapp/README.md` | Alterar | `4689ed80284e6c49d1194965c0414268ed1cffce3d604111fd058c929c250986` | `e9fc304c9ea6d5ee6dff5a47221476a5dd27c3cea53b778714a76267600984e9` |
| 33 | `workers/README.md` | Alterar | `f9e4a75bc24a6f7da5016caebb8fb157a8224e95a3c2af23334f5928ced802f6` | `a586f419cb7f8207cba7fd562e5a3c72368b3a20d7e0b9f56890c4165f7bc655` |
| 34 | `callback/README.md` | Alterar | `a3a7647985d05ddc230a182e5f23551ea4163cceb149db2239a34515679ac44c` | `c9ee7ee5f367a011178292e41d13b2f7abaa6b58618cf89ebb3de2203d229f80` |
| 35 | `utilitarios/README.md` | Alterar | `601d8b8aa59738b5005308a19d507b45ecc079e6950d5d63b6f9bc266a3ccadc` | `a982e0cfc817c0784e33b4329e0beccc92f4579d3244cd937808767e3a154d86` |
| 36 | `tests/README.md` | Alterar | `b12044c437fd38d94f6d527e73a8f74220aafd1180cb834ba1a8aa38fd9d0583` | `55a424c09bb2e6ff46abb8c742b7f11b11877b1ff697a56ee5e3c3db9df198b5` |
| 37 | `deploy/README.md` | Alterar | `f172b5f18e4f6e31420af7118780a81bd0b349445ce2f09b48b03df2296b6ee7` | `fbee0209124eb97f1bdc6f367d2bb0ed9867539bc7964e402987bc8441aaa688` |
| 38 | `deploy/idade_minima_suporte.md` | Criar | `Novo` | `ac19509b954af9695a41d9f78be6137cc535eb3047c35268fe6cd0e21d1da61a` |

## Parte 1 — domínio, schema e configuração

### Passo 1 — `core/validacoes/suporte_por_idade.py`

**Ação:** Criar. Centralizar somente os seis valores e a validação pura; booleanos não são idades.

Conteúdo completo do arquivo:

```python
"""Domínio puro da configuração de encaminhamento por idade da unidade."""

IDADES_MINIMAS_SUPORTE = (50, 60, 70, 80, 90)


def validar_idade_minima_suporte(valor):
    """None desativa; booleanos e números fora do domínio são erros."""
    if valor is not None and (
        type(valor) is not int or valor not in IDADES_MINIMAS_SUPORTE
    ):
        raise ValueError(f"Idade mínima de suporte inválida: {valor!r}")
    return valor
```

### Passo 2 — `core/database/deploy_database/bank_script.py`

**Ação:** Alterar. Atualizar a instalação limpa, preservando todo o restante do DDL e os registros de follow-up.

Conteúdo completo do arquivo:

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
            idade_minima_suporte INTEGER DEFAULT NULL
                CONSTRAINT ck_unidade_idade_minima_suporte CHECK (
                    idade_minima_suporte IS NULL
                    OR idade_minima_suporte IN (50, 60, 70, 80, 90)
                ),
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

### Passo 3 — `deploy/migrations/20260911_idade_minima_suporte.sql`

**Ação:** Criar. Disponibilizar o SQL integral para DBeaver. Criar o arquivo agora; executar somente na janela definida no procedimento.

Conteúdo completo do arquivo:

```sql
-- Executar o arquivo inteiro, com consumidores parados e backup validado.
-- Banco V1.2.0: TRUE -> 60; FALSE -> NULL. Não executar em instalação nova.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $precondicoes$
BEGIN
    IF to_regclass('chatbot.unidade') IS NULL THEN
        RAISE EXCEPTION 'Tabela chatbot.unidade ausente';
    END IF;
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'chatbot' AND table_name = 'unidade'
           AND column_name = 'idade_minima_suporte'
    ) THEN
        RAISE EXCEPTION 'Migração já aplicada ou schema parcial: idade_minima_suporte já existe';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'chatbot' AND table_name = 'unidade'
           AND column_name = 'suporte_idoso' AND data_type = 'boolean'
           AND is_nullable = 'NO' AND column_default = 'false'
    ) THEN
        RAISE EXCEPTION 'Esperado suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE da V1.2.0';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'chatbot.unidade'::regclass
           AND conname = 'ck_unidade_idade_minima_suporte'
    ) THEN
        RAISE EXCEPTION 'Restrição de destino já existe; revisar schema parcial';
    END IF;
END;
$precondicoes$;

LOCK TABLE chatbot.unidade IN ACCESS EXCLUSIVE MODE;

-- Fotografia temporária apenas para provar a conversão; eliminada no commit.
CREATE TEMP TABLE suporte_idade_antes ON COMMIT DROP AS
SELECT u.id_unidade, u.suporte_idoso,
       to_jsonb(u) - 'suporte_idoso' AS outros_campos
  FROM chatbot.unidade u;

SELECT COUNT(*) AS unidades_antes,
       COUNT(*) FILTER (WHERE suporte_idoso) AS habilitadas_antes,
       COUNT(*) FILTER (WHERE NOT suporte_idoso) AS desativadas_antes
  FROM suporte_idade_antes;

ALTER TABLE chatbot.unidade
    ALTER COLUMN suporte_idoso DROP DEFAULT,
    ALTER COLUMN suporte_idoso DROP NOT NULL;

ALTER TABLE chatbot.unidade
    ALTER COLUMN suporte_idoso TYPE INTEGER
    USING CASE WHEN suporte_idoso THEN 60 ELSE NULL END;

ALTER TABLE chatbot.unidade RENAME COLUMN suporte_idoso TO idade_minima_suporte;

ALTER TABLE chatbot.unidade
    ALTER COLUMN idade_minima_suporte SET DEFAULT NULL,
    ADD CONSTRAINT ck_unidade_idade_minima_suporte CHECK (
        idade_minima_suporte IS NULL
        OR idade_minima_suporte IN (50, 60, 70, 80, 90)
    );

DO $poscondicoes$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'chatbot' AND table_name = 'unidade'
           AND column_name = 'idade_minima_suporte'
           AND data_type = 'integer' AND is_nullable = 'YES'
           AND (column_default IS NULL OR column_default = 'NULL::integer')
    ) OR EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema = 'chatbot' AND table_name = 'unidade'
           AND column_name = 'suporte_idoso'
    ) THEN
        RAISE EXCEPTION 'Contrato final da coluna incorreto';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
         WHERE conrelid = 'chatbot.unidade'::regclass
           AND conname = 'ck_unidade_idade_minima_suporte'
           AND contype = 'c' AND convalidated
    ) THEN
        RAISE EXCEPTION 'Domínio final não está validado';
    END IF;
    IF EXISTS (
        SELECT 1 FROM suporte_idade_antes a
        FULL JOIN chatbot.unidade u USING (id_unidade)
         WHERE a.id_unidade IS NULL OR u.id_unidade IS NULL
            OR u.idade_minima_suporte IS DISTINCT FROM
               CASE WHEN a.suporte_idoso THEN 60 ELSE NULL END
            OR (to_jsonb(u) - 'idade_minima_suporte') IS DISTINCT FROM a.outros_campos
    ) THEN
        RAISE EXCEPTION 'Conversão não preservou configurações e demais dados das unidades';
    END IF;
END;
$poscondicoes$;

SELECT COUNT(*) AS unidades_depois,
       COUNT(*) FILTER (WHERE idade_minima_suporte = 60) AS habilitadas_60,
       COUNT(*) FILTER (WHERE idade_minima_suporte IS NULL) AS desativadas
  FROM chatbot.unidade;

COMMIT;
```

### Passo 4 — `deploy/rollback/20260911_idade_minima_suporte.sql`

**Ação:** Criar. Disponibilizar a reversão transacional restrita a NULL/60; faixas novas exigem decisão do responsável.

Conteúdo completo do arquivo:

```sql
-- Somente durante manutenção, antes de reiniciar código booleano.
-- Recusa faixas novas: 50/70/80/90 não são equivalentes ao suporte antigo.
BEGIN;
SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

DO $precondicoes$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema='chatbot' AND table_name='unidade'
           AND column_name='idade_minima_suporte' AND data_type='integer'
           AND is_nullable='YES'
    ) OR EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_schema='chatbot' AND table_name='unidade'
           AND column_name='suporte_idoso'
    ) THEN
        RAISE EXCEPTION 'Schema incompatível com esta reversão';
    END IF;
END;
$precondicoes$;

LOCK TABLE chatbot.unidade IN ACCESS EXCLUSIVE MODE;

DO $dominio$
BEGIN
    IF EXISTS (SELECT 1 FROM chatbot.unidade
                WHERE idade_minima_suporte IS NOT NULL AND idade_minima_suporte <> 60) THEN
        RAISE EXCEPTION 'Há faixas novas configuradas; não converter silenciosamente para 60+';
    END IF;
END;
$dominio$;

CREATE TEMP TABLE suporte_idade_rollback_antes ON COMMIT DROP AS
SELECT id_unidade, idade_minima_suporte, to_jsonb(u) - 'idade_minima_suporte' AS outros_campos
  FROM chatbot.unidade u;

ALTER TABLE chatbot.unidade
    DROP CONSTRAINT ck_unidade_idade_minima_suporte,
    ALTER COLUMN idade_minima_suporte DROP DEFAULT;
ALTER TABLE chatbot.unidade
    ALTER COLUMN idade_minima_suporte TYPE BOOLEAN
    USING (idade_minima_suporte IS NOT NULL);
ALTER TABLE chatbot.unidade RENAME COLUMN idade_minima_suporte TO suporte_idoso;
ALTER TABLE chatbot.unidade
    ALTER COLUMN suporte_idoso SET DEFAULT FALSE,
    ALTER COLUMN suporte_idoso SET NOT NULL;

DO $conferencia$
BEGIN
    IF EXISTS (
        SELECT 1 FROM suporte_idade_rollback_antes a
        FULL JOIN chatbot.unidade u USING (id_unidade)
         WHERE a.id_unidade IS NULL OR u.id_unidade IS NULL
            OR u.suporte_idoso IS DISTINCT FROM (a.idade_minima_suporte IS NOT NULL)
            OR (to_jsonb(u) - 'suporte_idoso') IS DISTINCT FROM a.outros_campos
    ) THEN
        RAISE EXCEPTION 'Reversão não preservou a configuração ou os demais campos';
    END IF;
END;
$conferencia$;

SELECT COUNT(*) AS unidades, COUNT(*) FILTER (WHERE suporte_idoso) AS habilitadas
  FROM chatbot.unidade;
COMMIT;
```

### Passo 5 — `callback/webhook/models.py`

**Ação:** Alterar. Substituir o BooleanField por IntegerField opcional com as seis escolhas, mantendo managed=False.

Conteúdo completo do arquivo:

```python
from core.validacoes.suporte_por_idade import IDADES_MINIMAS_SUPORTE

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Cliente(models.Model):
    id_cliente = models.AutoField(primary_key=True)
    nome = models.CharField(max_length=200, blank=True, null=True)
    waid_telefone = models.CharField(unique=True, max_length=50)
    email = models.CharField(unique=True, max_length=200, blank=True, null=True)
    idade = models.IntegerField(blank=True, null=True)
    profissao = models.CharField(max_length=100, blank=True, null=True)

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
    idade = models.IntegerField(blank=True, null=True)

    def __str__(self):
        return self.nome_dependente or str(self.id_dependente)

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
    profissao = models.CharField(max_length=100, blank=True, null=True)
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
    turnos_sem_avanco = models.IntegerField(default=0)
    iniciou_em = models.DateTimeField()
    finalizou_em = models.DateTimeField(blank=True, null=True)
    motivo_encerramento = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        choices=[
            ("idade_invalida", "Idade inválida"),
            ("foi_agendado", "Foi agendado"),
            (
                "encaminhado_suporte_idoso",
                "Encaminhado ao suporte ao idoso",
            ),
        ],
    )

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
    resposta = models.CharField(max_length=20)
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


class PesquisaSatisfacao(models.Model):
    id_pesquisa_satisfacao = models.AutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='pesquisa_satisfacao',
    )
    nota = models.PositiveSmallIntegerField(blank=True, null=True)
    comentario = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'pesquisa_satisfacao'
        verbose_name = 'Pesquisa de satisfação'
        verbose_name_plural = 'Pesquisas de satisfação'


class Unidade(models.Model):
    class Genero(models.TextChoices):
        MASCULINO = "masculino", "Masculino"
        FEMININO = "feminino", "Feminino"

    id_unidade = models.AutoField(primary_key=True)
    nome_unidade = models.CharField(
        "nome da unidade",
        unique=True,
        max_length=300,
    )
    nome_agente = models.CharField("nome do agente", max_length=100)
    genero = models.CharField(
        "gênero do agente",
        max_length=9,
        choices=Genero.choices,
    )
    cnpj = models.CharField(unique=True, max_length=50)
    email_responsavel = models.CharField(unique=True, max_length=255)
    telefone = models.CharField(unique=True, max_length=20)
    numero_comercial = models.CharField(
        max_length=30,
        blank=True,
        null=True,
    )
    idade_minima_suporte = models.IntegerField(
        "encaminhar titular ao comercial a partir de",
        blank=True,
        null=True,
        default=None,
        choices=[(None, "Desativado")] + [
            (idade, f"{idade}+") for idade in IDADES_MINIMAS_SUPORTE
        ],
        help_text=(
            "Na etapa de idade, encaminha somente o titular a partir do limite "
            "até 99 anos e encerra sem bloqueio. Não altera a regra de e-mail."
        ),
    )
    email_obrigatorio = models.BooleanField(
        "e-mail obrigatório",
        default=True,
        help_text=(
            "Exige um e-mail válido, exceto do titular com 60 anos ou mais."
        ),
    )
    waba_id = models.CharField(
        unique=True,
        max_length=100,
    )
    phone_number_id = models.CharField(unique=True, max_length=100)
    link_agendamento = models.CharField(unique=True, max_length=400)
    link_instagram = models.CharField(
        max_length=400,
        blank=True,
        null=True,
    )
    bpa_ativo = models.BooleanField(default=False)
    status_pagamento = models.BooleanField(blank=True, null=True, default=True)
    id_usuario_monitoramento = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        models.SET_NULL,
        db_column='id_usuario_monitoramento',
        related_name='unidade_monitorada',
        verbose_name='usuário de monitoramento',
        blank=True,
        null=True,
        limit_choices_to={'is_staff': False, 'is_superuser': False},
        help_text=(
            'Selecione uma conta comum cadastrada em Usuários. '
            'Cada conta pode monitorar somente uma unidade. '
            'Deixe vazio para manter a unidade sem acesso de monitoramento.'
        ),
    )

    def clean(self):
        super().clean()
        if self.id_usuario_monitoramento_id and (
            self.id_usuario_monitoramento.is_staff
            or self.id_usuario_monitoramento.is_superuser
        ):
            raise ValidationError({
                'id_usuario_monitoramento': (
                    'O monitoramento exige uma conta sem acesso ao Admin '
                    'e sem status de superusuário.'
                ),
            })

    def __str__(self):
        return self.nome_unidade

    class Meta:
        managed = False
        db_table = 'unidade'


class IntegracaoFunilUnidade(models.Model):
    id_integracao_funil = models.AutoField(primary_key=True)
    id_unidade = models.OneToOneField(
        Unidade,
        models.CASCADE,
        db_column='id_unidade',
        related_name='integracao_funil',
    )
    nome_widget = models.CharField(max_length=300)
    data_salvamento_widget = models.DateField(blank=True, null=True)
    codigo_widget = models.CharField(unique=True, max_length=100)
    link_api_carrossel = models.URLField(unique=True, max_length=500)
    codigo_canal_venda = models.CharField(max_length=100)
    widget_ativo = models.BooleanField(default=True)
    integracao_ativa = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id_unidade} / {self.nome_widget}"

    class Meta:
        managed = False
        db_table = 'integracao_funil_unidade'
        verbose_name = 'Integração do Funil por unidade'
        verbose_name_plural = 'Integrações do Funil por unidade'


class FunilEnvio(models.Model):
    id_funil_envio = models.AutoField(primary_key=True)
    id_conversa = models.OneToOneField(
        Conversa,
        models.CASCADE,
        db_column='id_conversa',
        related_name='envio_funil',
    )
    status = models.CharField(
        max_length=20,
        default='pending',
        choices=[
            ('pending', 'pending'),
            ('processing', 'processing'),
            ('sent', 'sent'),
        ],
    )
    attempt_count = models.IntegerField(default=0)
    next_attempt_at = models.DateTimeField()
    processing_started_at = models.DateTimeField(blank=True, null=True)
    enviado_em = models.DateTimeField(blank=True, null=True)
    ultimo_erro = models.TextField(blank=True, null=True)
    resposta_funil = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField()
    atualizado_em = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'funil_envios'
        verbose_name = 'Envio ao Funil'
        verbose_name_plural = 'Envios ao Funil'


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
    nome = models.CharField(max_length=200, blank=True, null=True)
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

### Passo 6 — `callback/webhook/admin.py`

**Ação:** Alterar. Expor o seletor e exigir número comercial válido quando ativo, preservando validações Meta-first e cache.

Conteúdo completo do arquivo:

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
from core.integrations.whatsapp.tools.ativando_waba_id import ativar_waba_id
from core.integrations.whatsapp.tools.desativa_waba_id import desativar_waba_id
from core.integrations.whatsapp.tools.desativando_numero import desregistrar_numero_whatsapp
from core.integrations.whatsapp.tools.usuarios import (
    desbloquear_usuario_meta,
)
from core.integrations.whatsapp.tools.validando_phone_waba import (
    validar_phone_number_id_da_waba,
)
from core.integrations.whatsapp.numero_comercial import (
    numero_comercial_whatsapp_valido,
)
from core.logging_config import short_value
from core.repositories.unidades.cache_control import (
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
    FunilEnvio,
    HistoricoMensagens,
    IntegracaoFunilUnidade,
    PesquisaSatisfacao,
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


@admin.register(IntegracaoFunilUnidade)
class IntegracaoFunilUnidadeAdmin(admin.ModelAdmin):
    list_display = (
        "id_integracao_funil",
        "id_unidade",
        "nome_widget",
        "codigo_widget",
        "codigo_canal_venda",
        "widget_ativo",
        "integracao_ativa",
        "data_salvamento_widget",
        "atualizado_em",
    )

    search_fields = (
        "id_unidade__nome_unidade",
        "nome_widget",
        "codigo_widget",
        "codigo_canal_venda",
        "link_api_carrossel",
    )

    list_filter = (
        "widget_ativo",
        "integracao_ativa",
        "data_salvamento_widget",
    )

    readonly_fields = (
        "criado_em",
        "atualizado_em",
    )

    ordering = ("id_unidade",)
    list_select_related = ("id_unidade",)
    list_per_page = 50
    empty_value_display = "-"


@admin.register(FunilEnvio)
class FunilEnvioAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):
    list_display = (
        "id_funil_envio",
        "id_conversa",
        "status",
        "attempt_count",
        "next_attempt_at",
        "processing_started_at",
        "enviado_em",
        "atualizado_em",
    )
    search_fields = (
        "id_conversa__id_conversa",
        "id_conversa__id_cliente__nome",
        "id_conversa__id_cliente__waid_telefone",
    )
    list_filter = ("status",)
    ordering = ("-atualizado_em",)
    date_hierarchy = "criado_em"
    list_select_related = (
        "id_conversa",
        "id_conversa__id_cliente",
    )
    list_per_page = 50
    empty_value_display = "-"


@admin.register(Unidade)
class UnidadeAdmin(admin.ModelAdmin):

    list_display = (
        "id_unidade",
        "nome_unidade",
        "id_usuario_monitoramento",
        "nome_agente",
        "genero",
        "cnpj",
        "telefone",
        "numero_comercial",
        "idade_minima_suporte",
        "email_obrigatorio",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
        "link_agendamento_clickable",
        "link_instagram_clickable",
        "bpa_ativo",
        "status_pagamento",
    )

    search_fields = (
        "nome_unidade",
        "id_usuario_monitoramento__username",
        "nome_agente",
        "cnpj",
        "telefone",
        "numero_comercial",
        "email_responsavel",
        "waba_id",
        "phone_number_id",
        "link_agendamento",
        "link_instagram",
    )

    list_filter = (
        "genero",
        "bpa_ativo",
        "idade_minima_suporte",
        "email_obrigatorio",
        "status_pagamento",
    )
    ordering = ("nome_unidade",)
    list_select_related = ("id_usuario_monitoramento",)

    list_per_page = 50
    empty_value_display = "-"

    def get_readonly_fields(self, request, obj=None):
        if obj is not None:
            return ("waba_id", "phone_number_id")

        return ()

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

                if (
                    self.cleaned_data.get("idade_minima_suporte") is not None
                    and not numero_comercial_whatsapp_valido(
                        self.cleaned_data.get("numero_comercial")
                    )
                ):
                    self.add_error(
                        "numero_comercial",
                        "Informe um número comercial brasileiro válido "
                        "antes de ativar o encaminhamento por idade.",
                    )

                if change or self.errors:
                    if change and not self.errors:
                        model_admin._validar_cache_unidades_form(
                            self,
                            request,
                            meta_validada=False,
                        )
                    return

                waba_id = self.cleaned_data.get("waba_id")
                phone_number_id = self.cleaned_data.get("phone_number_id")

                if not waba_id:
                    self.add_error(
                        "waba_id",
                        "Informe a WABA que sera assinada pelo App.",
                    )
                    return

                campo_com_erro = model_admin._preparar_meta_antes_de_salvar(
                    request,
                    waba_id,
                    phone_number_id,
                )

                if campo_com_erro == "vinculo_waba_phone":
                    self.add_error(
                        "phone_number_id",
                        "Este phone ID nao pertence a WABA informada. "
                        "A unidade nao foi salva.",
                    )
                    return

                if campo_com_erro == "waba_id":
                    self.add_error(
                        "waba_id",
                        "A Meta falhou ao assinar esta WABA. Unidade nao foi salva.",
                    )
                    return

                if campo_com_erro == "phone_number_id":
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

    def link_instagram_clickable(self, obj):
        if obj.link_instagram:
            return format_html(
                '<a href="{}" target="_blank">Abrir</a>',
                obj.link_instagram,
            )
        return "-"

    link_instagram_clickable.short_description = "Instagram"

    def _preparar_meta_antes_de_salvar(
        self,
        request,
        waba_id,
        phone_number_id,
    ):
        if not self._validar_vinculo_phone_waba_antes_de_salvar(
            request,
            waba_id,
            phone_number_id,
        ):
            return "vinculo_waba_phone"

        if not self._ativar_waba_antes_de_salvar(request, waba_id):
            return "waba_id"

        if not self._registrar_meta_antes_de_salvar(
            request,
            phone_number_id,
        ):
            return "phone_number_id"

        return None

    def _validar_vinculo_phone_waba_antes_de_salvar(
        self,
        request,
        waba_id,
        phone_number_id,
    ):
        try:
            status, resposta = validar_phone_number_id_da_waba(
                waba_id,
                phone_number_id,
            )

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_phone_waba_vinculo_invalido | "
                    "acao=bloquear_save waba_id=%s phone_number_id=%s "
                    "status=%s motivo=%s",
                    short_value(waba_id),
                    short_value(phone_number_id),
                    status,
                    resposta.get("reason")
                    if isinstance(resposta, dict)
                    else None,
                )
                self.message_user(
                    request,
                    "A Meta nao confirmou que o phone ID pertence a "
                    "WABA informada. A unidade nao foi salva.",
                    level=messages.ERROR,
                )
                return False

            logger.info(
                "whatsapp_phone_waba_vinculo_ok | "
                "acao=permitir_ativacao waba_id=%s phone_number_id=%s",
                short_value(waba_id),
                short_value(phone_number_id),
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_phone_waba_validacao_erro | "
                "acao=bloquear_save waba_id=%s phone_number_id=%s "
                "erro=%s",
                short_value(waba_id),
                short_value(phone_number_id),
                exc,
            )
            self.message_user(
                request,
                "Erro ao validar WABA e phone ID na Meta. "
                f"A unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

    def _ativar_waba_antes_de_salvar(self, request, waba_id):
        try:
            status, resposta = ativar_waba_id(waba_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_waba_ativar_falhou | acao=bloquear_save "
                    "waba_id=%s status=%s resposta=%s",
                    short_value(waba_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "Erro ao assinar WABA no WhatsApp. "
                    f"Unidade nao foi salva: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="ativar_waba",
                waba_id=waba_id,
            )
            logger.info(
                "whatsapp_waba_ativada | acao=permitir_registro_numero "
                "waba_id=%s status=%s",
                short_value(waba_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_waba_ativar_erro | acao=bloquear_save "
                "waba_id=%s erro=%s",
                short_value(waba_id),
                exc,
            )
            self.message_user(
                request,
                "Erro inesperado ao assinar WABA. "
                f"Unidade nao foi salva: {exc}",
                level=messages.ERROR,
            )
            return False

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
                acao="registrar_numero",
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
        if not self._desassinar_waba_antes_de_excluir(request, obj):
            return False

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
                    "A WABA foi desassinada, mas a Meta falhou ao "
                    "desregistrar o numero. Unidade mantida no banco: "
                    f"{resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desregistrar_numero",
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
                "A WABA foi desassinada, mas ocorreu um erro ao "
                "desregistrar o numero. Unidade mantida no banco: "
                f"{exc}",
                level=messages.ERROR,
            )
            return False

    def _desassinar_waba_antes_de_excluir(self, request, obj):
        try:
            status, resposta = desativar_waba_id(obj.waba_id)

            if not self._meta_resposta_sucesso(status, resposta):
                logger.error(
                    "whatsapp_waba_desassinar_falhou | "
                    "acao=bloquear_delete waba_id=%s status=%s "
                    "resposta=%s",
                    short_value(obj.waba_id),
                    status,
                    resposta,
                )
                self.message_user(
                    request,
                    "Erro ao remover a assinatura da WABA na Meta. "
                    f"Unidade mantida no banco: {resposta}",
                    level=messages.ERROR,
                )
                return False

            self._marcar_meta_sucesso(
                request,
                acao="desativar_waba",
                waba_id=obj.waba_id,
            )
            logger.warning(
                "whatsapp_waba_desassinada | acao=continuar_delete "
                "waba_id=%s status=%s",
                short_value(obj.waba_id),
                status,
            )
            return True

        except Exception as exc:
            logger.exception(
                "whatsapp_waba_desassinar_erro | "
                "acao=bloquear_delete waba_id=%s erro=%s",
                short_value(obj.waba_id),
                exc,
            )
            self.message_user(
                request,
                "Erro inesperado ao remover a assinatura da WABA. "
                f"Unidade mantida no banco: {exc}",
                level=messages.ERROR,
            )
            return False

    def _marcar_meta_sucesso(
        self,
        request,
        acao,
        **identificadores,
    ):
        operacoes = list(
            getattr(request, "_unidade_meta_sucesso", [])
        )
        operacoes.append({
            "acao": acao,
            **{
                nome: str(valor)
                for nome, valor in identificadores.items()
            },
        })
        request._unidade_meta_sucesso = operacoes

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
                "cache de unidades no Redis não foram confirmados. Faça uma "
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
        "profissao",
    )

    search_fields = (
        "nome",
        "waid_telefone",
        "email",
        "profissao",
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
        "idade",
    )

    search_fields = (
        "nome_dependente",
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
        "profissao",
        "turnos_sem_avanco",
        "status_ativa",
        "motivo_encerramento",
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
        "profissao",
    )

    list_filter = (
        "status_ativa",
        "motivo_encerramento",
        "turnos_sem_avanco",
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


@admin.register(PesquisaSatisfacao)
class PesquisaSatisfacaoAdmin(SomenteVisualizacaoAdminMixin, admin.ModelAdmin):

    list_display = (
        "id_pesquisa_satisfacao",
        "id_conversa",
        "nota",
        "comentario",
        "criado_em",
        "atualizado_em",
    )

    search_fields = (
        "id_conversa__id_conversa",
        "id_conversa__id_cliente__nome",
        "comentario",
    )

    list_filter = ("nota",)
    ordering = ("-atualizado_em",)
    date_hierarchy = "atualizado_em"
    list_per_page = 50
    empty_value_display = "-"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            "id_conversa",
            "id_conversa__id_cliente",
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
        "nome",
        "wa_id_cliente",
        "id_unidade",
        "phone_id_unidade",
    )

    search_fields = (
        "nome",
        "wa_id_cliente",
        "phone_id_unidade",
        "id_cliente__waid_telefone",
        "id_cliente__nome",
        "id_unidade__nome_unidade",
    )

    list_filter = ("id_unidade",)
    ordering = ("wa_id_cliente", "id_unidade__nome_unidade")
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
        conversas_resetadas = Conversa.objects.filter(
            id_cliente_id=obj.id_cliente_id,
            id_unidade_id=obj.id_unidade_id,
            status_ativa=True,
        ).update(turnos_sem_avanco=0)

        logger.warning(
            "admin_bloqueio_meta_excluido | "
            "acao=resetar_contador_e_excluir_registro "
            "usuario=%s wa_id_cliente=%s phone_id_unidade=%s "
            "conversas_resetadas=%s",
            request.user,
            short_value(obj.wa_id_cliente),
            short_value(obj.phone_id_unidade),
            conversas_resetadas,
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

## Parte 2 — etapa 6, envio e recuperação

### Passo 7 — `core/repositories/fluxo/contextos/etapa6.py`

**Ação:** Alterar. Ler a configuração atual no PostgreSQL e publicá-la sem conversão booleana.

Conteúdo completo do arquivo:

```python
import logging

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


logger = logging.getLogger("db.contexto_etapa6")


def buscar_contexto_etapa6(id_conversa, id_unidade, cursor):
    cursor.execute(
        """
        SELECT
            u.numero_comercial,
            u.bpa_ativo,
            u.idade_minima_suporte,
            cl.nome,
            d.nome_dependente
        FROM chatbot.unidade u
        JOIN chatbot.conversa c
          ON c.id_conversa = %s
         AND c.id_unidade = u.id_unidade
        JOIN chatbot.cliente cl
          ON cl.id_cliente = c.id_cliente
        LEFT JOIN chatbot.dependente d
          ON d.id_conversa = c.id_conversa
        WHERE u.id_unidade = %s
        LIMIT 1;
        """,
        (id_conversa, id_unidade),
    )

    resultado = cursor.fetchone()

    if not resultado:
        raise ValueError(
            "Contexto da etapa 6 não encontrado "
            f"(id_conversa={id_conversa}, id_unidade={id_unidade})"
        )

    (
        numero_comercial,
        bpa_ativo,
        idade_minima_suporte,
        nome_cliente,
        nome_dependente,
    ) = resultado

    logger.debug(
        "contexto_etapa6_consultado | id_conversa=%s id_unidade=%s "
        "numero_comercial_configurado=%s bpa_ativo=%s idade_minima_suporte=%s "
        "cliente_nomeado=%s dependente_nomeado=%s",
        id_conversa,
        id_unidade,
        bool(numero_comercial),
        bool(bpa_ativo),
        idade_minima_suporte,
        bool(nome_cliente),
        bool(nome_dependente),
    )

    validar_idade_minima_suporte(idade_minima_suporte)

    return {
        "numero_comercial_unidade": numero_comercial,
        "bpa_ativo_unidade": bool(bpa_ativo),
        "idade_minima_suporte": idade_minima_suporte,
        "nome_cliente": nome_cliente,
        "nome_dependente": nome_dependente,
    }
```

### Passo 8 — `core/integrations/whatsapp/messages/etapa6_messages.py`

**Ação:** Alterar. Parametrizar a mensagem de suporte; com 60, o conteúdo permanece idêntico ao legado.

Conteúdo completo do arquivo:

```python
from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


from core.integrations.whatsapp.messages.tratamentos_universais import (
    montar_mensagem_tratamento_reforco_escolar,
)


### ENTRADA NA ETAPA 6 - CLIENTE

MENSAGEM_IDADE_ETAPA6 = (
    "Certo, agora me fala, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6():
    return MENSAGEM_IDADE_ETAPA6


### ENTRADA NA ETAPA 6 - DEPENDENTE

MENSAGEM_IDADE_DEPENDENTE_ETAPA6 = (
    "Certo, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM MÍDIA

MENSAGEM_IDADE_ETAPA6_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6_midia():
    return MENSAGEM_IDADE_ETAPA6_MIDIA


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MÍDIA

MENSAGEM_IDADE_DEPENDENTE_ETAPA6_MIDIA = (
    "Olha, ainda não reconhecemos mensagens com mídia, apenas texto.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6_midia(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6_MIDIA.format(nome=nome)


### CLIENTE RESPONDE À IDADE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_ETAPA6_FINANCEIRO = (
    "Olha, demais informações como valores de investimento são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_idade_etapa6_financeiro():
    return MENSAGEM_IDADE_ETAPA6_FINANCEIRO


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA

MENSAGEM_IDADE_DEPENDENTE_ETAPA6_FINANCEIRO = (
    "Olha, demais informações como valores de investimento são apresentadas no atendimento "
    "presencial após a aula *gratuita*.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_dependente_etapa6_financeiro(nome):
    return MENSAGEM_IDADE_DEPENDENTE_ETAPA6_FINANCEIRO.format(nome=nome)


### CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR

MENSAGEM_RETOMADA_IDADE_ETAPA6 = "Me diz, qual é a sua idade?"
MENSAGEM_RETOMADA_IDADE_DEPENDENTE_ETAPA6 = (
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_idade_etapa6_reforco_escolar():
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_IDADE_ETAPA6,
    )


def montar_mensagem_idade_dependente_etapa6_reforco_escolar(nome):
    return montar_mensagem_tratamento_reforco_escolar(
        MENSAGEM_RETOMADA_IDADE_DEPENDENTE_ETAPA6.format(nome=nome),
    )


### CLIENTE RESPONDE À IDADE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA6 = (
    "Não consegui entender a sua idade. Digite apenas o número, exemplo: 25.\n"
    "Me diz, qual é a sua idade?"
)


def montar_mensagem_contexto_idade_invalida_etapa6():
    return MENSAGEM_CONTEXTO_IDADE_INVALIDA_ETAPA6


### CLIENTE RESPONDE À IDADE DO DEPENDENTE COM MENSAGEM FORA DE CONTEXTO

MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA6 = (
    "Não consegui entender a idade de {nome}. Digite apenas o número, "
    "exemplo: 10.\n"
    "Me diz, qual é a idade de {nome}?"
)


def montar_mensagem_contexto_idade_dependente_invalida_etapa6(nome):
    return MENSAGEM_CONTEXTO_IDADE_DEPENDENTE_INVALIDA_ETAPA6.format(
        nome=nome,
    )


### CLIENTE COM MENOS DE 18 ANOS

MENSAGEM_CLIENTE_MENOR_18_ETAPA6 = (
    "Como você tem menos de 18 anos, este atendimento precisa ser realizado "
    "por um adulto responsável.\n\n"
    "Peça a um adulto para retornar nosso atendimento.\n"
    "Um abraço e até logo! 👋☺️"
)


def montar_mensagem_cliente_menor_18_etapa6():
    return MENSAGEM_CLIENTE_MENOR_18_ETAPA6


### DEPENDENTE ABAIXO DA IDADE MINIMA DA UNIDADE

MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6 = (
    "No momento, esta unidade do Supera realiza treinamentos com crianças a "
    "partir de {idade_minima} anos. Quando {nome} completar {idade_minima} "
    "anos, você poderá entrar em contato "
    "novamente.\n\n"
    "Um abraço e até logo! 👋☺️"

)


def montar_mensagem_dependente_menor_5_etapa6(
    nome,
    idade_minima=5,
):
    return MENSAGEM_DEPENDENTE_MENOR_5_ETAPA6.format(
        nome=nome,
        idade_minima=idade_minima,
    )


### CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS

MENSAGEM_IDADE_ACIMA_99_ETAPA6 = (
    "Entendi. Olha, para idades muito avançadas, é melhor falar com nossa "
    "consultora especializada. Vou te passar o contato dela para continuar "
    "o atendimento, tudo bem?\n\n"
    "Basta clicar no botão abaixo."
)

BOTAO_FALAR_COM_CONSULTORA_ETAPA6 = "Falar com Consultora"


def montar_mensagem_idade_acima_99_etapa6():
    return MENSAGEM_IDADE_ACIMA_99_ETAPA6


def montar_botao_idade_acima_99_etapa6():
    return BOTAO_FALAR_COM_CONSULTORA_ETAPA6


### TITULAR A PARTIR DO LIMITE CONFIGURADO ATÉ 99 ANOS

MENSAGEM_SUPORTE_IDOSO_ETAPA6 = (
    "Entendi. Para oferecer um atendimento mais adequado, esta unidade "
    "realiza o suporte a clientes com {idade_minima} anos ou mais diretamente com a "
    "nossa equipe comercial.\n\n"
    "Vou te passar o contato para continuar o atendimento. Basta clicar "
    "no botão abaixo."
)

BOTAO_SUPORTE_IDOSO_ETAPA6 = "Falar com Comercial"


def montar_mensagem_suporte_idoso_etapa6(idade_minima):
    validar_idade_minima_suporte(idade_minima)
    if idade_minima is None:
        raise ValueError("Não há mensagem de suporte para política desativada")
    return MENSAGEM_SUPORTE_IDOSO_ETAPA6.format(idade_minima=idade_minima)


def montar_botao_suporte_idoso_etapa6():
    return BOTAO_SUPORTE_IDOSO_ETAPA6
```

### Passo 9 — `core/integrations/whatsapp/pywa_functions/pywa_senders/etapa6.py`

**Ação:** Alterar. Receber o limite validado e enviar o texto oficial com o CTA existente para o número comercial.

Conteúdo completo do arquivo:

```python
import logging
from pywa.types import URLButton

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_botao_idade_acima_99_etapa6,
    montar_botao_suporte_idoso_etapa6,
    montar_mensagem_cliente_menor_18_etapa6,
    montar_mensagem_contexto_idade_dependente_invalida_etapa6,
    montar_mensagem_contexto_idade_invalida_etapa6,
    montar_mensagem_dependente_menor_5_etapa6,
    montar_mensagem_idade_acima_99_etapa6,
    montar_mensagem_idade_dependente_etapa6,
    montar_mensagem_idade_dependente_etapa6_financeiro,
    montar_mensagem_idade_dependente_etapa6_midia,
    montar_mensagem_idade_dependente_etapa6_reforco_escolar,
    montar_mensagem_idade_etapa6,
    montar_mensagem_idade_etapa6_financeiro,
    montar_mensagem_idade_etapa6_midia,
    montar_mensagem_idade_etapa6_reforco_escolar,
    montar_mensagem_suporte_idoso_etapa6,
)
from core.integrations.whatsapp.numero_comercial import (
    montar_link_numero_comercial_whatsapp,
)
from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.etapa6")

ID_ETAPA6 = 6
TIPO_TRATAMENTO_MIDIA = "tipo_mensagem_nao_suportado"
TIPO_TRATAMENTO_FINANCEIRO = "pergunta_financeira"
TIPO_TRATAMENTO_REFORCO_ESCOLAR = "duvida_reforco_escolar"
TIPO_TRATAMENTO_IDADE_INVALIDA = "idade_invalida"


# CENARIO NORMAL: PERGUNTAR A IDADE DO PROPRIO CLIENTE
def enviar_etapa6_cliente(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_idade_etapa6()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente",
    )


# CENARIO NORMAL: PERGUNTAR A IDADE DO DEPENDENTE
def enviar_etapa6_dependente(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa6(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente",
    )


# CLIENTE RESPONDE A ETAPA 6 COM MIDIA
def enviar_etapa6_cliente_midia(cliente_telefone, phone_id_unidade):
    mensagem_bot = montar_mensagem_idade_etapa6_midia()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM MIDIA
def enviar_etapa6_dependente_midia(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa6_midia(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_midia",
        tipo_tratamento=TIPO_TRATAMENTO_MIDIA,
    )


# CLIENTE RESPONDE A IDADE COM PERGUNTA FINANCEIRA
def enviar_etapa6_cliente_financeiro(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_idade_etapa6_financeiro()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM PERGUNTA FINANCEIRA
def enviar_etapa6_dependente_financeiro(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa6_financeiro(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_financeiro",
        tipo_tratamento=TIPO_TRATAMENTO_FINANCEIRO,
    )


# CLIENTE PERGUNTA SE O SUPERA É REFORÇO ESCOLAR
def enviar_etapa6_cliente_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_idade_etapa6_reforco_escolar()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


def enviar_etapa6_dependente_reforco_escolar(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = montar_mensagem_idade_dependente_etapa6_reforco_escolar(
        nome_dependente
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_reforco_escolar",
        tipo_tratamento=TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    )


# CLIENTE RESPONDE A ETAPA 6 COM IDADE INVALIDA
def enviar_etapa6_cliente_contexto_idade_invalida(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_contexto_idade_invalida_etapa6()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_contexto_idade_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_IDADE_INVALIDA,
    )


# CLIENTE RESPONDE A IDADE DO DEPENDENTE COM IDADE INVALIDA
def enviar_etapa6_dependente_contexto_idade_invalida(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    mensagem_bot = (
        montar_mensagem_contexto_idade_dependente_invalida_etapa6(
            nome_dependente
        )
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_contexto_idade_invalida",
        tipo_tratamento=TIPO_TRATAMENTO_IDADE_INVALIDA,
    )


# CLIENTE COM MENOS DE 18 ANOS
def enviar_etapa6_cliente_menor_18(
    cliente_telefone,
    phone_id_unidade,
):
    mensagem_bot = montar_mensagem_cliente_menor_18_etapa6()

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_cliente_menor_18",
    )


# DEPENDENTE COM MENOS DE 5 ANOS
def enviar_etapa6_dependente_menor_5(
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
    idade_minima=5,
):
    mensagem_bot = montar_mensagem_dependente_menor_5_etapa6(
        nome_dependente,
        idade_minima,
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_dependente_menor_5",
    )


# CLIENTE OU DEPENDENTE COM MAIS DE 99 ANOS
def enviar_etapa6_idade_acima_99(
    cliente_telefone,
    phone_id_unidade,
    numero_comercial,
):
    mensagem_bot = montar_mensagem_idade_acima_99_etapa6()
    botao_url = URLButton(
        title=montar_botao_idade_acima_99_etapa6(),
        url=montar_link_numero_comercial_whatsapp(numero_comercial),
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_idade_acima_99",
        botao_url=botao_url,
    )


def enviar_etapa6_suporte_idoso(
    cliente_telefone,
    phone_id_unidade,
    numero_comercial,
    idade_minima,
):
    mensagem_bot = montar_mensagem_suporte_idoso_etapa6(idade_minima)
    botao_url = URLButton(
        title=montar_botao_suporte_idoso_etapa6(),
        url=montar_link_numero_comercial_whatsapp(numero_comercial),
    )

    return _enviar_texto_etapa6(
        cliente_telefone,
        phone_id_unidade,
        mensagem_bot,
        evento="enviar_etapa6_suporte_idoso",
        botao_url=botao_url,
    )


# CONSTRUTOR DE ENVIO DE TEXTO DA ETAPA 6
def _enviar_texto_etapa6(
    cliente_telefone,
    phone_id_unidade,
    mensagem_bot,
    *,
    evento,
    tipo_tratamento=None,
    botao_url=None,
):
    try:
        cliente_wa = conta_wa(phone_id_unidade)
        parametros_envio = {
            "to": cliente_telefone,
            "text": mensagem_bot,
        }

        if botao_url is not None:
            parametros_envio["buttons"] = botao_url

        sent_message = cliente_wa.send_message(
            **parametros_envio,
        )
        id_hash_msg_bot = extrair_id_hash_msg_bot(sent_message)

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
            "id_etapa_resultante": ID_ETAPA6,
            "tipo_mensagem": (
                "interactive_cta_url" if botao_url else "text"
            ),
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
            "Meta falhou ao enviar mensagem da etapa 6",
            id_etapa=ID_ETAPA6,
            phone_id_unidade=phone_id_unidade,
            cliente_telefone=cliente_telefone,
        ) from erro
```

### Passo 10 — `workers/worker_flow/response_flow/etapas/resolver_etapa6.py`

**Ação:** Alterar. Comparar somente a idade do titular ao limite, depois dos tratamentos prioritários e de 100+.

Conteúdo completo do arquivo:

```python
import logging

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte

from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa6 import (
    enviar_etapa6_cliente_contexto_idade_invalida,
    enviar_etapa6_cliente_financeiro,
    enviar_etapa6_cliente_menor_18,
    enviar_etapa6_cliente_midia,
    enviar_etapa6_cliente_reforco_escolar,
    enviar_etapa6_dependente_contexto_idade_invalida,
    enviar_etapa6_dependente_financeiro,
    enviar_etapa6_dependente_menor_5,
    enviar_etapa6_dependente_midia,
    enviar_etapa6_dependente_reforco_escolar,
    enviar_etapa6_idade_acima_99,
    enviar_etapa6_suporte_idoso,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders.etapa7 import (
    enviar_etapa7_cliente,
    enviar_etapa7_dependente,
)
from core.logging_config import short_value
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    obter_idade_minima_dependente,
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_financeiro import (
    TIPO_TRATAMENTO_FINANCEIRO,
    validar_pergunta_financeira,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_reforco_escolar import (
    TIPO_TRATAMENTO_REFORCO_ESCOLAR,
    validar_duvida_reforco_escolar,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_7_OFERTA_AULA,
    EVENTO_IDADE_VALIDA,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    anexar_transicao_ao_contexto_envio,
    resolver_destino_transicao,
)


logger = logging.getLogger("worker.etapa6")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"
MOTIVO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


def resolve_etapa6(contexto_historico):
    """
    Valida a idade do aluno e decide tratamento, encerramento ou 6 -> 7.
    """
    tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
    texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
    status_dependente = bool(
        contexto_historico.get("status_dependente")
    )
    bpa_ativo = bool(contexto_historico.get("bpa_ativo_unidade"))
    nome_dependente = contexto_historico.get("nome_dependente")
    nome_cliente = contexto_historico.get("nome_cliente")
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

    # A dúvida sobre reforço é mais específica que o financeiro e a idade.
    if validar_duvida_reforco_escolar(texto_cliente):
        _logar_tratamento(
            contexto_historico,
            TIPO_TRATAMENTO_REFORCO_ESCOLAR,
        )
        return _enviar_tratamento_reforco_escolar(
            status_dependente,
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

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
        contexto_envio = enviar_etapa6_idade_acima_99(
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

    # A chave ausente é erro; None é a configuração explicitamente desativada.
    idade_minima = validar_idade_minima_suporte(
        contexto_historico["idade_minima_suporte"]
    )

    # O tratamento universal de 100+ já ocorreu. Dependentes seguem seu fluxo.
    if (
        not status_dependente
        and idade_minima is not None
        and idade >= idade_minima
    ):
        contexto_envio = enviar_etapa6_suporte_idoso(
            cliente_telefone,
            phone_id_unidade,
            contexto_historico.get("numero_comercial_unidade"),
            idade_minima,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_SUPORTE_IDOSO,
        )

    if not status_dependente and idade < 18:
        contexto_envio = enviar_etapa6_cliente_menor_18(
            cliente_telefone,
            phone_id_unidade,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_CLIENTE_MENOR_18,
        )

    idade_minima_dependente = obter_idade_minima_dependente(
        bpa_ativo
    )

    if status_dependente and idade < idade_minima_dependente:
        contexto_envio = enviar_etapa6_dependente_menor_5(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
            idade_minima_dependente,
        )
        return _anexar_encerramento(
            contexto_envio,
            idade,
            MOTIVO_DEPENDENTE_MENOR_5,
            excluir_dependente=True,
        )

    # VALIDANDO DESTINO(S)
    # A resposta passou pelos tratamentos; agora o mapa autoriza 6 -> 7.
    etapa_destino = resolver_destino_transicao(
        contexto_historico,
        EVENTO_IDADE_VALIDA,
        destinos_esperados={ETAPA_7_OFERTA_AULA},
    )

    logger.info(
        "etapa6_idade_validada | acao=enviar_etapa7 "
        "id_conversa=%s id_mensagem_fila=%s evento=%s "
        "etapa_destino=%s idade=%s status_dependente=%s",
        contexto_historico["id_conversa"],
        mensagem_cliente["id_mensagem_fila"],
        EVENTO_IDADE_VALIDA,
        etapa_destino,
        idade,
        status_dependente,
    )

    if status_dependente:
        contexto_envio = enviar_etapa7_dependente(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )
    else:
        contexto_envio = enviar_etapa7_cliente(
            cliente_telefone,
            phone_id_unidade,
            nome_cliente,
        )

    contexto_envio["idade_aluno"] = idade

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
        return enviar_etapa6_dependente_midia(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_midia(
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
        return enviar_etapa6_dependente_financeiro(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_financeiro(
        cliente_telefone,
        phone_id_unidade,
    )


def _enviar_tratamento_reforco_escolar(
    status_dependente,
    cliente_telefone,
    phone_id_unidade,
    nome_dependente,
):
    if status_dependente:
        return enviar_etapa6_dependente_reforco_escolar(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_reforco_escolar(
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
        return enviar_etapa6_dependente_contexto_idade_invalida(
            cliente_telefone,
            phone_id_unidade,
            nome_dependente,
        )

    return enviar_etapa6_cliente_contexto_idade_invalida(
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

### Passo 11 — `workers/worker_flow/transacoes/efeitos_transicao.py`

**Ação:** Alterar. Aceitar a idade 50–99 no efeito de encaminhamento autorizado, sem mover commits ou efeitos de outras etapas.

Conteúdo completo do arquivo:

```python
import logging

from core.logging_config import short_value
from core.repositories.atendimento.clientes import (
    atualizar_email_cliente,
    atualizar_idade_cliente,
    atualizar_nome_cliente_por_telefone,
    atualizar_profissao_cliente,
)
from core.repositories.atendimento.conversas import (
    atualizar_profissao_conversa,
    atualizar_status_dependente_conversa,
)
from core.repositories.atendimento.dependentes import (
    atualizar_idade_dependente,
    atualizar_nome_dependente_por_conversa,
    inserir_dependente_para_conversa,
    remover_dependente_placeholder_da_conversa,
)
from core.repositories.fluxo.triagem import registrar_resposta_triagem
from core.repositories.fluxo.pesquisa_satisfacao import (
    salvar_comentario_satisfacao,
    salvar_nota_satisfacao,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa19 import (
    validar_etapa19,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa21 import (
    normalizar_comentario_etapa21,
    recusou_comentario_etapa21,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_nome import (
    validar_nome_cliente,
)
from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    validar_resposta_triagem,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    validar_idade,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa2 import (
    OPCAO_PARA_OUTRA_PESSOA,
    validar_etapa2,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    validar_profissao_etapa4,
)
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa10 import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
    classificar_resposta_email_aceita,
    validar_etapa10,
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
    ETAPA_22_FINALIZACAO,
    EVENTO_AGENDAMENTO_CONFIRMADO,
    EVENTO_CLIENTE_RETORNOU,
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO,
    EVENTO_EMAIL_VALIDO,
    EVENTO_IDADE_VALIDA,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
    EVENTO_PROFISSAO_TITULAR_VALIDA,
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
    EVENTO_SATISFACAO_AVALIADA,
    EVENTO_TRIAGEM_INICIADA,
    EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
)


logger = logging.getLogger("worker.support")

MOTIVO_ENCAMINHAMENTO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


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

    if (
        etapa_origem == ETAPA_6_IDADE_ALUNO
        and contexto_envio.get("encerrar_atendimento")
        and contexto_envio.get("motivo_encerramento")
        == MOTIVO_ENCAMINHAMENTO_SUPORTE_IDOSO
    ):
        return _persistir_idade_encaminhamento_suporte_idoso(
            contexto_historico,
            contexto_envio,
            cursor,
        )

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
        # 2 -> 3: a opção foi validada e aguarda confirmação explícita.
        if evento == EVENTO_DESTINO_ATENDIMENTO_DEFINIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_3_CONFIRMACAO_DESTINO,
            )
            return _persistir_destino_atendimento_da_etapa2(
                contexto_historico,
                contexto_envio,
                etapa_destino,
                cursor=cursor,
            )

    # ETAPA 3
    if etapa_origem == ETAPA_3_CONFIRMACAO_DESTINO:
        if evento == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_4_PROFISSAO,
            )
            return _persistir_confirmacao_destino_da_etapa3(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 4
    if etapa_origem == ETAPA_4_PROFISSAO:
        if evento == EVENTO_PROFISSAO_DEPENDENTE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_5_NOME_DEPENDENTE,
            )
            return _persistir_profissao_capturada_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=True,
            )

        if evento == EVENTO_PROFISSAO_TITULAR_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_6_IDADE_ALUNO,
            )
            return _persistir_profissao_capturada_na_etapa4(
                contexto_historico,
                contexto_envio,
                cursor,
                status_dependente_esperado=False,
            )

    # ETAPA 5
    if etapa_origem == ETAPA_5_NOME_DEPENDENTE:
        # 5 -> 6: o cliente informou o nome do dependente.
        if evento == EVENTO_NOME_DEPENDENTE_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_6_IDADE_ALUNO,
            )
            return _persistir_nome_dependente_capturado_na_etapa5(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 6
    if etapa_origem == ETAPA_6_IDADE_ALUNO:
        # 6 -> 7: a idade do aluno foi validada.
        if evento == EVENTO_IDADE_VALIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_7_OFERTA_AULA,
            )
            return _persistir_idade_capturada_na_etapa6(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 7
    if etapa_origem == ETAPA_7_OFERTA_AULA:
        # 7 -> 10: o cliente aceitou agendar.
        if evento == EVENTO_OFERTA_ACEITA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_EMAIL,
            )
            return _confirmar_decisao_oferta_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 7 -> 8: o cliente preferiu adiar.
        if evento == EVENTO_OFERTA_ADIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_OFERTA_ADIADA,
            )
            return _confirmar_decisao_oferta_da_etapa7(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 8
    if etapa_origem == ETAPA_8_OFERTA_ADIADA:
        # 8 -> 9: o cliente enviou uma nova mensagem após adiar a oferta.
        if evento == EVENTO_CLIENTE_RETORNOU:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_9_RETORNO_OFERTA,
            )
            return _confirmar_retorno_cliente_da_etapa8(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 9
    if etapa_origem == ETAPA_9_RETORNO_OFERTA:
        # 9 -> 10: o cliente retomou e confirmou o agendamento.
        if evento == EVENTO_RETORNO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_10_EMAIL,
            )
            return _confirmar_decisao_retorno_da_etapa9(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 9 -> 8: o cliente preferiu adiar novamente.
        if evento == EVENTO_RETORNO_ADIADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_8_OFERTA_ADIADA,
            )
            return _confirmar_decisao_retorno_da_etapa9(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 10
    if etapa_origem == ETAPA_10_EMAIL:
        # 10 -> 11: a coleta foi aceita. A aresta técnica legada é única;
        # o resultado semântico distingue endereço, ausência e não informado.
        if evento == EVENTO_EMAIL_VALIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_11_INTRODUCAO_TRIAGEM,
            )
            return _persistir_email_capturado_na_etapa10(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 11
    if etapa_origem == ETAPA_11_INTRODUCAO_TRIAGEM:
        # 11 -> 12: o cliente iniciou a triagem cognitiva.
        if evento == EVENTO_TRIAGEM_INICIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_12_TRIAGEM_PERGUNTA_1,
            )
            return _confirmar_inicio_triagem_da_etapa11(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 12
    if etapa_origem == ETAPA_12_TRIAGEM_PERGUNTA_1:
        # 12 -> 13: registra a resposta da pergunta 1.
        if evento == EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_13_TRIAGEM_PERGUNTA_2,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 13
    if etapa_origem == ETAPA_13_TRIAGEM_PERGUNTA_2:
        # 13 -> 14: registra a resposta da pergunta 2.
        if evento == EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_14_TRIAGEM_PERGUNTA_3,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 14
    if etapa_origem == ETAPA_14_TRIAGEM_PERGUNTA_3:
        # 14 -> 15: registra a resposta da pergunta 3.
        if evento == EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_15_TRIAGEM_PERGUNTA_4,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 15
    if etapa_origem == ETAPA_15_TRIAGEM_PERGUNTA_4:
        # 15 -> 16: registra a resposta da pergunta 4.
        if evento == EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_16_TRIAGEM_PERGUNTA_5,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 16
    if etapa_origem == ETAPA_16_TRIAGEM_PERGUNTA_5:
        # 16 -> 17: registra a resposta da pergunta 5.
        if evento == EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_17_TRIAGEM_PERGUNTA_6,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 17
    if etapa_origem == ETAPA_17_TRIAGEM_PERGUNTA_6:
        # 17 -> 18: registra a resposta da pergunta 6.
        if evento == EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_18_AGENDAMENTO,
            )
            return _persistir_resposta_triagem(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 18
    if etapa_origem == ETAPA_18_AGENDAMENTO:
        # 18 -> 19: o cliente confirmou o agendamento e inicia a pesquisa.
        if evento == EVENTO_AGENDAMENTO_CONFIRMADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_19_PESQUISA_SATISFACAO,
            )
            return _confirmar_agendamento_da_etapa18(
                contexto_historico,
                evento,
                etapa_destino,
            )

    # ETAPA 19
    if etapa_origem == ETAPA_19_PESQUISA_SATISFACAO:
        # 19 -> 20: registra a nota normalizada da pesquisa de satisfacao.
        if evento == EVENTO_SATISFACAO_AVALIADA:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_20_DECISAO_COMENTARIO,
            )
            return _persistir_nota_satisfacao_da_etapa19(
                contexto_historico,
                contexto_envio,
                cursor,
            )

    # ETAPA 20
    if etapa_origem == ETAPA_20_DECISAO_COMENTARIO:
        # 20 -> 21: confirma que o cliente deseja escrever um comentario.
        if evento == EVENTO_COMENTARIO_SATISFACAO_ACEITO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_21_COMENTARIO_SATISFACAO,
            )
            return _confirmar_decisao_comentario_da_etapa20(
                contexto_historico,
                evento,
                etapa_destino,
            )

        # 20 -> 22: registra a recusa explicita e encerra o atendimento.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECUSADO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_22_FINALIZACAO,
            )
            return _persistir_recusa_comentario_da_etapa20(
                contexto_historico,
                cursor,
            )

    # ETAPA 21
    if etapa_origem == ETAPA_21_COMENTARIO_SATISFACAO:
        # 21 -> 22: registra o comentario livre antes da finalizacao.
        if evento == EVENTO_COMENTARIO_SATISFACAO_RECEBIDO:
            _exigir_destino(
                etapa_origem,
                evento,
                etapa_destino,
                ETAPA_22_FINALIZACAO,
            )
            return _persistir_comentario_satisfacao_da_etapa21(
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
    contexto_envio,
    etapa_destino,
    *,
    cursor,
):
    id_conversa = contexto_historico["id_conversa"]
    opcao_atendimento = contexto_envio.get("opcao_atendimento")

    if opcao_atendimento is None:
        opcao_atendimento = validar_etapa2(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if opcao_atendimento is None:
        raise ValueError(
            "Destino do atendimento nao reconstruido na transicao 2 -> 3"
        )

    status_dependente = (
        opcao_atendimento == OPCAO_PARA_OUTRA_PESSOA
    )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente,
        cursor,
    )

    contexto_persistido = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente,
        "opcao_atendimento": opcao_atendimento,
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
        EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
        contexto_historico.get("id_etapa_origem_transicao"),
        etapa_destino,
        id_conversa,
        status_dependente,
        contexto_persistido["dependente_criado"],
    )

    return contexto_persistido


def _persistir_confirmacao_destino_da_etapa3(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Aplica o destino final como valor absoluto e seguro para replay.

    No primeiro processamento, o validador produz o valor absoluto. Em replay,
    movimento e efeito já foram confirmados juntos, então o worker relê esse
    mesmo valor da conversa. A resposta relativa nunca é reinterpretada.
    """
    status_dependente_final = contexto_envio.get(
        "status_dependente_final"
    )
    if not isinstance(status_dependente_final, bool):
        raise ValueError(
            "Confirmacao da etapa 3 sem status_dependente_final booleano "
            f"(valor={status_dependente_final!r})"
        )

    id_conversa = contexto_historico["id_conversa"]
    status_anterior = contexto_historico.get("status_dependente")
    if not isinstance(status_anterior, bool):
        raise ValueError(
            "Confirmacao da etapa 3 sem status_dependente anterior booleano "
            f"(valor={status_anterior!r})"
        )

    atualizar_status_dependente_conversa(
        id_conversa,
        status_dependente_final,
        cursor,
    )

    resultado = {
        "status_dependente_atualizado": True,
        "status_dependente": status_dependente_final,
        "status_dependente_alterado": (
            status_anterior != status_dependente_final
        ),
        "dependente_criado": False,
        "dependente_removido": False,
    }

    if status_dependente_final:
        dependente = inserir_dependente_para_conversa(id_conversa, cursor)
        resultado.update(
            {
                "dependente_criado": dependente["inserido"],
                "id_dependente": dependente["id_dependente"],
                "id_cliente_dependente": dependente["id_cliente"],
            }
        )
    else:
        resultado["dependente_removido"] = (
            remover_dependente_placeholder_da_conversa(
                id_conversa,
                cursor,
            )
        )

    logger.info(
        "destino_atendimento_confirmado | acao=aplicar_status_absoluto "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s "
        "status_anterior=%s status_final=%s dependente_criado=%s "
        "dependente_removido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico.get("id_etapa_origem_transicao"),
        contexto_envio.get("id_etapa_resultante"),
        id_conversa,
        status_anterior,
        status_dependente_final,
        resultado["dependente_criado"],
        resultado["dependente_removido"],
    )

    return resultado


def _persistir_profissao_capturada_na_etapa4(
    contexto_historico,
    contexto_envio,
    cursor,
    *,
    status_dependente_esperado,
):
    status_dependente = contexto_historico.get("status_dependente")
    if not isinstance(status_dependente, bool):
        raise ValueError(
            "Profissao sem status_dependente booleano persistido "
            f"(valor={status_dependente!r})"
        )

    if status_dependente != status_dependente_esperado:
        raise ValueError(
            "Evento da profissao incompativel com o destino do atendimento "
            f"(id_conversa={contexto_historico['id_conversa']}, "
            f"status_dependente={status_dependente})"
        )

    profissao = contexto_envio.get("profissao")

    if profissao is None:
        resultado = validar_profissao_etapa4(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )
        if resultado.valida:
            profissao = resultado.profissao

    if not profissao:
        raise ValueError(
            "Profissao nao reconstruida na transicao da etapa 4"
        )

    atualizar_profissao_conversa(
        contexto_historico["id_conversa"],
        profissao,
        cursor,
    )
    atualizar_profissao_cliente(
        contexto_historico["id_cliente"],
        profissao,
        cursor,
    )

    logger.info(
        "profissao_persistida | acao=salvar_snapshot_e_atualizar_cliente "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s profissao=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        short_value(profissao),
    )

    return {
        "profissao_atualizada": True,
        "profissao": profissao,
    }


def _persistir_nome_dependente_capturado_na_etapa5(
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
            "dependente_nome_anomalia_critica | motivo=nome_vazio_na_transicao_5_6 acao=rollback_e_retry id_conversa=%s etapa_origem=%s etapa_resultante=%s",
            contexto_historico["id_conversa"],
            contexto_historico.get("id_etapa_origem_transicao"),
            contexto_envio.get("id_etapa_resultante"),
        )
        raise ValueError(
            "Nome do dependente nao foi resolvido na transicao 5 -> 6"
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


def _persistir_idade_capturada_na_etapa6(
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
            "Idade não reconstruída na transição 6 -> 7"
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


def _persistir_idade_encaminhamento_suporte_idoso(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_historico.get("status_dependente"):
        raise ValueError(
            "Encaminhamento de suporte ao idoso não aceita dependente"
        )

    idade = contexto_envio.get("idade_aluno")
    if idade is None:
        resultado = validar_idade(
            contexto_historico.get("texto_cliente_atual") or ""
        )
        idade = resultado.idade if resultado.valida else None

    if (
        isinstance(idade, bool)
        or not isinstance(idade, int)
        or not 50 <= idade <= 99
    ):
        raise ValueError(
            "Idade inválida no encaminhamento de suporte ao idoso "
            f"(idade={idade!r})"
        )

    atualizar_idade_cliente(
        contexto_historico["id_cliente"],
        idade,
        cursor,
    )

    logger.info(
        "idade_titular_persistida | acao=encaminhar_suporte_idoso "
        "id_conversa=%s id_cliente=%s faixa=50_99",
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
    )
    return {
        "idade_aluno_atualizada": True,
        "idade_aluno": idade,
        "destino_dado": "cliente",
        "encaminhamento_suporte_idoso": True,
    }


def _confirmar_decisao_oferta_da_etapa7(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a aresta da oferta sem duplicar persistência.

    A mudança de id_etapa_atual já foi executada e revalidada no PostgreSQL
    por persistir_movimento_conversa antes dos efeitos específicos.
    """
    logger.info(
        "decisao_oferta_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_oferta_persistida": True,
        "decisao_oferta": evento,
    }


def _confirmar_retorno_cliente_da_etapa8(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta etapa apenas torna explícita a aresta 8 -> 9.
    """
    logger.info(
        "retorno_cliente_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "retorno_cliente_persistido": True,
        "evento_retorno": evento,
    }


def _confirmar_decisao_retorno_da_etapa9(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Torna explícita a decisão do retorno sem duplicar persistência.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função confirma apenas as arestas 9 -> 10 e 9 -> 8.
    """
    logger.info(
        "decisao_retorno_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_retorno_persistida": True,
        "decisao_retorno": evento,
    }


def _persistir_email_capturado_na_etapa10(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste de forma absoluta o resultado aceito na conversa atual."""
    classificacao = contexto_envio.get("resultado_coleta_email")
    email = contexto_envio.get("email_cliente")

    if classificacao is None and email:
        classificacao = CLASSIFICACAO_EMAIL_VALIDO
        email = validar_etapa10(email).email

    if classificacao is None:
        texto_cliente = contexto_historico.get("texto_cliente_atual") or ""

        if contexto_envio.get("resposta_ja_existia"):
            resultado_email = classificar_resposta_email_aceita(
                texto_cliente
            )
        else:
            email_obrigatorio = calcular_email_obrigatorio_efetivo(
                contexto_historico.get("email_obrigatorio_unidade"),
                contexto_historico.get("status_dependente"),
                contexto_historico.get("idade_cliente"),
            )
            resultado_email = classificar_resposta_email(
                texto_cliente,
                email_obrigatorio=email_obrigatorio,
            )

        if not resultado_email.aceita:
            raise ValueError(
                "Resultado de email nao reconstruido na transicao 10 -> 11"
            )

        classificacao = resultado_email.classificacao
        email = resultado_email.email

    classificacoes_validas = {
        CLASSIFICACAO_EMAIL_VALIDO,
        CLASSIFICACAO_EMAIL_AUSENTE,
        CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    }
    if classificacao not in classificacoes_validas:
        raise ValueError(
            "Classificacao de email invalida na transicao 10 -> 11 "
            f"(classificacao={classificacao!r})"
        )

    if classificacao == CLASSIFICACAO_EMAIL_VALIDO:
        resultado_estrutural = validar_etapa10(email)
        if not resultado_estrutural.valido:
            raise ValueError(
                "Email valido sem endereco reconstruivel na transicao 10 -> 11"
            )
        email = resultado_estrutural.email
    else:
        email = None

    atualizar_email_cliente(
        contexto_historico["id_cliente"],
        email,
        cursor,
    )

    logger.info(
        "cliente_email_persistido | acao=salvar_efeito_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s id_cliente=%s email_preenchido=%s "
        "resultado_coleta=%s",
        EVENTO_EMAIL_VALIDO,
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        contexto_historico["id_cliente"],
        bool(email),
        classificacao,
    )

    return {
        "cliente_email_atualizado": True,
        "email_preenchido": bool(email),
        "resultado_coleta_email": classificacao,
    }


def _confirmar_inicio_triagem_da_etapa11(
    contexto_historico,
    evento,
    etapa_destino,
):
    """
    Confirma a continuidade sem criar dado de negócio adicional.

    A mudança de id_etapa_atual já foi persistida pelo movimento genérico da
    conversa. Esta função torna explícita somente a aresta 11 -> 12.
    """
    logger.info(
        "inicio_triagem_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "inicio_triagem_persistido": True,
        "evento_triagem": evento,
    }


def _persistir_resposta_triagem(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """
    Persiste a opção da pergunta de origem dentro da transação final.

    Em reaplicação idempotente, o contexto de envio não possui a resposta.
    Nesse caso, a opção é reconstruída pela mensagem original do cliente.
    """
    resposta_triagem = contexto_envio.get("resposta_triagem")

    if resposta_triagem is None:
        resposta_triagem = validar_resposta_triagem(
            contexto_historico.get("texto_cliente_atual") or "",
            contexto_historico.get("tipo_mensagem_atual"),
        )

    if resposta_triagem is None:
        raise ValueError(
            "Resposta da triagem não foi reconstruída na transição "
            f"(etapa={contexto_historico.get('id_etapa_origem_transicao')})"
        )

    mensagem_cliente = contexto_historico["mensagem_cliente_atual"]
    resultado = registrar_resposta_triagem(
        contexto_historico["id_conversa"],
        contexto_historico["id_etapa_origem_transicao"],
        resposta_triagem,
        mensagem_cliente.get("id_mensagem"),
        cursor,
    )

    logger.info(
        "efeito_resposta_triagem_persistido | acao=salvar_resposta "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s resposta=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        resposta_triagem,
        resultado["inserido"],
    )

    return {
        "resposta_triagem_persistida": True,
        **resultado,
    }


def _confirmar_agendamento_da_etapa18(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a aresta 18 -> 19 sem criar dado de negocio adicional."""
    logger.info(
        "agendamento_confirmado_persistido | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "agendamento_confirmado": True,
        "evento_agendamento": evento,
    }


def _persistir_nota_satisfacao_da_etapa19(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste a nota; em retry, reconstrói o valor pela mensagem original."""
    nota_satisfacao = contexto_envio.get("nota_satisfacao")

    if nota_satisfacao is None:
        nota_satisfacao = validar_etapa19(
            contexto_historico.get("texto_cliente_atual") or ""
        )

    if nota_satisfacao is None:
        raise ValueError(
            "Nota de satisfacao ausente na transicao 19 -> 20 "
            f"(id_conversa={contexto_historico['id_conversa']})"
        )

    resultado = salvar_nota_satisfacao(
        contexto_historico["id_conversa"],
        nota_satisfacao,
        cursor,
    )

    logger.info(
        "efeito_nota_satisfacao_persistido | acao=salvar_nota "
        "evento=%s etapa_origem=%s etapa_resultante=%s "
        "id_conversa=%s nota=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        nota_satisfacao,
        resultado["inserido"],
    )

    return {
        "nota_satisfacao_persistida": True,
        **resultado,
    }


def _confirmar_decisao_comentario_da_etapa20(
    contexto_historico,
    evento,
    etapa_destino,
):
    """Confirma a escolha sem criar dado antes do comentário efetivo."""
    logger.info(
        "decisao_comentario_persistida | acao=confirmar_transicao "
        "evento=%s etapa_origem=%s etapa_resultante=%s id_conversa=%s",
        evento,
        contexto_historico["id_etapa_origem_transicao"],
        etapa_destino,
        contexto_historico["id_conversa"],
    )

    return {
        "decisao_comentario_persistida": True,
        "decisao_comentario": evento,
    }


def _persistir_recusa_comentario_da_etapa20(
    contexto_historico,
    cursor,
):
    """Registra NULL de forma idempotente para a recusa explícita."""
    resultado = salvar_comentario_satisfacao(
        contexto_historico["id_conversa"],
        None,
        cursor,
    )

    logger.info(
        "recusa_comentario_satisfacao_persistida | "
        "acao=salvar_comentario_nulo evento=%s etapa_origem=%s "
        "etapa_resultante=%s id_conversa=%s inserido=%s",
        EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
        contexto_historico["id_etapa_origem_transicao"],
        ETAPA_22_FINALIZACAO,
        contexto_historico["id_conversa"],
        resultado["inserido"],
    )

    return {
        "comentario_satisfacao_persistido": True,
        **resultado,
    }


def _persistir_comentario_satisfacao_da_etapa21(
    contexto_historico,
    contexto_envio,
    cursor,
):
    """Persiste o texto; em retry, reconstrói a mensagem original."""
    if "comentario_satisfacao" in contexto_envio:
        comentario_satisfacao = contexto_envio["comentario_satisfacao"]
    else:
        texto_cliente = contexto_historico.get("texto_cliente_atual") or ""
        tipo_mensagem = contexto_historico.get("tipo_mensagem_atual")
        desistiu = recusou_comentario_etapa21(
            texto_cliente,
            tipo_mensagem,
        )
        comentario_satisfacao = normalizar_comentario_etapa21(
            texto_cliente,
            tipo_mensagem,
        )

        if comentario_satisfacao is None and not desistiu:
            raise ValueError(
                "Comentario de satisfacao nao reconstruido na "
                "transicao 21 -> 22 "
                f"(id_conversa={contexto_historico['id_conversa']})"
            )

    resultado = salvar_comentario_satisfacao(
        contexto_historico["id_conversa"],
        comentario_satisfacao,
        cursor,
    )

    logger.info(
        "efeito_comentario_satisfacao_persistido | "
        "acao=salvar_comentario evento=%s etapa_origem=%s "
        "etapa_resultante=%s id_conversa=%s "
        "comentario_preenchido=%s inserido=%s",
        contexto_envio.get("evento_transicao"),
        contexto_historico["id_etapa_origem_transicao"],
        contexto_envio["id_etapa_resultante"],
        contexto_historico["id_conversa"],
        bool(comentario_satisfacao),
        resultado["inserido"],
    )

    return {
        "comentario_satisfacao_persistido": True,
        **resultado,
    }
```

### Passo 12 — `workers/worker_flow/transacoes/encerramento_atendimento.py`

**Ação:** Alterar. Reconhecer as cinco mensagens oficiais no retry e usar o limite atual quando reavaliar o encerramento.

Conteúdo completo do arquivo:

```python
import logging

from core.validacoes.suporte_por_idade import (
    IDADES_MINIMAS_SUPORTE,
    validar_idade_minima_suporte,
)

from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_suporte_idoso_etapa6,
)
from core.repositories.atendimento.conversas import encerrar_conversa
from core.repositories.atendimento.dependentes import (
    excluir_dependente_da_conversa,
)
from core.repositories.fluxo.politicas import buscar_politica_etapa
from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa6 import (
    obter_idade_minima_dependente,
    validar_idade,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    ETAPA_6_IDADE_ALUNO,
)


logger = logging.getLogger("worker.support")

MOTIVO_CLIENTE_MENOR_18 = "cliente_menor_18"
MOTIVO_DEPENDENTE_MENOR_5 = "dependente_menor_5"
MOTIVO_IDADE_ACIMA_99 = "idade_acima_99"
MOTIVO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"
MOTIVO_ETAPA_FINAL = "etapa_final"

MOTIVO_ENCERRAMENTO_IDADE_INVALIDA = "idade_invalida"
MOTIVO_ENCERRAMENTO_FOI_AGENDADO = "foi_agendado"
MOTIVO_ENCERRAMENTO_SUPORTE_IDOSO = "encaminhado_suporte_idoso"


def resolver_intencao_encerramento(
    contexto_historico,
    contexto_envio,
    cursor,
):
    if contexto_envio.get("encerrar_atendimento"):
        motivo = contexto_envio["motivo_encerramento"]
        motivo_banco = (
            MOTIVO_ENCERRAMENTO_SUPORTE_IDOSO
            if motivo == MOTIVO_SUPORTE_IDOSO
            else MOTIVO_ENCERRAMENTO_IDADE_INVALIDA
        )
        return {
            "motivo": motivo,
            "motivo_encerramento": motivo_banco,
            "excluir_dependente": bool(
                contexto_envio.get("excluir_dependente")
            ),
            "bloqueio_dias": 0,
        }

    # No retry, a resposta já existe e a decisão é reconstruída pela mesma
    # mensagem original da etapa 6, sem consultar conversas anteriores.
    if contexto_envio.get("resposta_ja_existia"):
        intencao_reconstruida = _reconstruir_encerramento_etapa6(
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
        "motivo_encerramento": MOTIVO_ENCERRAMENTO_FOI_AGENDADO,
        "excluir_dependente": False,
        "bloqueio_dias": politica_destino.bloqueio_dias,
    }


def _reconstruir_encerramento_etapa6(contexto_historico):
    if (
        contexto_historico.get("id_etapa_origem_transicao")
        != ETAPA_6_IDADE_ALUNO
    ):
        return None

    resultado = validar_idade(
        contexto_historico.get("texto_cliente_atual") or ""
    )

    if resultado.acima_limite:
        return {
            "motivo": MOTIVO_IDADE_ACIMA_99,
            "motivo_encerramento": MOTIVO_ENCERRAMENTO_IDADE_INVALIDA,
            "excluir_dependente": False,
            "bloqueio_dias": 0,
        }

    if not resultado.valida:
        return None

    if (
        not contexto_historico.get("status_dependente")
        and 50 <= resultado.idade <= 99
        and _resposta_bot_e_encaminhamento_suporte_idoso(
            contexto_historico
        )
    ):
        # O texto prova o envio, mas não congela a configuração anterior.
        idade_minima = validar_idade_minima_suporte(
            contexto_historico["idade_minima_suporte"]
        )
        if idade_minima is None or resultado.idade < idade_minima:
            return None
        return {
            "motivo": MOTIVO_SUPORTE_IDOSO,
            "motivo_encerramento": MOTIVO_ENCERRAMENTO_SUPORTE_IDOSO,
            "excluir_dependente": False,
            "bloqueio_dias": 0,
        }

    if contexto_historico.get("status_dependente"):
        idade_minima = obter_idade_minima_dependente(
            contexto_historico.get("bpa_ativo_unidade")
        )

        if resultado.idade < idade_minima:
            return {
                "motivo": MOTIVO_DEPENDENTE_MENOR_5,
                "motivo_encerramento": MOTIVO_ENCERRAMENTO_IDADE_INVALIDA,
                "excluir_dependente": True,
                "bloqueio_dias": 0,
            }
        return None

    if resultado.idade < 18:
        return {
            "motivo": MOTIVO_CLIENTE_MENOR_18,
            "motivo_encerramento": MOTIVO_ENCERRAMENTO_IDADE_INVALIDA,
            "excluir_dependente": False,
            "bloqueio_dias": 0,
        }

    return None


def _resposta_bot_e_encaminhamento_suporte_idoso(contexto_historico):
    resposta_bot = (
        contexto_historico.get("resposta_bot_para_mensagem_atual") or {}
    )
    if resposta_bot.get("tipo_mensagem") != "interactive_cta_url":
        return False

    conteudo = str(resposta_bot.get("conteudo_texto") or "").strip()
    return any(
        conteudo.endswith(montar_mensagem_suporte_idoso_etapa6(limite).strip())
        for limite in IDADES_MINIMAS_SUPORTE
    )


def aplicar_encerramento_se_necessario(
    id_conversa,
    intencao_encerramento,
    cursor,
):
    if not intencao_encerramento:
        return {
            "atendimento_encerrado": False,
            "finalizou_em": None,
            "bloqueio_dias": 0,
            "motivo": None,
            "motivo_encerramento": None,
        }

    if intencao_encerramento["excluir_dependente"]:
        excluir_dependente_da_conversa(id_conversa, cursor)

    motivo_encerramento = intencao_encerramento["motivo_encerramento"]
    finalizou_em = encerrar_conversa(
        id_conversa,
        motivo_encerramento,
        cursor,
    )
    bloqueio_dias = int(
        intencao_encerramento.get("bloqueio_dias") or 0
    )

    logger.info(
        "atendimento_encerrado | acao=encerrar_conversa "
        "id_conversa=%s motivo=%s motivo_encerramento=%s "
        "dependente_excluido=%s",
        id_conversa,
        intencao_encerramento["motivo"],
        motivo_encerramento,
        intencao_encerramento["excluir_dependente"],
    )
    return {
        "atendimento_encerrado": True,
        "finalizou_em": finalizou_em,
        "bloqueio_dias": bloqueio_dias,
        "motivo": intencao_encerramento["motivo"],
        "motivo_encerramento": motivo_encerramento,
    }
```

## Parte 3 — painel e relatórios

### Passo 13 — `core/repositories/monitoramento/painel.py`

**Ação:** Alterar. Atualizar a coluna lida e agregar encaminhamentos por unidade autorizada e data de encerramento.

Conteúdo completo do arquivo:

```python
"""Consultas somente leitura do painel, sempre limitadas à unidade autorizada."""


def _linhas(cursor):
    colunas = [item[0] for item in cursor.description]
    return [dict(zip(colunas, linha)) for linha in cursor.fetchall()]


def _linha(cursor):
    colunas = [item[0] for item in cursor.description]
    valor = cursor.fetchone()
    return dict(zip(colunas, valor)) if valor else None


def _periodo(coluna, inicio, fim, parametros):
    trecho = f' AND {coluna} < %s'
    if inicio is not None:
        trecho = f' AND {coluna} >= %s' + trecho
        parametros.extend((inicio, fim))
    else:
        parametros.append(fim)
    return trecho


def buscar_unidade(id_unidade, cursor):
    cursor.execute("""
        SELECT u.id_unidade, u.nome_unidade, u.nome_agente, u.idade_minima_suporte,
               u.email_obrigatorio, u.bpa_ativo,
               MIN(CASE WHEN h.quem_enviou = 'cliente' THEN h.received_data_hora END) AS inicio_historico
          FROM chatbot.unidade u
          LEFT JOIN chatbot.conversa c ON c.id_unidade = u.id_unidade
          LEFT JOIN chatbot.historico_mensagens h ON h.id_conversa = c.id_conversa
         WHERE u.id_unidade = %s
         GROUP BY u.id_unidade, u.nome_unidade, u.nome_agente,
                  u.idade_minima_suporte, u.email_obrigatorio, u.bpa_ativo
    """, (id_unidade,))
    return _linha(cursor)


def listar_conversas(id_unidade, inicio, fim, cursor):
    p_contato = [id_unidade]
    filtro_contato = _periodo('h0.received_data_hora', inicio, fim, p_contato)
    p_funil = []
    filtro_funil = _periodo('f.enviado_em', inicio, fim, p_funil)
    p_avaliacao = []
    filtro_avaliacao = _periodo('p.criado_em', inicio, fim, p_avaliacao)
    p_atividade = []
    filtro_atividade = _periodo('h.received_data_hora', inicio, fim, p_atividade)
    cursor.execute(f"""
        WITH conversas_periodo AS (
            SELECT c.*
              FROM chatbot.conversa c
             WHERE c.id_unidade = %s
               AND EXISTS (
                   SELECT 1 FROM chatbot.historico_mensagens h0
                    WHERE h0.id_conversa = c.id_conversa
                      AND h0.quem_enviou = 'cliente' {filtro_contato}
               )
        )
        SELECT c.id_cliente, c.id_conversa, c.status_dependente,
               c.id_etapa_atual, cl.nome AS nome_cliente, cl.waid_telefone,
               cl.email, cl.idade AS idade_titular,
               cl.profissao AS profissao_cliente, c.profissao AS profissao_conversa,
               d.nome_dependente, d.idade AS idade_dependente,
               EXISTS (SELECT 1 FROM chatbot.funil_envios f
                        WHERE f.id_conversa = c.id_conversa AND f.status = 'sent'
                        {filtro_funil}) AS foi_funil,
               EXISTS (SELECT 1 FROM chatbot.pesquisa_satisfacao p
                        WHERE p.id_conversa = c.id_conversa AND p.nota IS NOT NULL
                        {filtro_avaliacao}) AS avaliada,
               (SELECT h.received_data_hora FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_atividade,
               (SELECT h.conteudo_texto FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_mensagem,
               (SELECT h.id_mensagem FROM chatbot.historico_mensagens h
                 WHERE h.id_conversa = c.id_conversa {filtro_atividade}
                   AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
                 ORDER BY h.received_data_hora DESC, h.id_mensagem DESC LIMIT 1) AS ultima_mensagem_id
          FROM conversas_periodo c
          JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
          LEFT JOIN chatbot.dependente d ON d.id_conversa = c.id_conversa
         ORDER BY ultima_atividade DESC NULLS LAST, c.id_conversa DESC
    """, tuple(
        p_contato + p_funil + p_avaliacao
        + p_atividade + p_atividade + p_atividade
    ))
    return _linhas(cursor)


def buscar_mensagens(id_unidade, id_cliente, inicio, fim, cursor):
    parametros = [id_unidade, id_cliente]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT h.id_mensagem, h.id_conversa, h.id_etapa,
               h.received_data_hora AS data, h.quem_enviou,
               h.tipo_mensagem AS tipo, h.conteudo_texto AS texto
          FROM chatbot.historico_mensagens h
          JOIN chatbot.conversa c ON c.id_conversa = h.id_conversa
         WHERE c.id_unidade = %s AND c.id_cliente = %s {filtro}
           AND (h.quem_enviou = 'cliente' OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent'))
         ORDER BY h.received_data_hora, h.id_mensagem
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_metricas(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    p_msg = []
    f_msg = _periodo('h.received_data_hora', inicio, fim, p_msg)
    p_funil = []
    f_funil = _periodo('f.enviado_em', inicio, fim, p_funil)
    p_nota = []
    f_nota = _periodo('p.criado_em', inicio, fim, p_nota)
    cursor.execute(f"""
        WITH contatos AS (
          SELECT DISTINCT c.id_cliente
            FROM chatbot.conversa c JOIN chatbot.historico_mensagens h ON h.id_conversa=c.id_conversa
           WHERE c.id_unidade=%s AND h.quem_enviou='cliente' {filtro}
        )
        SELECT (SELECT COUNT(*) FROM contatos) AS leads,
               (SELECT COUNT(*) FROM chatbot.historico_mensagens h
                 JOIN chatbot.conversa c ON c.id_conversa=h.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  {f_msg} AND (h.quem_enviou='cliente' OR (h.quem_enviou='bot' AND h.status_envio='sent'))) AS mensagens,
               (SELECT COUNT(DISTINCT c.id_cliente) FROM chatbot.funil_envios f
                 JOIN chatbot.conversa c ON c.id_conversa=f.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND f.status='sent' {f_funil}) AS funil,
               (SELECT COUNT(DISTINCT c.id_cliente) FROM chatbot.pesquisa_satisfacao p
                 JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND p.nota IS NOT NULL {f_nota}) AS avaliacoes,
               (SELECT ROUND(AVG(p.nota)::numeric,2) FROM chatbot.pesquisa_satisfacao p
                 JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
                WHERE c.id_unidade=%s AND c.id_cliente IN (SELECT id_cliente FROM contatos)
                  AND p.nota IS NOT NULL {f_nota}) AS nota_media
    """, tuple(parametros + [id_unidade] + p_msg + [id_unidade] + p_funil + [id_unidade] + p_nota + [id_unidade] + p_nota))
    return _linha(cursor)


def contar_encaminhados_comercial_por_idade(id_unidade, inicio, fim, cursor):
    """Conta o fato concluído, pela data de encerramento, sem inferir pela idade."""
    parametros = [id_unidade]
    filtro = _periodo('c.finalizou_em', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT COUNT(DISTINCT c.id_cliente)
          FROM chatbot.conversa c
         WHERE c.id_unidade = %s
           AND c.status_ativa = FALSE
           AND c.motivo_encerramento = 'encaminhado_suporte_idoso'
           AND c.finalizou_em IS NOT NULL {filtro}
    """, tuple(parametros))
    return int(cursor.fetchone()[0])


def buscar_perfis(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    parametros_funil = []
    filtro_funil = _periodo('f.enviado_em', inicio, fim, parametros_funil)
    cursor.execute(f"""
        SELECT DISTINCT c.id_cliente, c.id_conversa, c.status_dependente,
               cl.idade AS idade_titular, d.idade AS idade_dependente,
               EXISTS (SELECT 1 FROM chatbot.funil_envios f
                        WHERE f.id_conversa=c.id_conversa AND f.status='sent'
                        {filtro_funil}) AS foi_funil
          FROM chatbot.conversa c JOIN chatbot.cliente cl ON cl.id_cliente=c.id_cliente
          LEFT JOIN chatbot.dependente d ON d.id_conversa=c.id_conversa
         WHERE c.id_unidade=%s AND EXISTS (
               SELECT 1 FROM chatbot.historico_mensagens h
                WHERE h.id_conversa=c.id_conversa AND h.quem_enviou='cliente' {filtro})
    """, tuple(parametros_funil + parametros))
    return _linhas(cursor)


def buscar_satisfacao(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('p.criado_em', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT p.nota, COUNT(*) AS quantidade
          FROM chatbot.pesquisa_satisfacao p
          JOIN chatbot.conversa c ON c.id_conversa=p.id_conversa
         WHERE c.id_unidade=%s AND p.nota IS NOT NULL {filtro}
         GROUP BY p.nota ORDER BY p.nota
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_etapas(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        WITH conversas_periodo AS (
            SELECT c.id_cliente, c.id_conversa, c.id_etapa_atual,
                   MAX(h.received_data_hora) AS ultima_atividade
              FROM chatbot.conversa c
              JOIN chatbot.historico_mensagens h
                ON h.id_conversa = c.id_conversa
             WHERE c.id_unidade = %s AND h.quem_enviou = 'cliente' {filtro}
             GROUP BY c.id_cliente, c.id_conversa, c.id_etapa_atual
        ),
        ultimas_conversas AS (
            SELECT *, ROW_NUMBER() OVER (
                       PARTITION BY id_cliente
                       ORDER BY ultima_atividade DESC, id_conversa DESC
                   ) AS ordem
              FROM conversas_periodo
        )
        SELECT e.id_etapa, e.nome_etapa, COUNT(c.id_cliente) AS quantidade
          FROM chatbot.etapa e
          LEFT JOIN ultimas_conversas c
            ON c.id_etapa_atual = e.id_etapa AND c.ordem = 1
         WHERE e.id_etapa BETWEEN 1 AND 22
         GROUP BY e.id_etapa, e.nome_etapa ORDER BY e.id_etapa
    """, tuple(parametros))
    return _linhas(cursor)


def buscar_atividade(id_unidade, inicio, fim, cursor, granularidade):
    unidade_tempo = {'dia': 'day', 'semana': 'week', 'mes': 'month'}[granularidade]
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT DATE_TRUNC('{unidade_tempo}', h.received_data_hora AT TIME ZONE 'America/Sao_Paulo') AS periodo,
               COUNT(*) FILTER (WHERE h.quem_enviou='cliente' OR (h.quem_enviou='bot' AND h.status_envio='sent')) AS mensagens,
               COUNT(DISTINCT c.id_cliente) FILTER (WHERE h.quem_enviou='cliente') AS leads
          FROM chatbot.historico_mensagens h JOIN chatbot.conversa c ON c.id_conversa=h.id_conversa
         WHERE c.id_unidade=%s {filtro}
         GROUP BY 1 ORDER BY 1
    """, tuple(parametros))
    return _linhas(cursor)


def listar_contatos(id_unidade, inicio, fim, cursor):
    parametros = [id_unidade]
    filtro = _periodo('h.received_data_hora', inicio, fim, parametros)
    cursor.execute(f"""
        SELECT cl.id_cliente, cl.nome, cl.email, cl.waid_telefone
          FROM chatbot.cliente cl
         WHERE EXISTS (
             SELECT 1 FROM chatbot.conversa c
             JOIN chatbot.historico_mensagens h ON h.id_conversa=c.id_conversa
              WHERE c.id_cliente=cl.id_cliente AND c.id_unidade=%s
                AND h.quem_enviou='cliente' {filtro})
         ORDER BY cl.nome NULLS LAST, cl.id_cliente
    """, tuple(parametros))
    return _linhas(cursor)
```

### Passo 14 — `callback/monitoramento/services.py`

**Ação:** Alterar. Propagar a configuração e o total; manter os envios históricos nas faixas fixas, sem consulta extra na seção Conversas.

Conteúdo completo do arquivo:

```python
"""Orquestra leituras do painel a partir da unidade resolvida pelo guard."""

from zoneinfo import ZoneInfo

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte

from django.db import connection

from core.repositories.monitoramento import painel as repositorio

from .apresentacao import (
    botoes_para_mensagem,
    classificar_faixa,
    consolidar_conversas,
    montar_relatorio,
)


FUSO_PAINEL = ZoneInfo('America/Sao_Paulo')


def _iso(valor):
    return valor.isoformat() if hasattr(valor, 'isoformat') else valor


def _no_fuso_painel(valor):
    if valor is None:
        return None
    if valor.tzinfo is None:
        return valor.replace(tzinfo=FUSO_PAINEL)
    return valor.astimezone(FUSO_PAINEL)


def _periodo_payload(periodo, unidade):
    inicio = periodo.inicio or unidade.get('inicio_historico')
    return {
        'chave': periodo.chave,
        'rotulo': periodo.rotulo,
        'inicio': _iso(inicio),
        'fim': _iso(periodo.fim),
        'texto': (
            f"{_no_fuso_painel(inicio).strftime('%d/%m/%Y %H:%M')} até agora"
            if inicio else 'Nenhuma conversa registrada até agora'
        ),
    }


def carregar_conversas(acesso, periodo):
    with connection.cursor() as cursor:
        unidade = repositorio.buscar_unidade(acesso.id_unidade, cursor)
        linhas = repositorio.listar_conversas(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
        metricas = repositorio.buscar_metricas(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
    conversas = consolidar_conversas(linhas)
    for item in conversas:
        item['ultima_atividade'] = _iso(item['ultima_atividade'])
    metricas['nota_media'] = float(metricas['nota_media']) if metricas.get('nota_media') is not None else None
    return {
        'unidade': {
            'nome': unidade['nome_unidade'],
            'agente': unidade['nome_agente'],
            'regras': {
                'idade_minima_suporte': validar_idade_minima_suporte(unidade['idade_minima_suporte']),
                'email_obrigatorio': bool(unidade['email_obrigatorio']),
                'bpa_ativo': bool(unidade['bpa_ativo']),
            },
        },
        'periodo': _periodo_payload(periodo, unidade),
        'metricas': metricas,
        'conversas': conversas,
        'atualizado_em': _iso(periodo.fim),
    }


def carregar_mensagens(acesso, id_cliente, periodo):
    with connection.cursor() as cursor:
        linhas = repositorio.buscar_mensagens(
            acesso.id_unidade, id_cliente, periodo.inicio, periodo.fim, cursor
        )
    mensagens = []
    for linha in linhas:
        item = {
            'id_mensagem': linha['id_mensagem'],
            'id_conversa': linha['id_conversa'],
            'id_etapa': linha['id_etapa'],
            'data': _iso(linha['data']),
            'quem_enviou': linha['quem_enviou'],
            'tipo': linha['tipo'],
            'texto': linha['texto'] or f"[{linha['tipo'] or 'mensagem sem texto'}]",
        }
        item['botoes'] = botoes_para_mensagem(item)
        mensagens.append(item)
    return {'id_cliente': id_cliente, 'mensagens': mensagens}


def _agrupar_perfis(linhas, *, bpa_ativo):
    minimo = 4 if bpa_ativo else 5
    chaves = ('dependente_menor', 'dependente_adulto', 'dependente_idoso', 'titular_adulto', 'titular_idoso')
    acumulado = {chave: {'clientes': set(), 'conversas': 0, 'funil': set()} for chave in chaves}
    todos_clientes = set()
    clientes_classificados = set()
    for linha in linhas:
        id_cliente = linha['id_cliente']
        todos_clientes.add(id_cliente)
        status_dependente = linha.get('status_dependente')
        if status_dependente not in (True, False) or type(status_dependente) is not bool:
            continue
        dependente = status_dependente is True
        idade = linha.get('idade_dependente') if dependente else linha.get('idade_titular')
        faixa = classificar_faixa(idade)
        if dependente and faixa == 'menor' and idade >= minimo:
            chave = 'dependente_menor'
        elif dependente and faixa in ('adulto', 'idoso'):
            chave = 'dependente_' + faixa
        elif not dependente and faixa in ('adulto', 'idoso'):
            chave = 'titular_' + faixa
        else:
            continue
        alvo = acumulado[chave]
        alvo['clientes'].add(id_cliente)
        alvo['conversas'] += 1
        clientes_classificados.add(id_cliente)
        if linha.get('foi_funil'):
            alvo['funil'].add(id_cliente)
    rotulos = {
        'dependente_menor': f'Dependentes de {minimo} a 17 anos',
        'dependente_adulto': 'Dependentes de 18 a 59 anos',
        'dependente_idoso': 'Dependentes com 60 anos ou mais',
        'titular_adulto': 'Titulares de 18 a 59 anos',
        'titular_idoso': 'Titulares com 60 anos ou mais',
    }
    resposta = []
    for chave in chaves:
        item = acumulado[chave]
        leads = len(item['clientes'])
        funil = len(item['funil'])
        resposta.append({
            'chave': chave, 'rotulo': rotulos[chave], 'leads': leads,
            'conversas': item['conversas'], 'funil': funil,
            'taxa_funil': round(funil / leads * 100, 1) if leads else 0,
            'funil_nao_aplicavel': False,
        })
    return {
        'linhas': resposta,
        'sem_classificacao': len(todos_clientes - clientes_classificados),
        'idade_minima_dependente': minimo,
    }


def _granularidade(periodo, unidade):
    inicio = periodo.inicio or unidade.get('inicio_historico')
    if not inicio:
        return 'dia'
    dias = (periodo.fim - inicio).days
    return 'mes' if dias > 180 else 'semana' if dias > 60 else 'dia'


def carregar_relatorio(acesso, periodo):
    with connection.cursor() as cursor:
        unidade = repositorio.buscar_unidade(acesso.id_unidade, cursor)
        metricas = repositorio.buscar_metricas(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        encaminhados = repositorio.contar_encaminhados_comercial_por_idade(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
        anteriores = None
        if periodo.inicio_anterior is not None:
            anteriores = repositorio.buscar_metricas(
                acesso.id_unidade, periodo.inicio_anterior, periodo.fim_anterior, cursor
            )
        perfis_brutos = repositorio.buscar_perfis(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        satisfacao_bruta = repositorio.buscar_satisfacao(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        etapas = repositorio.buscar_etapas(acesso.id_unidade, periodo.inicio, periodo.fim, cursor)
        atividade = repositorio.buscar_atividade(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor,
            _granularidade(periodo, unidade),
        )
    for grupo in (metricas, anteriores or {}):
        if grupo.get('nota_media') is not None:
            grupo['nota_media'] = float(grupo['nota_media'])
    satisfacao = {str(nota): 0 for nota in range(1, 6)}
    for linha in satisfacao_bruta:
        satisfacao[str(linha['nota'])] = linha['quantidade']
    for linha in etapas:
        linha['quantidade'] = int(linha['quantidade'])
    for linha in atividade:
        # DATE_TRUNC sobre AT TIME ZONE devolve timestamp sem fuso. O offset
        # explícito impede o navegador de interpretar o agrupamento como UTC.
        linha['periodo'] = _iso(_no_fuso_painel(linha['periodo']))
    relatorio = montar_relatorio(
        metricas, anteriores,
        _agrupar_perfis(
            perfis_brutos,
            bpa_ativo=bool(unidade['bpa_ativo']),
        ),
        satisfacao, etapas, atividade,
        encaminhados_comercial_por_idade=encaminhados,
    )
    relatorio.update({
        'unidade': {
            'nome': unidade['nome_unidade'],
            'idade_minima_suporte': validar_idade_minima_suporte(unidade['idade_minima_suporte']),
        },
        'periodo': _periodo_payload(periodo, unidade),
        'atualizado_em': _iso(periodo.fim),
    })
    return relatorio


def carregar_contatos(acesso, periodo):
    with connection.cursor() as cursor:
        return repositorio.listar_contatos(
            acesso.id_unidade, periodo.inicio, periodo.fim, cursor
        )
```

### Passo 15 — `callback/monitoramento/apresentacao.py`

**Ação:** Alterar. Incluir o inteiro validado no payload do relatório, preservando classificação e CSVs.

Conteúdo completo do arquivo:

```python
"""Transformações puras dos dados do painel, sem acesso ao banco."""

import re

from core.integrations.whatsapp.messages.etapa2_messages import montar_botoes_etapa2
from core.integrations.whatsapp.messages.etapa3_messages import montar_botoes_etapa3
from core.integrations.whatsapp.messages.etapa7_messages import montar_botoes_etapa7
from core.integrations.whatsapp.messages.etapa9_messages import montar_botoes_etapa9
from core.integrations.whatsapp.messages.etapa11_messages import montar_botoes_etapa11
from core.integrations.whatsapp.messages.etapa18_messages import montar_botoes_etapa18
from core.integrations.whatsapp.messages.etapa19_messages import montar_opcoes_satisfacao_etapa19
from core.integrations.whatsapp.messages.etapa20_messages import montar_botoes_etapa20
from core.integrations.whatsapp.messages.triagem_componentes import montar_botoes_triagem


_BOTOES_POR_ETAPA = {
    2: montar_botoes_etapa2,
    3: montar_botoes_etapa3,
    7: montar_botoes_etapa7,
    9: montar_botoes_etapa9,
    11: montar_botoes_etapa11,
    12: montar_botoes_triagem,
    13: montar_botoes_triagem,
    14: montar_botoes_triagem,
    15: montar_botoes_triagem,
    16: montar_botoes_triagem,
    17: montar_botoes_triagem,
    18: montar_botoes_etapa18,
    19: lambda: [titulo for _, titulo in montar_opcoes_satisfacao_etapa19()],
    20: montar_botoes_etapa20,
}


# Ordem e grafia do modelo CSV distribuído pelo Google Contacts.
CABECALHO_CSV_GOOGLE_CONTATOS = (
    'Name Prefix',
    'First Name',
    'Middle Name',
    'Last Name',
    'Name Suffix',
    'Phonetic First Name',
    'Phonetic Middle Name',
    'Phonetic Last Name',
    'Nickname',
    'File As',
    'E-mail 1 - Label',
    'E-mail 1 - Value',
    'Phone 1 - Label',
    'Phone 1 - Value',
    'Address 1 - Label',
    'Address 1 - Country',
    'Address 1 - Street',
    'Address 1 - Extended Address',
    'Address 1 - City',
    'Address 1 - Region',
    'Address 1 - Postal Code',
    'Address 1 - PO Box',
    'Organization Name',
    'Organization Title',
    'Organization Department',
    'Birthday',
    'Event 1 - Label',
    'Event 1 - Value',
    'Relation 1 - Label',
    'Relation 1 - Value',
    'Website 1 - Label',
    'Website 1 - Value',
    'Custom Field 1 - Label',
    'Custom Field 1 - Value',
    'Notes',
    'Labels',
)


def botoes_para_mensagem(mensagem):
    tipo = str(mensagem.get('tipo') or '')
    if mensagem.get('quem_enviou') != 'bot' or not tipo.startswith('interactive'):
        return []
    fabrica = _BOTOES_POR_ETAPA.get(mensagem.get('id_etapa'))
    return list(fabrica()) if fabrica else []


def classificar_faixa(idade):
    if type(idade) is not int or idade <= 0 or idade >= 100:
        return None
    if idade < 18:
        return 'menor'
    if idade < 60:
        return 'adulto'
    return 'idoso'


def _perfil_resumido(status_dependente, faixa):
    if status_dependente is True:
        return f'dependente_{faixa}' if faixa else 'dependente'
    if status_dependente is False:
        return faixa
    return None


def consolidar_conversas(linhas):
    clientes = {}
    for linha in linhas:
        cliente = clientes.setdefault(linha['id_cliente'], {
            'id_cliente': linha['id_cliente'],
            'nome': linha.get('nome_cliente') or 'Cliente sem nome',
            'contato': linha.get('waid_telefone') or '',
            'email': linha.get('email') or '',
            'profissao': linha.get('profissao_cliente') or linha.get('profissao_conversa') or '',
            'ids_conversa': [], 'perfis': set(), 'perfis_resumidos': set(),
            'dependentes': set(),
            'foi_funil': False, 'avaliada': False,
            'ultima_atividade': None, 'ultima_mensagem': '',
            'ultima_mensagem_id': None,
        })
        cliente['ids_conversa'].append(linha['id_conversa'])
        cliente['foi_funil'] |= bool(linha.get('foi_funil'))
        cliente['avaliada'] |= bool(linha.get('avaliada'))
        status_dependente = linha.get('status_dependente')
        dependente = status_dependente is True
        if dependente:
            cliente['perfis'].add('dependente')
            if linha.get('nome_dependente'):
                cliente['dependentes'].add(str(linha['nome_dependente']))
        idade = (
            linha.get('idade_dependente') if dependente
            else linha.get('idade_titular') if status_dependente is False
            else None
        )
        faixa = classificar_faixa(idade)
        if faixa:
            cliente['perfis'].add(faixa)
        perfil_resumido = _perfil_resumido(status_dependente, faixa)
        if perfil_resumido:
            cliente['perfis_resumidos'].add(perfil_resumido)
        atividade = linha.get('ultima_atividade')
        id_mensagem = linha.get('ultima_mensagem_id') or 0
        if atividade and (
            cliente['ultima_atividade'] is None
            or atividade > cliente['ultima_atividade']
            or (
                atividade == cliente['ultima_atividade']
                and id_mensagem > (cliente['ultima_mensagem_id'] or 0)
            )
        ):
            cliente['ultima_atividade'] = atividade
            cliente['ultima_mensagem'] = linha.get('ultima_mensagem') or ''
            cliente['ultima_mensagem_id'] = linha.get('ultima_mensagem_id')
    ordem = {'dependente': 0, 'menor': 1, 'adulto': 2, 'idoso': 3}
    ordem_resumida = {
        'dependente_menor': 0,
        'dependente_adulto': 1,
        'dependente_idoso': 2,
        'menor': 3,
        'adulto': 4,
        'idoso': 5,
        'dependente': 6,
    }
    for cliente in clientes.values():
        cliente['ids_conversa'].sort()
        cliente['perfis'] = sorted(cliente['perfis'], key=lambda item: ordem[item])
        cliente['perfis_resumidos'] = sorted(
            cliente['perfis_resumidos'], key=lambda item: ordem_resumida[item]
        )
        cliente['dependentes'] = sorted(cliente['dependentes'])
    return sorted(clientes.values(), key=lambda item: item['ultima_atividade'] or '', reverse=True)


def normalizar_telefone_google(valor):
    digitos = re.sub(r'\D', '', str(valor or ''))
    if len(digitos) in (10, 11):
        digitos = '55' + digitos
    if not re.fullmatch(r'[1-9]\d{7,14}', digitos):
        return ''
    return '+' + digitos


def separar_nome(valor):
    partes = str(valor or '').strip().split()
    if not partes:
        return '', ''
    return partes[0], ' '.join(partes[1:])


def proteger_celula_csv(valor):
    texto = str(valor or '')
    return "'" + texto if texto.startswith(('=', '+', '-', '@')) else texto


CABECALHO_CSV_ESSENCIAL = ('Nome', 'E-mail', 'Telefone')


def montar_linha_csv_essencial(*, primeiro_nome, sobrenome, email, telefone):
    """Mantém o nome completo em uma coluna, sem acrescentar rótulos comerciais."""
    nome = ' '.join(parte for parte in (primeiro_nome, sobrenome) if parte)
    # O telefone já está normalizado; remove só o código do Brasil, mantendo o DDD.
    telefone_essencial = telefone.removeprefix('+55')
    return [proteger_celula_csv(nome), proteger_celula_csv(email), telefone_essencial]


def montar_linha_csv_google_contatos(
    *,
    primeiro_nome,
    sobrenome,
    email,
    telefone,
    nome_unidade,
):
    """Posiciona os dados nas colunas exatas do modelo do Google Contacts."""
    valores = {
        'First Name': proteger_celula_csv(primeiro_nome),
        'Last Name': proteger_celula_csv(sobrenome),
        'E-mail 1 - Label': 'Work' if email else '',
        'E-mail 1 - Value': proteger_celula_csv(email),
        'Phone 1 - Label': 'Mobile' if telefone else '',
        'Phone 1 - Value': telefone,
        'Notes': 'Contato exportado pelo monitoramento ESL Tech',
        'Labels': proteger_celula_csv(nome_unidade),
    }
    return [valores.get(coluna, '') for coluna in CABECALHO_CSV_GOOGLE_CONTATOS]


def montar_relatorio(
    metricas, anteriores, perfis, satisfacao, etapas, atividade,
    *, encaminhados_comercial_por_idade,
):
    if type(encaminhados_comercial_por_idade) is not int or encaminhados_comercial_por_idade < 0:
        raise ValueError('Total de encaminhamentos inválido')
    def variacao(atual, anterior):
        if atual is None or anterior is None:
            return None
        if anterior == 0:
            return 100.0 if atual else 0.0
        return round((atual - anterior) / anterior * 100, 1)
    tendencias = {}
    for chave in ('leads', 'mensagens', 'funil', 'avaliacoes', 'nota_media'):
        tendencias[chave] = variacao(metricas.get(chave, 0), anteriores.get(chave) if anteriores else None)
    return {
        'metricas': metricas,
        'encaminhados_comercial_por_idade': encaminhados_comercial_por_idade,
        'tendencias': tendencias,
        'perfis': perfis,
        'satisfacao': satisfacao,
        'etapas': etapas,
        'atividade': atividade,
    }
```

### Passo 16 — `callback/monitoramento/static/monitoramento/js/painel.js`

**Ação:** Alterar. Renderizar o indicador e a política atual, atualizar a explicação e preservar as tags e downloads.

Conteúdo completo do arquivo:

```javascript
(() => {
  'use strict';
  const corpo=document.body, ids=id=>document.getElementById(id);
  const urls={conversas:corpo.dataset.urlConversas,mensagens:corpo.dataset.urlMensagens,relatorio:corpo.dataset.urlRelatorio,csv:corpo.dataset.urlCsv,login:corpo.dataset.urlLogin};
  const estado={secao:'conversas',periodo:'total',filtro:'todas',busca:'',conversas:[],selecionada:null,regras:{},carregandoConversas:false,recarregarConversas:false,carregandoRelatorio:false,recarregarRelatorio:false,sequenciaConversas:0,sequenciaRelatorio:0};
  const criar=(tag,classe='',texto='')=>{const n=document.createElement(tag);if(classe)n.className=classe;if(texto!==''&&texto!==null)n.textContent=texto;return n;};
  const numero=new Intl.NumberFormat('pt-BR'), data=new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeZone:'America/Sao_Paulo'}), dia=new Intl.DateTimeFormat('pt-BR',{dateStyle:'long',timeZone:'America/Sao_Paulo'}), hora=new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'}), curto=new Intl.DateTimeFormat('pt-BR',{day:'2-digit',month:'short',timeZone:'America/Sao_Paulo'});
  const cores=['#37663d','#5d568f','#a35b38','#44758a','#8a4f67','#4d7468','#7b683b'];
  async function json(url){const a=new AbortController(),t=setTimeout(()=>a.abort(),15000);try{const r=await fetch(url,{headers:{Accept:'application/json'},credentials:'same-origin',cache:'no-store',signal:a.signal});let d={};try{d=await r.json();}catch(_e){}if(r.status===401){location.assign(urls.login);throw new Error('Sessão expirada.');}if(!r.ok)throw new Error(d.erro||'Não foi possível carregar os dados.');return d;}finally{clearTimeout(t);}}
  const urlPeriodo=(base,periodo=estado.periodo)=>base+'?periodo='+encodeURIComponent(periodo);
  function status(texto,tipo=''){const n=ids('estadoAtualizacao');n.className='estado-atualizacao '+tipo;n.lastChild.textContent=texto;}
  function toast(texto){const n=ids('toast');n.textContent=texto;n.hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>n.hidden=true,4500);}
  const iniciais=nome=>(nome||'?').split(/\s+/).slice(0,2).map(p=>p[0]||'').join('').toUpperCase();
  const cor=id=>cores[Math.abs(Number(id)||0)%cores.length];
  const perfil=p=>({dependente:'Dependente',menor:'Menor de 18',adulto:'Adulto',idoso:'60+'}[p]||p);
  const perfisResumidos={
    dependente_menor:{curto:'DP -18',completo:'Dependente menor de 18 anos'},
    dependente_adulto:{curto:'DP 18–59',completo:'Dependente de 18 a 59 anos'},
    dependente_idoso:{curto:'DP 60+',completo:'Dependente com 60 anos ou mais'},
    dependente:{curto:'DP',completo:'Dependente sem faixa etária informada'},
    menor:{curto:'-18',completo:'Titular menor de 18 anos'},
    adulto:{curto:'18–59',completo:'Titular de 18 a 59 anos'},
    idoso:{curto:'60+',completo:'Titular com 60 anos ou mais'},
  };
  function visivel(i){if(estado.filtro==='continuacoes'&&i.ids_conversa.length<2)return false;if(estado.filtro==='funil'&&!i.foi_funil)return false;if(estado.filtro==='avaliadas'&&!i.avaliada)return false;const b=estado.busca.trim().toLocaleLowerCase('pt-BR');return !b||[i.nome,i.contato,i.email,i.profissao,i.ultima_mensagem,...i.dependentes].filter(Boolean).join(' ').toLocaleLowerCase('pt-BR').includes(b);}
  function mini(pai,texto,classe=''){pai.appendChild(criar('span','mini-tag '+classe,texto));}
  function renderLista(){
    const lista=ids('listaConversas');
    const itens=estado.conversas.filter(visivel);
    lista.replaceChildren();

    if(!itens.length){
      lista.appendChild(criar('div','estado-vazio',estado.conversas.length?'Nenhum contato corresponde à pesquisa ou filtro.':'Nenhuma conversa neste período.'));
      return;
    }

    itens.forEach(item=>{
      const botao=criar('button','item-conversa');
      const avatar=criar('div','avatar',iniciais(item.nome));
      const corpo=criar('div','item-corpo');
      const cabecalho=criar('div','item-linha');
      const metadados=criar('span','item-metadados');
      const perfisResumo=criar('span','perfis-resumidos-item');
      const dataAtividade=criar('time','',item.ultima_atividade?data.format(new Date(item.ultima_atividade)):'—');

      botao.type='button';
      botao.dataset.cliente=String(item.id_cliente);
      if(estado.selecionada===item.id_cliente)botao.classList.add('ativo');
      avatar.style.background=cor(item.id_cliente);

      (item.perfis_resumidos||[]).forEach(chave=>{
        const classe=chave.replaceAll('_','-');
        const perfilAtual=perfisResumidos[chave]||{curto:chave,completo:chave};
        const etiqueta=criar('span','mini-tag perfil-resumido '+classe,perfilAtual.curto);
        etiqueta.title=perfilAtual.completo;
        etiqueta.setAttribute('aria-label',perfilAtual.completo);
        perfisResumo.appendChild(etiqueta);
      });
      if(perfisResumo.childElementCount)metadados.appendChild(perfisResumo);
      metadados.appendChild(dataAtividade);
      cabecalho.append(criar('strong','',item.nome),metadados);
      corpo.append(cabecalho,criar('div','item-previa',item.ultima_mensagem||'Sem conteúdo textual'));

      const tags=criar('div','mini-tags');
      if(item.ids_conversa.length>1)mini(tags,item.ids_conversa.length+' conversas');
      if(item.foi_funil)mini(tags,'Funil','funil');
      if(item.avaliada)mini(tags,'Avaliada','nota');
      corpo.appendChild(tags);
      botao.append(avatar,corpo);
      botao.addEventListener('click',()=>abrir(item.id_cliente));
      lista.appendChild(botao);
    });
  }
  function detalhes(i){ids('nomeContato').textContent=i.nome;ids('avatarContato').textContent=iniciais(i.nome);ids('avatarContato').style.background=cor(i.id_cliente);const r=[];if(i.contato)r.push('Contato: '+i.contato);if(i.profissao)r.push('Profissão: '+i.profissao);ids('detalhesContato').textContent=r.join(' • ')||'Dados ainda não informados';const tags=ids('tagsContato');tags.replaceChildren();i.perfis.forEach(p=>tags.appendChild(criar('span','tag-contato '+p,perfil(p))));if(i.foi_funil)tags.appendChild(criar('span','tag-contato funil','Funil'));const dl=criar('dl'),campos=[['Contato',i.contato||'Não informado'],['Profissão',i.profissao||'Não informada']];if(estado.regras.email_obrigatorio||i.email)campos.push(['E-mail',i.email||'Obrigatório · não informado']);if(i.dependentes.length)campos.push(['Dependente(s)',i.dependentes.join(', ')]);campos.push(['Conversas técnicas',i.ids_conversa.join(', ')]);campos.push(['Regras da unidade',[estado.regras.email_obrigatorio?'E-mail obrigatório':'E-mail opcional',politicaSuporte(estado.regras.idade_minima_suporte),estado.regras.bpa_ativo?'BPA ativo':'BPA inativo'].join(' · ')]);campos.forEach(([t,v])=>{const g=criar('div');g.append(criar('dt','',t),criar('dd','',v));dl.appendChild(g);});ids('painelDetalhes').replaceChildren(dl);}
  function marca(){const c=criar('div','marca-dagua');c.setAttribute('aria-hidden','true');const i=document.querySelector('.marca-app img').cloneNode();i.alt='';c.appendChild(i);return c;}
  function renderMensagens(ms,{manter=false}={}){const c=ids('mensagensChat'),final=c.scrollHeight-c.scrollTop-c.clientHeight<120,topo=c.scrollTop;c.replaceChildren(marca());let d='',conv=null;ms.forEach(m=>{const dt=new Date(m.data),nd=dia.format(dt);if(nd!==d){c.appendChild(criar('div','dia',nd));d=nd;}if(conv!==m.id_conversa){c.appendChild(criar('div','separador-conversa',(conv===null?'Início':'Continuação')+' do atendimento · conversa '+m.id_conversa));conv=m.id_conversa;}const l=criar('div','linha-mensagem '+(m.quem_enviou==='bot'?'bot':'cliente')),b=criar('div','bolha');if(m.tipo&&m.tipo!=='text')b.appendChild(criar('span','tipo-mensagem',m.tipo.replaceAll('_',' ')));b.appendChild(criar('div','texto-mensagem',m.texto));if(m.botoes?.length){const bs=criar('div','botoes-mensagem');m.botoes.forEach(x=>{const bt=criar('button','botao-mensagem',x);bt.type='button';bt.disabled=true;bt.setAttribute('aria-label',x+' (botão histórico)');bs.appendChild(bt);});b.appendChild(bs);}const mt=criar('div','meta-mensagem');mt.appendChild(criar('span','','Etapa '+(m.id_etapa??'—')+' · '+hora.format(dt)));if(m.quem_enviou==='bot')mt.appendChild(criar('span','ticks','✓✓'));b.appendChild(mt);l.appendChild(b);c.appendChild(l);});if(!ms.length)c.appendChild(criar('div','boas-vindas','Nenhuma mensagem visível no período.'));requestAnimationFrame(()=>{if(!manter||final)c.scrollTop=c.scrollHeight;else c.scrollTop=topo;});}
  async function abrir(idCliente,{silencioso=false}={}){const i=estado.conversas.find(c=>c.id_cliente===idCliente);if(!i)return;const periodo=estado.periodo;estado.selecionada=idCliente;renderLista();detalhes(i);ids('topoChat').hidden=false;document.querySelector('.app-conversas').classList.add('chat-aberto');const c=ids('mensagensChat');if(!silencioso)c.replaceChildren(marca(),criar('div','estado-vazio carregando','Carregando histórico…'));try{const d=await json(urls.mensagens+idCliente+'/?periodo='+encodeURIComponent(periodo));if(estado.selecionada===idCliente&&estado.periodo===periodo)renderMensagens(d.mensagens,{manter:silencioso});}catch(e){if(estado.periodo!==periodo)return;if(!silencioso)c.replaceChildren(marca(),criar('div','estado-vazio',e.message));else toast('Não foi possível atualizar a conversa agora.');}}
  async function carregarConversas(silencioso=false){if(estado.carregandoConversas){estado.recarregarConversas=true;return;}estado.carregandoConversas=true;const periodo=estado.periodo,seq=++estado.sequenciaConversas;if(estado.secao==='conversas')status('Atualizando…','atualizando');try{const d=await json(urlPeriodo(urls.conversas,periodo));if(seq!==estado.sequenciaConversas||periodo!==estado.periodo)return;const velha=estado.conversas.find(c=>c.id_cliente===estado.selecionada);estado.conversas=d.conversas;estado.regras=d.unidade.regras;ids('nomeUnidade').textContent=d.unidade.nome;ids('periodoConversas').textContent='Agente '+d.unidade.agente+' · '+d.periodo.texto;renderLista();const nova=estado.conversas.find(c=>c.id_cliente===estado.selecionada);if(nova&&(!silencioso||!velha||nova.ultima_mensagem_id!==velha.ultima_mensagem_id||nova.ultima_atividade!==velha.ultima_atividade))await abrir(nova.id_cliente,{silencioso});else if(!estado.selecionada&&matchMedia('(min-width:721px)').matches&&estado.conversas[0])await abrir(estado.conversas[0].id_cliente);if(estado.secao==='conversas')status('Atualizado agora');}catch(e){if(seq!==estado.sequenciaConversas||periodo!==estado.periodo)return;if(estado.secao==='conversas')status('Falha ao atualizar','erro');if(!silencioso)ids('listaConversas').replaceChildren(criar('div','estado-vazio',e.message));else toast(e.message);}finally{estado.carregandoConversas=false;if(estado.recarregarConversas){estado.recarregarConversas=false;void carregarConversas(true);}}}
  function tend(v){if(v==null)return['Histórico completo',''];if(v===0)return['Sem variação ante o período anterior',''];return[(v>0?'↑ ':'↓ ')+Math.abs(v).toLocaleString('pt-BR')+'% ante o período anterior',v>0?'positiva':'negativa'];}
  function kpi(rotulo,valor,v){const c=criar('article','cartao kpi'),t=tend(v);c.append(criar('span','rotulo',rotulo),criar('strong','',valor),criar('span','tendencia '+t[1],t[0]));return c;}
  function titulo(t,d,l=''){const h=criar('header','titulo-cartao'),x=criar('div');x.append(criar('h2','',t),criar('p','',d));h.appendChild(x);if(l)h.appendChild(criar('span','legenda',l));return h;}
  function atividade(ds){
    const componente=criar('div','grafico-atividade');
    if(!ds.length){
      componente.appendChild(criar('div','estado-vazio','Sem atividade no período.'));
      return componente;
    }

    const resumo=criar('p','grafico-resumo','Toque em uma barra para ver data, leads e mensagens.');
    resumo.setAttribute('aria-live','polite');
    const rolagem=criar('div','grafico-rolagem');
    const barras=criar('div','grafico-barras');
    const maximo=Math.max(1,...ds.flatMap(item=>[Number(item.leads)||0,Number(item.mensagens)||0]));

    ds.forEach((item,indice)=>{
      const leads=Number(item.leads)||0;
      const mensagens=Number(item.mensagens)||0;
      const dataCurta=curto.format(new Date(item.periodo));
      const descricao=dataCurta+': '+numero.format(leads)+' leads e '+numero.format(mensagens)+' mensagens';
      const coluna=criar('button','coluna-grafico');
      const barraLeads=criar('i');
      const barraMensagens=criar('i','barra-mensagens');

      coluna.type='button';
      coluna.title=descricao;
      coluna.setAttribute('aria-label',descricao);
      barraLeads.style.height=Math.max(2,leads/maximo*100)+'%';
      barraMensagens.style.height=Math.max(2,mensagens/maximo*100)+'%';
      coluna.append(barraLeads,barraMensagens);

      if(ds.length<35||indice%Math.ceil(ds.length/16)===0){
        coluna.appendChild(criar('span','rotulo-data',dataCurta));
      }

      const mostrarResumo=()=>{resumo.textContent=descricao;};
      coluna.addEventListener('click',mostrarResumo);
      coluna.addEventListener('focus',mostrarResumo);
      coluna.addEventListener('mouseenter',mostrarResumo);
      barras.appendChild(coluna);
    });

    rolagem.appendChild(barras);
    componente.append(resumo,rolagem);
    return componente;
  }
  function satisfacao(ds){const c=criar('article','cartao');c.appendChild(titulo('Satisfação','Distribuição das notas registradas.'));const b=criar('div','barras-satisfacao'),max=Math.max(1,...Object.values(ds).map(Number));[5,4,3,2,1].forEach(n=>{const q=Number(ds[String(n)]||0),l=criar('div','barra-linha'),tr=criar('div','trilho'),i=criar('i');i.style.width=q/max*100+'%';tr.appendChild(i);l.append(criar('span','',n+' ★'),tr,criar('strong','',String(q)));b.appendChild(l);});c.appendChild(b);return c;}
  function perfis(ds){
    const colunas=['Perfil','Leads','Conversas','Funil','Taxa'];
    const cartao=criar('article','cartao');
    const tabela=criar('table','tabela-perfis');
    const cabecalho=criar('thead');
    const linhaCabecalho=criar('tr');

    cartao.appendChild(titulo('Perfil dos atendimentos','Faixas atuais; dependentes a partir de '+ds.idade_minima_dependente+' anos.'));
    colunas.forEach(coluna=>linhaCabecalho.appendChild(criar('th','',coluna)));
    cabecalho.appendChild(linhaCabecalho);
    tabela.appendChild(cabecalho);

    const corpoTabela=criar('tbody');
    ds.linhas.forEach(item=>{
      const linha=criar('tr');
      const valores=[
        item.rotulo,
        item.leads,
        item.conversas,
        item.funil,
        item.taxa_funil==null?'—':item.taxa_funil.toLocaleString('pt-BR')+'%',
      ];

      valores.forEach((valor,indice)=>{
        const celula=criar('td','',String(valor));
        celula.dataset.rotulo=colunas[indice];
        linha.appendChild(celula);
      });
      corpoTabela.appendChild(linha);
    });

    tabela.appendChild(corpoTabela);
    cartao.appendChild(tabela);
    if(ds.sem_classificacao){
      cartao.appendChild(criar('p','tendencia',ds.sem_classificacao+' lead(s) sem classificação etária completa.'));
    }
    return cartao;
  }
  function etapas(ds){const c=criar('article','cartao');c.appendChild(titulo('Onde os atendimentos estão','Etapa atual da conversa mais recente de cada contato ativo no período.','22 etapas'));const lista=criar('div','etapas-lista'),max=Math.max(1,...ds.map(e=>Number(e.quantidade)));ds.forEach(e=>{const l=criar('div','etapa-linha'),tr=criar('div','trilho'),i=criar('i');i.style.width=Number(e.quantidade)/max*100+'%';tr.appendChild(i);l.append(criar('span','etapa-numero',String(e.id_etapa)),criar('span','etapa-nome',e.nome_etapa),tr,criar('strong','',String(e.quantidade)));lista.appendChild(l);});c.appendChild(lista);return c;}
  function exportacao(formato='google'){
    const essencial=formato==='essencial';
    const cartao=criar('article','cartao exportacao');
    const descricao=criar('div');
    const botoes=criar('div','botoes-download');
    const titulo=essencial?'Baixe os dados essenciais':'Leve os contatos para o Google Contatos';
    const explicacao=essencial
      ?'CSV com apenas Nome, E-mail e Telefone do período selecionado. O nome completo fica em uma coluna. Elegíveis possuem os três dados; campos ausentes ficam vazios no arquivo completo.'
      :'Arquivos no formato Google CSV. Elegíveis possuem nome, e-mail e telefone; campos ausentes ficam vazios no arquivo completo. Para mais de 3.000 contatos, escolha períodos menores antes de importar no Google.';

    descricao.append(criar('h2','',titulo),criar('p','',explicacao));
    [['Baixar todos os contatos','todos'],['Baixar apenas elegíveis','elegiveis']].forEach(([texto,tipo])=>{
      const link=criar('a','botao-download'+(tipo==='elegiveis'?' primario':''),texto);
      const parametros=new URLSearchParams({periodo:estado.periodo,tipo});
      if(essencial)parametros.set('formato','essencial');
      link.href=urls.csv+'?'+parametros;
      link.setAttribute('aria-label',texto+' — '+(essencial?'CSV essencial':'Google CSV'));
      botoes.appendChild(link);
    });
    cartao.append(descricao,botoes);
    return cartao;
  }
  function politicaSuporte(limite){
    return limite===null?'Encaminhamento por idade: desativado':'Encaminhamento ao comercial: '+limite+'+';
  }
  function encaminhamentos(d){
    if(!Number.isSafeInteger(d.encaminhados_comercial_por_idade)||d.encaminhados_comercial_por_idade<0){
      throw new Error('Não foi possível obter o total de encaminhamentos.');
    }
    const cartao=criar('article','cartao indicador-comercial');
    const descricao=criar('div');
    descricao.append(
      criar('h2','','Encaminhados ao comercial'),
      criar('p','','Leads únicos encaminhados por suporte de idade no período'),
      criar('p','politica-suporte',politicaSuporte(d.unidade.idade_minima_suporte)),
    );
    cartao.append(descricao,criar('strong','total-comercial',numero.format(d.encaminhados_comercial_por_idade)));
    return cartao;
  }
  function interpretar(m){const c=criar('article','cartao como-interpretar');c.appendChild(criar('h2','','Como interpretar os números'));const ul=criar('ul');['Lead é um contato único que enviou mensagem no período selecionado.','Funil é um envio confirmado no registro local; não confirma agendamento ou venda.','Encaminhados ao comercial conta leads únicos pelo encerramento por suporte de idade no período, inclusive históricos. Não confirma clique, atendimento humano, matrícula ou venda; não inclui o tratamento de 100+. A data considerada é a do encaminhamento, e não a da mensagem recebida.','A comparação usa a janela imediatamente anterior com a mesma duração. O histórico total não possui comparação.','A etapa mostra o estado atual da conversa mais recente de cada contato ativo no período; não reconstrói a etapa histórica daquele dia.','Participação em avaliações: '+(m.leads?Math.round((m.avaliacoes||0)/m.leads*1000)/10:0)+'% dos leads.'].forEach(x=>ul.appendChild(criar('li','',x)));c.appendChild(ul);return c;}
  function renderRelatorio(d){
    ids('periodoRelatorios').textContent=d.periodo.texto;
    const relatorio=ids('conteudoRelatorio');
    const metricasRelatorio=d.metricas;
    const tendencias=d.tendencias;
    const gradeKpis=criar('div','grade-kpis');
    const gradeRelatorio=criar('div','grade-relatorio');
    const cartaoAtividade=criar('article','cartao');
    const instrucaoGrafico=matchMedia('(hover: none)').matches
      ?'Toque nas barras para ver cada valor. Deslize para consultar outras datas.'
      :'Passe o cursor sobre as barras para ver cada valor.';

    relatorio.replaceChildren();
    gradeKpis.append(
      kpi('Leads em contato',numero.format(metricasRelatorio.leads||0),tendencias.leads),
      kpi('Mensagens',numero.format(metricasRelatorio.mensagens||0),tendencias.mensagens),
      kpi('Enviados ao funil',numero.format(metricasRelatorio.funil||0),tendencias.funil),
      kpi('Nota média',metricasRelatorio.nota_media==null?'—':Number(metricasRelatorio.nota_media).toLocaleString('pt-BR')+' / 5',tendencias.nota_media),
    );
    cartaoAtividade.append(
      titulo('Evolução da demanda',instrucaoGrafico,'Verde: leads · Lima: mensagens'),
      atividade(d.atividade),
    );
    gradeRelatorio.append(cartaoAtividade,satisfacao(d.satisfacao));
    relatorio.append(
      gradeKpis,
      encaminhamentos(d),
      gradeRelatorio,
      perfis(d.perfis),
      etapas(d.etapas),
      exportacao(),
      exportacao('essencial'),
      interpretar(metricasRelatorio),
    );
  }
  async function carregarRelatorio(silencioso=false){if(estado.carregandoRelatorio){estado.recarregarRelatorio=true;return;}estado.carregandoRelatorio=true;const periodo=estado.periodo,seq=++estado.sequenciaRelatorio;if(!silencioso)ids('conteudoRelatorio').replaceChildren(criar('div','cartao carregando-relatorio','Preparando os indicadores…'));if(estado.secao==='relatorios')status('Atualizando…','atualizando');try{const d=await json(urlPeriodo(urls.relatorio,periodo));if(seq!==estado.sequenciaRelatorio||periodo!==estado.periodo)return;renderRelatorio(d);if(estado.secao==='relatorios')status('Atualizado agora');}catch(e){if(seq!==estado.sequenciaRelatorio||periodo!==estado.periodo)return;if(estado.secao==='relatorios')status('Falha ao atualizar','erro');if(!silencioso)ids('conteudoRelatorio').replaceChildren(criar('div','cartao carregando-relatorio',e.message));else toast(e.message);}finally{estado.carregandoRelatorio=false;if(estado.recarregarRelatorio){estado.recarregarRelatorio=false;void carregarRelatorio(true);}}}
  function trocar(secao){estado.secao=secao;document.querySelectorAll('[data-secao]').forEach(b=>{const a=b.dataset.secao===secao;b.classList.toggle('ativo',a);b.setAttribute('aria-pressed',String(a));});ids('secaoConversas').hidden=secao!=='conversas';ids('secaoRelatorios').hidden=secao!=='relatorios';window.scrollTo({top:0});secao==='relatorios'?carregarRelatorio():carregarConversas(true);}
  document.querySelectorAll('[data-secao]').forEach(b=>b.addEventListener('click',()=>trocar(b.dataset.secao)));
  document.querySelectorAll('[data-periodo]').forEach(s=>s.addEventListener('change',()=>{estado.periodo=s.value;estado.selecionada=null;estado.sequenciaConversas++;estado.sequenciaRelatorio++;document.querySelectorAll('[data-periodo]').forEach(o=>o.value=s.value);estado.secao==='relatorios'?carregarRelatorio():carregarConversas();}));
  document.querySelectorAll('[data-filtro]').forEach(b=>b.addEventListener('click',()=>{estado.filtro=b.dataset.filtro;document.querySelectorAll('[data-filtro]').forEach(x=>x.classList.toggle('ativo',x===b));renderLista();}));
  ids('buscaConversas').addEventListener('input',e=>{estado.busca=e.target.value;renderLista();});
  ids('voltarConversas').addEventListener('click',()=>document.querySelector('.app-conversas').classList.remove('chat-aberto'));
  ids('alternarDetalhes').addEventListener('click',e=>{const a=e.currentTarget.getAttribute('aria-expanded')==='true';e.currentTarget.setAttribute('aria-expanded',String(!a));ids('painelDetalhes').hidden=a;});
  ids('mensagensChat').addEventListener('scroll',()=>{const c=ids('mensagensChat');ids('irFinal').hidden=c.scrollHeight-c.scrollTop-c.clientHeight<150;});
  ids('irFinal').addEventListener('click',()=>ids('mensagensChat').scrollTo({top:ids('mensagensChat').scrollHeight,behavior:'smooth'}));
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)(estado.secao==='conversas'?carregarConversas(true):carregarRelatorio(true));});
  setInterval(()=>{if(!document.hidden&&estado.secao==='conversas')carregarConversas(true);},10000);
  setInterval(()=>{if(!document.hidden&&estado.secao==='relatorios')carregarRelatorio(true);},30000);
  // O espaço do chat acompanha o cabeçalho real, inclusive após girar o celular.
  function ajustarAlturaPainel(){
    const raiz=document.documentElement;
    raiz.style.setProperty('--altura-cabecalho',document.querySelector('.cabecalho-app').offsetHeight+'px');
    raiz.style.setProperty('--altura-aviso',document.querySelector('.faixa-consulta').offsetHeight+'px');
  }
  ajustarAlturaPainel();
  if('ResizeObserver' in window){
    const observador=new ResizeObserver(ajustarAlturaPainel);
    observador.observe(document.querySelector('.cabecalho-app'));
    observador.observe(document.querySelector('.faixa-consulta'));
  }else{
    window.addEventListener('resize',ajustarAlturaPainel);
  }
  carregarConversas();
})();

```

### Passo 17 — `callback/monitoramento/static/monitoramento/css/painel.css`

**Ação:** Alterar. Acrescentar somente estilos do card compacto, usando o padrão de tipografia existente e quebra responsiva.

Conteúdo completo do arquivo:

```css
:root{color-scheme:light;--verde-950:#122716;--verde-900:#1c321d;--verde-800:#274a2c;--verde-700:#37663d;--lima:#d9ff6b;--creme:#f5f1ef;--branco:#fff;--texto:#1c2a1d;--muted:#6f796e;--linha:#dde2d8;--painel:#f8f9f5;--erro:#a93636;--sombra:0 16px 45px rgba(20,43,23,.09);font-family:"Segoe UI",-apple-system,BlinkMacSystemFont,Arial,sans-serif;font-synthesis:none}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{margin:0;min-height:100%;max-width:100%;background:var(--creme);color:var(--texto)}
body{min-width:300px;overflow-x:clip}
button,input,select{font:inherit}
button,select{cursor:pointer}
button:focus-visible,input:focus-visible,select:focus-visible,a:focus-visible{outline:3px solid #83a84d;outline-offset:2px}
svg{stroke:currentColor;fill:none;stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}
.skip-link{position:fixed;z-index:50;left:14px;top:-60px;padding:11px 14px;border-radius:8px;background:#fff;color:var(--verde-900)}
.skip-link:focus{top:10px}
.cabecalho-app{height:64px;padding:0 clamp(18px,3vw,44px);display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:25px;background:var(--verde-900);color:#fff;position:sticky;top:0;z-index:20;box-shadow:0 4px 16px #10231328}
.marca-app{display:flex;align-items:center;min-width:0}
.marca-app img{width:104px;height:auto;filter:brightness(0) invert(1)}
.marca-app .divisor{height:30px;width:1px;background:#ffffff30;margin:0 18px}
.marca-app div{display:flex;flex-direction:column;min-width:0}
.marca-app strong{font-size:13px;letter-spacing:.06em}
.marca-app div span{font-size:11px;color:#becaba;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.seletor-secao{display:flex;padding:4px;border:1px solid #ffffff15;border-radius:13px;background:#0e211278}
.seletor-secao button{height:40px;padding:0 20px;border:0;border-radius:9px;background:transparent;color:#c7d2c4;display:flex;align-items:center;gap:8px;font-weight:650}
.seletor-secao button svg{width:17px}
.seletor-secao button.ativo{background:#fff;color:var(--verde-900);box-shadow:0 3px 9px #0003}
.acoes-cabecalho{justify-self:end;display:flex;align-items:center;gap:18px}
.estado-atualizacao{font-size:11px;color:#c5d1c2;display:flex;align-items:center;white-space:nowrap}
.estado-atualizacao i{width:7px;height:7px;border-radius:50%;background:var(--lima);box-shadow:0 0 0 4px #d9ff6b17;margin-right:8px}
.estado-atualizacao.atualizando i{animation:pulso 1s infinite}
.estado-atualizacao.erro i{background:#ff908a}
.botao-sair{border:1px solid #ffffff30;border-radius:8px;background:transparent;color:#fff;padding:8px 13px}
.botao-sair:hover{background:#ffffff12}
.faixa-consulta{min-height:32px;padding:5px clamp(18px,3vw,44px);display:flex;align-items:center;justify-content:center;gap:10px;background:#e8f0d0;border-bottom:1px solid #cfdaae;color:#3f522f}
.faixa-consulta svg{width:17px;flex:0 0 17px}
.faixa-consulta p{font-size:11px;margin:0;line-height:1.5}
main{width:100%;max-width:1600px;min-width:0;margin:0 auto}
.secao-painel{min-width:0;padding:12px clamp(16px,3vw,42px) 14px}
#secaoConversas{display:flex;flex-direction:column;height:calc(100dvh - var(--altura-cabecalho,64px) - var(--altura-aviso,32px));min-height:300px}
.barra-contexto{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:10px;flex-shrink:0}
.sobrelinha{font-size:9px;font-weight:800;letter-spacing:.18em;color:var(--verde-700);margin:0 0 6px}
.barra-contexto h1{font-size:28px;line-height:1.1;letter-spacing:-.04em;margin:0 0 5px}
.barra-contexto>div>p:last-child{font-size:12px;color:var(--muted);margin:0}
.seletor-periodo{display:flex;flex-direction:column;gap:5px;color:var(--muted);font-size:9px;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.seletor-periodo select{min-width:190px;height:42px;padding:0 34px 0 12px;border:1px solid var(--linha);border-radius:9px;color:var(--texto);background:#fff}
.app-conversas{flex:1;min-height:200px;display:grid;grid-template-columns:minmax(310px,370px) 1fr;overflow:hidden;border:1px solid #d5dbd1;border-radius:17px;background:#fff;box-shadow:var(--sombra)}
.lista-conversas{min-width:0;min-height:0;display:flex;flex-direction:column;border-right:1px solid var(--linha);background:#fff}
.busca{position:relative;padding:8px 12px 4px}
.busca svg{position:absolute;width:17px;left:25px;top:21px;color:#7a8677}
.busca input{width:100%;height:42px;border:1px solid var(--linha);border-radius:9px;background:var(--painel);padding:0 12px 0 39px;color:var(--texto);outline:0}
.busca input:focus{border-color:var(--verde-700);background:#fff}
.filtros-conversas{display:flex;gap:6px;padding:2px 12px 6px;overflow-x:auto;scrollbar-width:none}
.filtros-conversas button{white-space:nowrap;padding:7px 11px;border:1px solid var(--linha);border-radius:999px;background:#fff;color:#667064;font-size:11px}
.filtros-conversas button.ativo{border-color:var(--verde-700);background:var(--verde-800);color:#fff}
.rolagem-lista{flex:1;min-height:0;overflow:auto;overscroll-behavior:contain}
.item-conversa{width:100%;padding:7px 12px;border:0;border-top:1px solid #edf0e9;background:#fff;display:grid;grid-template-columns:40px minmax(0,1fr);gap:10px;align-items:center;text-align:left;color:inherit}
.item-conversa:hover,.item-conversa.ativo{background:#f0f4e9}
.item-conversa.ativo{box-shadow:inset 3px 0 var(--verde-700)}
.avatar{width:45px;height:45px;border-radius:50%;background:var(--verde-700);color:#fff;display:grid;place-items:center;font-weight:750}
.item-conversa .avatar{width:40px;height:40px}
.item-corpo{min-width:0}
.item-linha{display:flex;justify-content:space-between;gap:7px;align-items:flex-start}
.item-linha strong{min-width:0;flex:1;font-size:13px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.item-linha time{font-size:9px;color:#8a9487;white-space:nowrap}
.item-metadados{min-width:0;display:flex;align-items:center;justify-content:flex-end;gap:5px;flex:0 0 auto}
.perfis-resumidos-item{max-width:100px;display:flex;flex-wrap:wrap;justify-content:flex-end;gap:2px}
.mini-tag.perfil-resumido{padding:2px 5px;font-size:7px;white-space:nowrap;background:#edf2e8;color:#40573e}
.mini-tag.perfil-resumido.dependente-menor,.mini-tag.perfil-resumido.menor{background:#e1edff;color:#315f98}
.mini-tag.perfil-resumido.dependente-adulto{background:#ddf1e4;color:#296b42}
.mini-tag.perfil-resumido.dependente-idoso,.mini-tag.perfil-resumido.idoso{background:#e9e1ff;color:#614299}
.item-previa{margin:3px 0 0;font-size:11px;color:#748071;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.mini-tags:not(:empty){margin-top:4px}
.mini-tags,.tags-contato{display:flex;flex-wrap:wrap;gap:4px}
.mini-tag,.tag-contato{display:inline-flex;align-items:center;border-radius:999px;background:#edf2e8;color:#50614b;padding:2px 6px;font-size:8px;font-weight:700;text-transform:uppercase;letter-spacing:.04em}
.mini-tag.funil,.tag-contato.funil{background:#dff4e3;color:#267242}
.mini-tag.nota{background:#fff2cb;color:#8b6813}
.tag-contato.idoso{background:#e9e1ff;color:#614299}
.tag-contato.menor{background:#e1edff;color:#315f98}
.estado-vazio{padding:42px 18px;text-align:center;color:var(--muted);font-size:12px}
.carregando::before{content:"";display:block;width:24px;height:24px;margin:0 auto 13px;border:2px solid #d8dfd2;border-top-color:var(--verde-700);border-radius:50%;animation:girar .8s linear infinite}
.janela-chat{min-width:0;min-height:0;position:relative;display:flex;flex-direction:column;background:#eef0e8;overflow:hidden}
.topo-chat{min-height:60px;padding:6px 12px;display:flex;align-items:center;gap:12px;background:#fff;border-bottom:1px solid var(--linha);z-index:2}
.voltar{display:none;border:0;background:transparent;font-size:28px;color:var(--verde-800)}
.identidade-contato{min-width:0;flex:1}
.identidade-contato h2{font-size:14px;margin:0 0 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.identidade-contato p{font-size:10px;color:var(--muted);margin:0 0 4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.detalhes-botao{border:1px solid var(--linha);border-radius:8px;padding:7px 10px;background:#fff;color:#5c685b;font-size:10px}
.detalhes-botao[aria-expanded=true]{background:var(--verde-800);color:#fff}
.painel-detalhes{flex:0 1 auto;max-height:40%;overflow:auto;padding:10px 18px;background:#fbfcf9;border-bottom:1px solid var(--linha);font-size:11px;color:#606b5e;z-index:2}
.painel-detalhes dl{margin:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.painel-detalhes dt{font-size:8px;text-transform:uppercase;letter-spacing:.08em;color:#8a9388}
.painel-detalhes dd{margin:2px 0 0;overflow-wrap:anywhere}
.topo-chat,.rodape-chat{flex-shrink:0}
.mensagens{flex:1;min-height:0;overflow-y:auto;position:relative;padding:22px clamp(18px,5vw,70px);background-color:#eef0e8;background-image:radial-gradient(#63755a12 1px,transparent 1px);background-size:18px 18px;overscroll-behavior:contain}
.marca-dagua{position:fixed;pointer-events:none;opacity:.035;width:260px;left:calc(50% + 135px);top:50%;transform:translate(-50%,-50%) rotate(-8deg)}
.marca-dagua img{width:100%;filter:grayscale(1)}
.boas-vindas{position:relative;z-index:1;max-width:410px;margin:14vh auto 0;padding:25px;border:1px solid #d7ddd1;border-radius:15px;background:#ffffffd9;text-align:center;box-shadow:0 8px 25px #25331d0b}
.boas-vindas span{font-size:9px;font-weight:800;letter-spacing:.14em;color:var(--verde-700)}
.boas-vindas h2{font-size:20px;margin:7px 0}
.boas-vindas p{font-size:12px;color:var(--muted);margin:0}
.dia,.separador-conversa{position:relative;z-index:1;width:max-content;max-width:90%;margin:8px auto 14px;padding:5px 10px;border:1px solid #d6ddcd;border-radius:8px;background:#f9fbf5;color:#6c7868;font-size:9px;box-shadow:0 1px 2px #0000000d}
.separador-conversa{margin-top:18px;background:#e3edd8;color:#4d6446}
.linha-mensagem{position:relative;z-index:1;display:flex;margin:3px 0}
.linha-mensagem.bot{justify-content:flex-end}
.bolha{max-width:min(76%,720px);padding:8px 10px 6px;border-radius:4px 11px 11px 11px;background:#fff;box-shadow:0 1px 2px #23301f1c}
.linha-mensagem.bot .bolha{border-radius:11px 4px 11px 11px;background:#dff1cf}
.tipo-mensagem{display:block;width:max-content;margin-bottom:4px;padding:2px 5px;border-radius:4px;background:#213b2520;color:#496346;font-size:8px;font-weight:700;text-transform:uppercase}
.texto-mensagem{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;line-height:1.45}
.botoes-mensagem{display:grid;gap:4px;margin:8px -4px -1px}
.botao-mensagem:disabled{cursor:default;opacity:1}
.botao-mensagem{min-height:31px;border:0;border-top:1px solid #bed2b3;background:transparent;color:#39704a;font-size:11px;text-align:center}
.meta-mensagem{display:flex;justify-content:flex-end;align-items:center;gap:4px;margin-top:3px;color:#73806f;font-size:8px}
.ticks{color:#4e8eb1;font-size:10px}
.rodape-chat{padding:4px 12px;text-align:center;background:#fff;border-top:1px solid var(--linha);color:#8a9388;font-size:8px}
.ir-final{position:absolute;right:20px;bottom:42px;z-index:4;width:39px;height:39px;border:1px solid var(--linha);border-radius:50%;background:#fff;color:var(--verde-800);box-shadow:0 5px 17px #1c321d30}
.secao-relatorios{padding-bottom:60px}
.conteudo-relatorio{min-width:0;display:grid;gap:10px}
.conteudo-relatorio>*{min-width:0;max-width:100%}
.cartao{min-width:0;max-width:100%;border:1px solid var(--linha);border-radius:14px;background:#fff;padding:14px;box-shadow:0 5px 20px #1c321d08}
.carregando-relatorio{text-align:center;color:var(--muted);padding:60px}
.grade-kpis{min-width:0;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
.kpi{min-height:98px;position:relative;overflow:hidden}
.kpi::after{content:"";position:absolute;right:-28px;bottom:-40px;width:90px;height:90px;border-radius:50%;background:#d9ff6b38}
.kpi .rotulo{font-size:9px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}
.kpi strong{display:block;margin:4px 0;font-size:30px;color:var(--verde-900);letter-spacing:-.05em}
.tendencia{font-size:10px;color:#687266}
.tendencia.positiva{color:#2c7b45}
.tendencia.negativa{color:#ae4444}
.grade-relatorio{min-width:0;display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,.7fr);gap:10px}
.titulo-cartao{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:10px}
.titulo-cartao h2{font-size:16px;margin:0 0 4px}
.titulo-cartao p{font-size:10px;color:var(--muted);margin:0;line-height:1.5}
.legenda{font-size:9px;color:var(--muted);white-space:nowrap}
.grafico-atividade{width:100%;max-width:100%;min-width:0}
.grafico-resumo{display:none;min-height:28px;margin:0 0 8px;padding:7px 9px;border-radius:7px;background:#f0f4e9;color:#536050;font-size:9px}
.grafico-rolagem{width:100%;max-width:100%;min-width:0;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-width:thin}
.grafico-barras{height:200px;width:max-content;min-width:100%;display:flex;align-items:flex-end;gap:5px;padding:18px 4px 30px;border-bottom:1px solid var(--linha)}
.coluna-grafico{appearance:none;height:100%;min-width:19px;flex:1 0 19px;display:flex;align-items:flex-end;justify-content:center;gap:2px;position:relative;padding:0;border:0;background:transparent;color:inherit}
.coluna-grafico i{display:block;width:7px;min-height:2px;border-radius:3px 3px 0 0;background:var(--verde-700)}
.coluna-grafico i.barra-mensagens{position:static;padding:0;background:#c6e662}
.coluna-grafico .rotulo-data{position:absolute;top:calc(100% + 8px);left:50%;transform:translateX(-50%) rotate(-35deg);font-size:7px;color:#7d8879;white-space:nowrap}
.barras-satisfacao{display:grid;gap:10px}
.barra-linha{display:grid;grid-template-columns:35px 1fr 30px;align-items:center;gap:8px;font-size:10px}
.trilho{height:8px;border-radius:999px;background:#edf0e9;overflow:hidden}
.trilho i{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,var(--verde-700),#96bd50)}
.tabela-perfis{width:100%;border-collapse:collapse;font-size:11px}
.tabela-perfis th{text-align:left;padding:9px 8px;color:var(--muted);font-size:8px;text-transform:uppercase;letter-spacing:.08em;border-bottom:1px solid var(--linha)}
.tabela-perfis td{padding:8px;border-bottom:1px solid #edf0e9}
.tabela-perfis td:not(:first-child),.tabela-perfis th:not(:first-child){text-align:right}
.etapas-lista{display:grid;gap:8px}
.etapa-linha{display:grid;grid-template-columns:25px minmax(160px,1fr) 2fr 30px;gap:8px;align-items:center;font-size:9px}
.etapa-numero{width:22px;height:22px;border-radius:6px;background:#edf2e8;display:grid;place-items:center;font-weight:700;color:var(--verde-700)}
.etapa-nome{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.exportacao{display:flex;align-items:center;justify-content:space-between;gap:20px;background:var(--verde-900);color:#fff}
.exportacao h2{margin:0 0 5px;font-size:17px}
.exportacao p{margin:0;color:#c2cec0;font-size:10px;max-width:690px}
.botoes-download{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
.botao-download{display:inline-flex;min-height:44px;align-items:center;padding:0 13px;border:1px solid #ffffff30;border-radius:8px;color:#fff;text-decoration:none;font-size:10px}
.botao-download.primario{background:var(--lima);border-color:var(--lima);color:var(--verde-950);font-weight:700}
.como-interpretar{background:#f0f4e9}
.como-interpretar h2{font-size:15px;margin:0 0 8px}
.como-interpretar ul{margin:0;padding-left:18px;color:#5f6b5c;font-size:10px;line-height:1.7}
.toast{position:fixed;z-index:100;left:50%;bottom:20px;transform:translateX(-50%);max-width:min(90vw,430px);padding:11px 15px;border-radius:9px;background:#202b21;color:#fff;box-shadow:0 8px 30px #0004;font-size:11px}
@keyframes girar{to{transform:rotate(360deg)}
}
@keyframes pulso{50%{opacity:.35}
}
@media(max-width:1000px){.cabecalho-app{grid-template-columns:minmax(0,1fr) auto auto;gap:12px;padding-inline:clamp(16px,2.5vw,28px)}
.seletor-secao{grid-row:1;grid-column:2;justify-self:center;margin:0;transform:none;z-index:auto}
.seletor-secao button{height:38px;padding:0 14px}
.acoes-cabecalho{grid-row:1;grid-column:3}
.faixa-consulta{margin-top:0}
.acoes-cabecalho .estado-atualizacao{display:none}
.app-conversas{grid-template-columns:minmax(270px,330px) minmax(0,1fr)}
.grade-relatorio{grid-template-columns:1fr}
.grade-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.filtros-conversas{gap:4px;padding-inline:10px}
.filtros-conversas button{padding:6px 8px;font-size:10px}
.marca-dagua{position:absolute;left:50%}
}
@media(max-width:720px){.cabecalho-app{height:auto;min-height:50px;padding:0 16px 6px;grid-template-columns:minmax(0,1fr) auto;grid-template-rows:50px auto;gap:0 10px}
.marca-app img{width:82px}
.marca-app .divisor{height:25px;margin:0 10px}
.marca-app strong{font-size:11px}
.marca-app div span{max-width:125px;font-size:9px}
.botao-sair{padding:7px 10px;font-size:10px}
.seletor-secao{grid-row:2;grid-column:1/-1;width:100%;margin:0;transform:none}
.seletor-secao button{flex:1;justify-content:center;height:38px;padding:0 10px;font-size:11px}
.acoes-cabecalho{grid-row:1;grid-column:2}
.faixa-consulta{margin-top:0;padding:5px 16px;align-items:flex-start}
.faixa-consulta p{font-size:9px}
.secao-painel{padding:10px 0 0}
.barra-contexto{padding:0 16px;align-items:flex-end}
.barra-contexto h1{font-size:24px}
.barra-contexto>div>p:last-child{font-size:10px}
.seletor-periodo select{min-width:150px;width:150px;height:39px;font-size:10px}
.app-conversas{border-radius:0;border-left:0;border-right:0;display:block}
.lista-conversas{height:100%;border:0}
.janela-chat{display:none;height:100%}
.chat-aberto .lista-conversas{display:none}
.chat-aberto .janela-chat{display:flex}
.voltar{display:block}
.topo-chat{padding-left:8px}
.detalhes-botao{font-size:0;padding:7px}
.detalhes-botao::before{content:"i";font-size:12px;font-family:Georgia,serif}
.painel-detalhes dl{grid-template-columns:repeat(2,minmax(0,1fr))}
.mensagens{padding:16px 10px}
.marca-dagua{position:absolute;left:50%;width:210px}
.bolha{max-width:88%}
.secao-relatorios{padding:10px 13px 24px}
.secao-relatorios .barra-contexto{padding:0 3px}
.grade-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
.kpi{min-height:98px;padding:12px}
.kpi strong{font-size:25px}
.cartao{padding:12px}
.grade-relatorio{display:block}
.grade-relatorio>.cartao+ .cartao{margin-top:10px}
.tabela-perfis{font-size:9px}
.tabela-perfis th,.tabela-perfis td{padding:9px 4px}
.etapa-linha{grid-template-columns:24px minmax(105px,1.2fr) 1fr 25px}
.exportacao{display:block}
.botoes-download{justify-content:flex-start;margin-top:10px}
.botao-download{flex:1;justify-content:center}
.estado-vazio{padding:30px 15px}
.grafico-resumo{display:block}
}
@media(max-width:560px){.barra-contexto{flex-direction:column;align-items:stretch;gap:8px}
.seletor-periodo{width:100%;margin-top:0}
.seletor-periodo select{width:100%;min-width:0}
.tabela-perfis,.tabela-perfis tbody,.tabela-perfis tr,.tabela-perfis td{display:block;width:100%}
.tabela-perfis thead{display:none}
.tabela-perfis tbody{display:grid;gap:9px}
.tabela-perfis tr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:7px 12px;padding:10px;border:1px solid #e5e9e1;border-radius:10px;background:#fbfcf9}
.tabela-perfis td,.tabela-perfis td:not(:first-child){padding:0;border:0;text-align:left;font-size:11px}
.tabela-perfis td:first-child{grid-column:1/-1;padding-bottom:3px;font-weight:650;overflow-wrap:anywhere}
.tabela-perfis td:not(:first-child)::before{content:attr(data-rotulo);display:block;margin-bottom:2px;color:var(--muted);font-size:7px;font-weight:700;letter-spacing:.07em;text-transform:uppercase}
.etapa-linha{grid-template-columns:25px minmax(0,1fr) 28px;grid-template-rows:auto 7px;gap:5px 8px;font-size:10px}
.etapa-numero{grid-column:1;grid-row:1/3;align-self:center}
.etapa-nome{grid-column:2;grid-row:1;white-space:normal;overflow:visible;line-height:1.3}
.etapa-linha .trilho{grid-column:2;grid-row:2}
.etapa-linha>strong{grid-column:3;grid-row:1/3;align-self:center;text-align:right}
}
@media(max-width:390px){
.grade-kpis{grid-template-columns:1fr 1fr}
.titulo-cartao{display:block}
.legenda{display:block;margin-top:7px}
.exportacao .botao-download{flex-basis:100%}
}
@media(hover:none){.grafico-resumo{display:block}
}
@media(orientation:landscape) and (max-height:600px) and (max-width:1000px){.cabecalho-app{height:56px;min-height:56px;padding:0 12px;grid-template-columns:minmax(0,1fr) auto auto;grid-template-rows:56px;gap:8px}
.marca-app img{width:70px}
.marca-app .divisor{height:24px;margin:0 9px}
.marca-app strong{font-size:10px}
.marca-app div span{max-width:145px;font-size:8px}
.seletor-secao{grid-row:1;grid-column:2;width:auto;padding:3px;border-radius:10px}
.seletor-secao button{height:34px;padding:0 9px;gap:6px;font-size:10px}
.seletor-secao button svg{width:14px}
.acoes-cabecalho{grid-row:1;grid-column:3}
.botao-sair{padding:6px 9px;font-size:10px}
.faixa-consulta{min-height:32px;padding:5px 12px}
.faixa-consulta p{display:-webkit-box;overflow:hidden;-webkit-box-orient:vertical;-webkit-line-clamp:2;font-size:8px;line-height:1.3}
.secao-painel{padding-top:8px}
.barra-contexto{flex-direction:row;align-items:flex-end;gap:12px}
.seletor-periodo{width:auto;margin:0}
.seletor-periodo select{width:min(190px,32vw);min-width:140px;height:36px}
}
@media(orientation:landscape) and (max-height:440px) and (max-width:560px){.marca-app div span{display:none}
}
@media(pointer:coarse){.seletor-secao button,.botao-sair,.detalhes-botao,.voltar,.filtros-conversas button,.seletor-periodo select,.busca input{min-height:44px}
.detalhes-botao,.voltar,.ir-final{min-width:44px;min-height:44px}
}
@media(prefers-reduced-motion:reduce){*{animation:none!important;scroll-behavior:auto!important}
}

.indicador-comercial{display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:10px 20px}
.indicador-comercial>div{flex:1 1 230px;min-width:0;overflow-wrap:anywhere}
.indicador-comercial h2{margin:0 0 5px;font-size:16px}
.indicador-comercial p{margin:0;color:var(--muted);font-size:12px;line-height:1.5}
.indicador-comercial .politica-suporte{margin-top:4px}
.total-comercial{font-size:28px;line-height:1.2;overflow-wrap:anywhere;max-width:100%;color:var(--verde-800)}
```

### Passo 18 — `callback/monitoramento/templates/monitoramento/painel.html`

**Ação:** Alterar. Atualizar a chave de cache dos dois estáticos para a publicação coordenada.

Conteúdo completo do arquivo:

```html
{% load static %}
<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="robots" content="noindex, nofollow">
  <meta name="theme-color" content="#1c321d">
  <meta name="referrer" content="same-origin">
  <title>Monitoramento · ESL Tech</title>
  <link rel="stylesheet" href="{% static 'monitoramento/css/painel.css' %}?v=20260911">
  <script src="{% static 'monitoramento/js/painel.js' %}?v=20260911" defer></script>
</head>
<body data-url-conversas="{% url 'monitoramento:dados_conversas' %}"
      data-url-mensagens="{% url 'monitoramento:dados_conversas' %}"
      data-url-relatorio="{% url 'monitoramento:dados_relatorio' %}"
      data-url-csv="{% url 'monitoramento:contatos_csv' %}"
      data-url-login="{% url 'monitoramento:login' %}">
  <a class="skip-link" href="#conteudo">Ir para o conteúdo</a>
  <header class="cabecalho-app">
    <div class="marca-app">
      <img src="{% static 'monitoramento/img/esl-tech.svg' %}" alt="ESL Tech" width="116" height="48">
      <span class="divisor" aria-hidden="true"></span>
      <div><strong>Monitoramento</strong><span id="nomeUnidade">{{ nome_unidade }}</span></div>
    </div>
    <nav class="seletor-secao" aria-label="Seções do monitoramento">
      <button type="button" class="ativo" data-secao="conversas" aria-pressed="true">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H8l-4 3V5Z"/></svg>Conversas
      </button>
      <button type="button" data-secao="relatorios" aria-pressed="false">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 20V10m7 10V4m7 16v-7"/></svg>Relatórios
      </button>
    </nav>
    <div class="acoes-cabecalho">
      <span class="estado-atualizacao" id="estadoAtualizacao" role="status"><i></i>Atualizado agora</span>
      <form method="post" action="{% url 'monitoramento:sair' %}">{% csrf_token %}<button type="submit" class="botao-sair" aria-label="Sair da conta">Sair</button></form>
    </div>
  </header>

  <div class="faixa-consulta" role="note">
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8v.1"/></svg>
    <p><strong>Ambiente somente para monitoramento.</strong> Nenhuma mensagem pode ser enviada por aqui. Para falar com um contato, use o número comercial da unidade.</p>
  </div>

  <main id="conteudo">
    <section id="secaoConversas" class="secao-painel" aria-labelledby="tituloConversas">
      <header class="barra-contexto">
        <div><h1 id="tituloConversas">Conversas</h1><p id="periodoConversas">Carregando período…</p></div>
        <label class="seletor-periodo">Período
          <select data-periodo>
            {% for chave, rotulo in periodos %}<option value="{{ chave }}">{{ rotulo }}</option>{% endfor %}
          </select>
        </label>
      </header>
      <div class="app-conversas">
        <aside class="lista-conversas" aria-label="Lista de conversas">
          <div class="busca"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4 4"/></svg><input id="buscaConversas" type="search" placeholder="Pesquisar contato" aria-label="Pesquisar contato"></div>
          <nav class="filtros-conversas" aria-label="Filtrar conversas">
            <button type="button" class="ativo" data-filtro="todas">Todas</button>
            <button type="button" data-filtro="continuacoes">Continuações</button>
            <button type="button" data-filtro="funil">Funil</button>
            <button type="button" data-filtro="avaliadas">Avaliadas</button>
          </nav>
          <div id="listaConversas" class="rolagem-lista" aria-live="polite"><div class="estado-vazio carregando">Carregando conversas…</div></div>
        </aside>
        <section class="janela-chat" aria-label="Histórico da conversa">
          <header class="topo-chat" id="topoChat" hidden>
            <button type="button" id="voltarConversas" class="voltar" aria-label="Voltar para a lista">‹</button>
            <div class="avatar" id="avatarContato"></div>
            <div class="identidade-contato"><h2 id="nomeContato"></h2><p id="detalhesContato"></p><div id="tagsContato" class="tags-contato"></div></div>
            <button type="button" id="alternarDetalhes" class="detalhes-botao" aria-expanded="false">Detalhes</button>
          </header>
          <div class="painel-detalhes" id="painelDetalhes" hidden></div>
          <div class="mensagens" id="mensagensChat">
            <div class="marca-dagua" aria-hidden="true"><img src="{% static 'monitoramento/img/esl-tech.svg' %}" alt=""></div>
            <div class="boas-vindas"><span>ESL Tech</span><h2>Acompanhe cada atendimento.</h2><p>Selecione um contato para visualizar toda a conversa consolidada.</p></div>
          </div>
          <button id="irFinal" type="button" class="ir-final" aria-label="Ir para a mensagem mais recente" hidden>↓</button>
          <footer class="rodape-chat">Conteúdo privado da unidade · consulta somente leitura</footer>
        </section>
      </div>
    </section>

    <section id="secaoRelatorios" class="secao-painel secao-relatorios" aria-labelledby="tituloRelatorios" hidden>
      <header class="barra-contexto">
        <div><p class="sobrelinha">INTELIGÊNCIA COMERCIAL</p><h1 id="tituloRelatorios">Relatórios</h1><p id="periodoRelatorios">Selecione um período para interpretar os resultados.</p></div>
        <label class="seletor-periodo">Período
          <select data-periodo>
            {% for chave, rotulo in periodos %}<option value="{{ chave }}">{{ rotulo }}</option>{% endfor %}
          </select>
        </label>
      </header>
      <div id="conteudoRelatorio" class="conteudo-relatorio"><div class="cartao carregando-relatorio">Preparando os indicadores…</div></div>
    </section>
  </main>
  <div id="toast" class="toast" role="status" hidden></div>
</body>
</html>
```

### Passo 19 — `utilitarios/reports_functions/weekly.py`

**Ação:** Alterar. Propagar o limite no snapshot e na nota do PDF e computar os envios reais nas faixas fixas. O total reutiliza este módulo.

Conteúdo completo do arquivo:

```python
"""Gera dashboards HTML e relatórios PDF semanais por unidade.

O utilitário é deliberadamente import-safe: banco, configuração privada e
ReportLab só são carregados quando ``main`` é executado.  A visão humana
agrupa as conversas técnicas por ``(id_unidade, id_cliente)`` sem alterar a
forma como o chatbot persiste ou processa cada conversa.

Uso padrão (configuração de ``utilitarios/local_settings.py``)::

    python -m utilitarios.reports_functions.weekly

Para consultar uma configuração explícita ou uma unidade específica::

    python -m utilitarios.reports_functions.weekly --env-file .env.prod \
        --id-unidade 1
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from html import escape as html_escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo

from core.validacoes.suporte_por_idade import validar_idade_minima_suporte


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
SAIDA_PADRAO = RAIZ_PROJETO / "monitoramento"
FUSO_RELATORIO = ZoneInfo("America/Sao_Paulo")
DIAS_PADRAO = 7
MAX_MENSAGENS_PADRAO = 100_000
IDADE_ADULTA_MINIMA = 18
IDADE_IDOSA_MINIMA = 60
IDADE_MINIMA_DEPENDENTE_PADRAO = 5
IDADE_MINIMA_DEPENDENTE_BPA = 4

PERFIS_ATENDIMENTO = (
    "dependente_infantil",
    "dependente_adulto",
    "dependente_idoso",
    "titular_adulto",
    "titular_idoso",
)

ROTULOS_TIPO_MENSAGEM = {
    "audio": "Áudio",
    "button": "Botão",
    "contacts": "Contato compartilhado",
    "document": "Documento",
    "image": "Imagem",
    "interactive": "Interação",
    "location": "Localização",
    "reaction": "Reação",
    "sticker": "Figurinha",
    "text": "Mensagem",
    "unknown": "Conteúdo não textual",
    "video": "Vídeo",
}


def criar_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Gera um dashboard HTML e um relatório PDF dos últimos dias "
            "para cada unidade."
        )
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Arquivo .env explícito; sem ele usa utilitarios/local_settings.py.",
    )
    parser.add_argument(
        "--dias",
        type=int,
        default=DIAS_PADRAO,
        help=f"Tamanho da janela móvel (padrão: {DIAS_PADRAO}).",
    )
    parser.add_argument(
        "--ate",
        help=(
            "Fim da janela em ISO-8601. Sem fuso, considera America/Sao_Paulo; "
            "sem o parâmetro, usa o instante atual."
        ),
    )
    parser.add_argument(
        "--id-unidade",
        type=int,
        action="append",
        dest="ids_unidade",
        help="Limita a uma unidade; pode ser repetido.",
    )
    parser.add_argument(
        "--saida",
        type=Path,
        default=SAIDA_PADRAO,
        help="Diretório raiz da saída (padrão: monitoramento).",
    )
    parser.add_argument(
        "--max-mensagens",
        type=int,
        default=MAX_MENSAGENS_PADRAO,
        help="Proteção contra um HTML grande demais.",
    )
    parser.add_argument(
        "--statement-timeout-ms",
        type=int,
        default=60_000,
        help="Timeout das consultas do snapshot (padrão: 60000).",
    )
    return parser


def resolver_janela(
    dias: int = DIAS_PADRAO,
    ate: str | datetime | None = None,
) -> tuple[datetime, datetime]:
    """Retorna ``[inicio, fim)`` em UTC para uma janela móvel."""
    if dias <= 0:
        raise ValueError("--dias precisa ser maior que zero")

    if ate is None:
        fim = datetime.now(timezone.utc)
    elif isinstance(ate, datetime):
        fim = ate
    else:
        valor = ate.strip().replace("Z", "+00:00")
        fim = datetime.fromisoformat(valor)

    if fim.tzinfo is None:
        fim = fim.replace(tzinfo=FUSO_RELATORIO)
    fim = fim.astimezone(timezone.utc)
    return fim - timedelta(days=dias), fim


def sanear_nome_unidade(nome: str, id_unidade: int | None = None) -> str:
    """Converte o nome de uma unidade em um componente de caminho seguro."""
    limpo = re.sub(r"^\s*supera(?:\s+|-)+", "", nome or "", flags=re.I)
    limpo = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", limpo)
    limpo = re.sub(r"\s+", " ", limpo).strip(" .")
    chave = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", limpo)
        if not unicodedata.combining(caractere)
    ).casefold()
    if chave in {"saj", "santo antonio de jesus"}:
        limpo = "SAJ"
    if not limpo:
        limpo = f"Unidade {id_unidade}" if id_unidade is not None else "Unidade"
    reservados_windows = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{numero}" for numero in range(1, 10)),
        *(f"LPT{numero}" for numero in range(1, 10)),
    }
    if limpo.upper() in reservados_windows:
        sufixo = f" {id_unidade}" if id_unidade is not None else " unidade"
        limpo += sufixo
    return limpo


def _texto_mensagem(texto: Any, tipo: Any) -> str:
    valor = str(texto).strip() if texto is not None else ""
    if valor:
        return valor
    tipo_normalizado = str(tipo or "unknown").strip().lower()
    return f"[{ROTULOS_TIPO_MENSAGEM.get(tipo_normalizado, tipo_normalizado or 'Conteúdo')}]"


def _iso(valor: Any) -> str | None:
    if valor is None:
        return None
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=timezone.utc)
        return valor.astimezone(timezone.utc).isoformat()
    return str(valor)


def _data_local(valor: Any, formato: str = "%d/%m/%Y %H:%M") -> str:
    if valor is None:
        return "—"
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor.replace("Z", "+00:00"))
    if valor.tzinfo is None:
        valor = valor.replace(tzinfo=timezone.utc)
    return valor.astimezone(FUSO_RELATORIO).strftime(formato)


def _profissao_atual(linha: Mapping[str, Any]) -> str | None:
    for chave in ("profissao_cliente", "profissao_conversa_recente"):
        valor = linha.get(chave)
        if valor is not None and str(valor).strip():
            return str(valor).strip()
    return None


def _idade_inteira(valor: Any) -> int | None:
    """Valida 1–99 anos sem converter booleanos ou truncar idades fracionárias."""
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor if 0 < valor < 100 else None


def _classificar_perfil_atendimento(
    *,
    status_dependente: Any,
    idade_titular: Any,
    idade_dependente: Any,
    idade_minima_dependente: int,
) -> str | None:
    """Classifica a pessoa atendida, mantendo ``NULL`` e legado como desconhecidos."""
    if status_dependente is True:
        idade = _idade_inteira(idade_dependente)
        if idade is None or idade < idade_minima_dependente:
            return None
        if idade < IDADE_ADULTA_MINIMA:
            return "dependente_infantil"
        if idade < IDADE_IDOSA_MINIMA:
            return "dependente_adulto"
        return "dependente_idoso"

    if status_dependente is False:
        idade = _idade_inteira(idade_titular)
        if idade is None or idade < IDADE_ADULTA_MINIMA:
            return None
        if idade < IDADE_IDOSA_MINIMA:
            return "titular_adulto"
        return "titular_idoso"

    return None


def _rotulos_perfis(idade_minima_dependente: int) -> dict[str, str]:
    return {
        "dependente_infantil": (
            f"Dependentes de {idade_minima_dependente} a 17 anos"
        ),
        "dependente_adulto": "Dependentes de 18 a 59 anos",
        "dependente_idoso": "Dependentes com 60 anos ou mais",
        "titular_adulto": "Titulares de 18 a 59 anos",
        "titular_idoso": "Titulares com 60 anos ou mais",
    }


def _montar_segmentacao_perfis(
    perfis_conversa: Sequence[Mapping[str, Any]],
    ids_conversas_funil: set[int],
    *,
    idade_minima_suporte: int | None,
    bpa_ativo: bool,
) -> dict[str, Any]:
    """Agrega perfis por conversa sem confundi-los com o lead consolidado.

    Um cliente conta uma vez em cada segmento no qual apareceu. A quantidade
    de conversas permanece disponível porque um mesmo contato pode iniciar
    atendimentos para pessoas diferentes durante o período.
    """
    validar_idade_minima_suporte(idade_minima_suporte)
    idade_minima_dependente = (
        IDADE_MINIMA_DEPENDENTE_BPA
        if bpa_ativo
        else IDADE_MINIMA_DEPENDENTE_PADRAO
    )
    rotulos = _rotulos_perfis(idade_minima_dependente)
    acumuladores = {
        chave: {
            "ids_clientes": set(),
            "ids_conversas": set(),
            "ids_clientes_funil": set(),
            "ids_conversas_funil": set(),
        }
        for chave in PERFIS_ATENDIMENTO
    }
    todos_clientes: set[int] = set()
    clientes_classificados: set[int] = set()
    clientes_por_perfil: dict[int, set[str]] = defaultdict(set)
    conversas_classificadas: set[int] = set()
    conversas_sem_classificacao: set[int] = set()
    clientes_funil_sem_classificacao: set[int] = set()
    clientes_funil_classificados: set[int] = set()

    for perfil in perfis_conversa:
        id_cliente = int(perfil["id_cliente"])
        id_conversa = int(perfil["id_conversa"])
        todos_clientes.add(id_cliente)
        chave = _classificar_perfil_atendimento(
            status_dependente=perfil.get("status_dependente"),
            idade_titular=perfil.get("idade_titular"),
            idade_dependente=perfil.get("idade_dependente"),
            idade_minima_dependente=idade_minima_dependente,
        )
        if chave is None:
            conversas_sem_classificacao.add(id_conversa)
            if id_conversa in ids_conversas_funil:
                clientes_funil_sem_classificacao.add(id_cliente)
            continue

        acumulador = acumuladores[chave]
        acumulador["ids_clientes"].add(id_cliente)
        acumulador["ids_conversas"].add(id_conversa)
        clientes_classificados.add(id_cliente)
        clientes_por_perfil[id_cliente].add(chave)
        conversas_classificadas.add(id_conversa)
        if id_conversa in ids_conversas_funil:
            acumulador["ids_clientes_funil"].add(id_cliente)
            acumulador["ids_conversas_funil"].add(id_conversa)
            clientes_funil_classificados.add(id_cliente)

    linhas: list[dict[str, Any]] = []
    for chave in PERFIS_ATENDIMENTO:
        acumulador = acumuladores[chave]
        total_leads = len(acumulador["ids_clientes"])
        total_conversas = len(acumulador["ids_conversas"])
        funil_observado = len(acumulador["ids_clientes_funil"])
        total_funil = funil_observado
        linhas.append(
            {
                "chave": chave,
                "rotulo": rotulos[chave],
                "leads": total_leads,
                "conversas": total_conversas,
                "leads_funil": total_funil,
                "leads_funil_observados": funil_observado,
                "conversas_funil": (
                    len(acumulador["ids_conversas_funil"])
                ),
                "conversas_funil_observadas": len(
                    acumulador["ids_conversas_funil"]
                ),
                "taxa_funil": (
                    round(total_funil / total_leads * 100, 1)
                    if total_leads
                    else 0.0
                ),
                "funil_nao_aplicavel": False,
            }
        )

    total_conversas = len(perfis_conversa)
    maior_volume = max(item["leads"] for item in linhas)
    perfis_predominantes = [
        item["rotulo"] for item in linhas
        if maior_volume and item["leads"] == maior_volume
    ]

    return {
        "linhas": linhas,
        "idade_minima_dependente": idade_minima_dependente,
        "leads_classificados": len(clientes_classificados),
        "leads_sem_classificacao": len(todos_clientes - clientes_classificados),
        "leads_multiperfil": sum(
            len(perfis) > 1 for perfis in clientes_por_perfil.values()
        ),
        "conversas_classificadas": len(conversas_classificadas),
        "conversas_sem_classificacao": len(conversas_sem_classificacao),
        "conversas_funil_sem_classificacao": len(
            conversas_sem_classificacao & ids_conversas_funil
        ),
        "leads_funil_apenas_sem_classificacao": len(
            clientes_funil_sem_classificacao - clientes_funil_classificados
        ),
        "conversas_apenas_envio_funil": sum(
            bool(perfil.get("apenas_envio_funil")) for perfil in perfis_conversa
        ),
        "cobertura_conversas": round(
            len(conversas_classificadas) / total_conversas * 100, 1
        )
        if total_conversas
        else 0.0,
        "perfis_predominantes": perfis_predominantes,
        "idade_minima_suporte": idade_minima_suporte,
    }


def _ordenar_data(valor: Any) -> datetime:
    if isinstance(valor, datetime):
        data = valor
    elif valor:
        data = datetime.fromisoformat(str(valor).replace("Z", "+00:00"))
    else:
        return datetime.min.replace(tzinfo=timezone.utc)
    if data.tzinfo is None:
        data = data.replace(tzinfo=timezone.utc)
    return data.astimezone(timezone.utc)


def montar_snapshot(
    unidades: Sequence[Mapping[str, Any]],
    mensagens: Sequence[Mapping[str, Any]],
    funil: Sequence[Mapping[str, Any]],
    pesquisas: Sequence[Mapping[str, Any]],
    inicio: datetime,
    fim: datetime,
) -> dict[str, Any]:
    """Materializa a visão de relatório a partir de linhas do banco.

    A chave visual é sempre ``(id_unidade, id_cliente)``. Os IDs das
    conversas técnicas permanecem no resultado para auditoria.
    """
    unidades_por_id: dict[int, dict[str, Any]] = {}
    for linha in unidades:
        id_unidade = int(linha["id_unidade"])
        unidades_por_id[id_unidade] = {
            "id_unidade": id_unidade,
            "nome_unidade": str(linha["nome_unidade"]),
            "nome_agente": str(linha.get("nome_agente") or "Assistente"),
            "idade_minima_suporte": validar_idade_minima_suporte(linha["idade_minima_suporte"]),
            "bpa_ativo": bool(linha.get("bpa_ativo", False)),
            "conversas": [],
            "pesquisas": [],
        }

    funil_por_unidade: dict[int, set[int]] = defaultdict(set)
    conversas_funil_por_unidade: dict[int, set[int]] = defaultdict(set)
    for linha in funil:
        id_unidade = int(linha["id_unidade"])
        funil_por_unidade[id_unidade].add(int(linha["id_cliente"]))
        if linha.get("id_conversa") is not None:
            conversas_funil_por_unidade[id_unidade].add(
                int(linha["id_conversa"])
            )

    grupos: dict[tuple[int, int], dict[str, Any]] = {}
    perfis_conversa: dict[tuple[int, int, int], dict[str, Any]] = {}
    for linha in mensagens:
        id_unidade = int(linha["id_unidade"])
        id_cliente = int(linha["id_cliente"])
        if id_unidade not in unidades_por_id:
            continue
        chave = (id_unidade, id_cliente)
        grupo = grupos.get(chave)
        if grupo is None:
            grupo = {
                "id_cliente": id_cliente,
                "nome": str(linha.get("nome_cliente") or "Cliente sem nome"),
                "waid_telefone": str(linha.get("waid_telefone") or ""),
                "email": str(linha.get("email") or ""),
                "profissao": _profissao_atual(linha),
                "ids_conversa": [],
                "mensagens": [],
                "primeira_atividade": None,
                "ultima_atividade": None,
                "status_ativa": False,
                "etapa_atual": None,
                "foi_funil": False,
            }
            grupos[chave] = grupo

        id_conversa = int(linha["id_conversa"])
        if id_conversa not in grupo["ids_conversa"]:
            grupo["ids_conversa"].append(id_conversa)
        perfis_conversa.setdefault(
            (id_unidade, id_cliente, id_conversa),
            {
                "id_unidade": id_unidade,
                "id_cliente": id_cliente,
                "id_conversa": id_conversa,
                "status_dependente": linha.get("status_dependente"),
                "idade_titular": linha.get("idade_titular"),
                "idade_dependente": linha.get("idade_dependente"),
                "nome_dependente": linha.get("nome_dependente"),
                "apenas_envio_funil": False,
            },
        )

        data_mensagem = linha.get("received_data_hora")
        data_ordenacao = _ordenar_data(data_mensagem)
        if (
            grupo["primeira_atividade"] is None
            or data_ordenacao < _ordenar_data(grupo["primeira_atividade"])
        ):
            grupo["primeira_atividade"] = _iso(data_mensagem)
        if (
            grupo["ultima_atividade"] is None
            or data_ordenacao >= _ordenar_data(grupo["ultima_atividade"])
        ):
            grupo["ultima_atividade"] = _iso(data_mensagem)
            grupo["status_ativa"] = bool(linha.get("status_ativa"))
            grupo["etapa_atual"] = linha.get("id_etapa_atual")

        grupo["mensagens"].append(
            {
                "id_mensagem": int(linha["id_mensagem"]),
                "id_conversa": id_conversa,
                "data": _iso(data_mensagem),
                "quem_enviou": str(linha["quem_enviou"]),
                "tipo": str(linha.get("tipo_mensagem") or "unknown"),
                "texto": _texto_mensagem(
                    linha.get("conteudo_texto"), linha.get("tipo_mensagem")
                ),
                "id_etapa": linha.get("id_etapa"),
            }
        )

    for (id_unidade, id_cliente), grupo in grupos.items():
        grupo["mensagens"].sort(
            key=lambda item: (_ordenar_data(item["data"]), item["id_mensagem"])
        )
        grupo["foi_funil"] = id_cliente in funil_por_unidade[id_unidade]
        unidades_por_id[id_unidade]["conversas"].append(grupo)

    for unidade in unidades_por_id.values():
        unidade["conversas"].sort(
            key=lambda grupo: _ordenar_data(grupo["ultima_atividade"]), reverse=True
        )

    # Um retry pode confirmar o envio de uma conversa antiga enquanto o mesmo
    # contato interage em outra. Preservamos o perfil do envio, sem acrescentar
    # suas mensagens fora da janela ao dashboard de conversas.
    for linha in funil:
        id_unidade = int(linha["id_unidade"])
        id_cliente = int(linha["id_cliente"])
        if (id_unidade, id_cliente) not in grupos or linha.get("id_conversa") is None:
            continue
        id_conversa = int(linha["id_conversa"])
        perfis_conversa.setdefault(
            (id_unidade, id_cliente, id_conversa),
            {
                "id_unidade": id_unidade,
                "id_cliente": id_cliente,
                "id_conversa": id_conversa,
                "status_dependente": linha.get("status_dependente"),
                "idade_titular": linha.get("idade_titular"),
                "idade_dependente": linha.get("idade_dependente"),
                "nome_dependente": linha.get("nome_dependente"),
                "apenas_envio_funil": True,
            },
        )

    perfis_por_unidade: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for perfil in perfis_conversa.values():
        perfis_por_unidade[int(perfil["id_unidade"])].append(perfil)
    for id_unidade, unidade in unidades_por_id.items():
        unidade["perfis_atendimento"] = perfis_por_unidade[id_unidade]

    for linha in pesquisas:
        id_unidade = int(linha["id_unidade"])
        if id_unidade not in unidades_por_id:
            continue
        unidades_por_id[id_unidade]["pesquisas"].append(
            {
                "id_cliente": int(linha["id_cliente"]),
                "id_conversa": int(linha["id_conversa"]),
                "nome": str(linha.get("nome_cliente") or "Cliente sem nome"),
                "waid_telefone": str(linha.get("waid_telefone") or ""),
                "profissao": _profissao_atual(linha),
                "nota": linha.get("nota"),
                "comentario": (
                    str(linha["comentario"]).strip()
                    if linha.get("comentario") is not None
                    else ""
                ),
                "criado_em": _iso(linha.get("criado_em")),
            }
        )

    for id_unidade, unidade in unidades_por_id.items():
        ids_leads_periodo = {
            int(conversa["id_cliente"]) for conversa in unidade["conversas"]
        }
        # O relatório de satisfação responde à pergunta "quantos desses leads".
        # Portanto, notas e comentários só entram quando o cliente também faz
        # parte da coorte que enviou mensagem à unidade dentro da janela.
        unidade["pesquisas"] = [
            item
            for item in unidade["pesquisas"]
            if int(item["id_cliente"]) in ids_leads_periodo
        ]
        pesquisas_unidade = unidade["pesquisas"]
        notas = [int(item["nota"]) for item in pesquisas_unidade if item["nota"] is not None]
        distribuicao = {str(nota): notas.count(nota) for nota in range(1, 6)}
        leads_com_nota = {
            item["id_cliente"] for item in pesquisas_unidade if item["nota"] is not None
        }
        ids_funil_periodo = funil_por_unidade[id_unidade] & ids_leads_periodo
        total_leads = len(ids_leads_periodo)
        total_funil = len(ids_funil_periodo)
        unidade["metricas"] = {
            "leads_contato": total_leads,
            "leads_funil": total_funil,
            "taxa_funil": round((total_funil / total_leads * 100), 1)
            if total_leads
            else 0.0,
            "leads_com_nota": len(leads_com_nota),
            "respostas_satisfacao": len(notas),
            "media_satisfacao": round(sum(notas) / len(notas), 2) if notas else None,
            "distribuicao_notas": distribuicao,
            "comentarios": sum(bool(item["comentario"]) for item in pesquisas_unidade),
            "taxa_participacao_satisfacao": round(
                len(leads_com_nota) / total_leads * 100, 1
            ) if total_leads else 0.0,
            "segmentacao_perfis": _montar_segmentacao_perfis(
                perfis_por_unidade[id_unidade],
                conversas_funil_por_unidade[id_unidade],
                idade_minima_suporte=unidade["idade_minima_suporte"],
                bpa_ativo=bool(unidade["bpa_ativo"]),
            ),
        }
        pesquisas_unidade.sort(
            key=lambda item: _ordenar_data(item["criado_em"]), reverse=True
        )

    return {
        "periodo": {
            "tipo": "semanal",
            "inicio": inicio.astimezone(timezone.utc).isoformat(),
            "fim": fim.astimezone(timezone.utc).isoformat(),
            "dias": (fim - inicio).total_seconds() / 86_400,
            "rotulo": (
                f"{_data_local(inicio, '%d/%m/%Y %H:%M')} até "
                f"{_data_local(fim, '%d/%m/%Y %H:%M')}"
            ),
        },
        "gerado_em": datetime.now(timezone.utc).isoformat(),
        "unidades": sorted(
            unidades_por_id.values(), key=lambda item: item["nome_unidade"].casefold()
        ),
    }


def _filtro_unidades(ids_unidade: Sequence[int] | None, alias: str = "u") -> tuple[str, tuple[Any, ...]]:
    if not ids_unidade:
        return "", ()
    ids = sorted(set(int(valor) for valor in ids_unidade))
    return f" AND {alias}.id_unidade = ANY(%s)", (ids,)


def _coluna_existe(cursor: Any, tabela: str, coluna: str) -> bool:
    cursor.execute(
        """
        SELECT EXISTS (
            SELECT 1
              FROM information_schema.columns
             WHERE table_schema = 'chatbot'
               AND table_name = %s
               AND column_name = %s
        ) AS existe
        """,
        (tabela, coluna),
    )
    return bool(cursor.fetchone()["existe"])


def coletar_snapshot(
    conn: Any,
    inicio: datetime,
    fim: datetime,
    ids_unidade: Sequence[int] | None = None,
    max_mensagens: int = MAX_MENSAGENS_PADRAO,
    statement_timeout_ms: int = 60_000,
) -> dict[str, Any]:
    """Consulta um snapshot consistente sem realizar nenhuma mutação."""
    if max_mensagens <= 0:
        raise ValueError("--max-mensagens precisa ser maior que zero")
    if statement_timeout_ms <= 0:
        raise ValueError("--statement-timeout-ms precisa ser maior que zero")

    from psycopg.rows import dict_row

    cursor = conn.cursor(row_factory=dict_row)
    try:
        cursor.execute("BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        cursor.execute(
            "SELECT set_config('statement_timeout', %s, true)",
            (f"{statement_timeout_ms}ms",),
        )
        cursor.execute("SELECT set_config('lock_timeout', '5000ms', true)")

        filtro, params_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT
                u.id_unidade,
                u.nome_unidade,
                u.nome_agente,
                u.idade_minima_suporte,
                u.bpa_ativo
              FROM chatbot.unidade u
             WHERE TRUE {filtro}
             ORDER BY u.nome_unidade, u.id_unidade
            """,
            params_filtro,
        )
        unidades = cursor.fetchall()
        if ids_unidade and len(unidades) != len(set(ids_unidade)):
            encontrados = {int(linha["id_unidade"]) for linha in unidades}
            ausentes = sorted(set(ids_unidade) - encontrados)
            raise RuntimeError(f"Unidade(s) não encontrada(s): {ausentes}")

        tem_profissao_cliente = _coluna_existe(cursor, "cliente", "profissao")
        tem_profissao_conversa = _coluna_existe(cursor, "conversa", "profissao")
        expr_profissao_cliente = (
            "cl.profissao" if tem_profissao_cliente else "NULL::text"
        )
        if tem_profissao_conversa:
            expr_profissao_conversa = "cx_prof.profissao"
            lateral_profissao = """
               LEFT JOIN LATERAL (
                    SELECT cx_prof.profissao
                      FROM chatbot.conversa cx_prof
                     WHERE cx_prof.id_cliente = c.id_cliente
                       AND NULLIF(BTRIM(cx_prof.profissao), '') IS NOT NULL
                     ORDER BY cx_prof.iniciou_em DESC, cx_prof.id_conversa DESC
                     LIMIT 1
               ) cx_prof ON TRUE
            """
        else:
            expr_profissao_conversa = "NULL::text"
            lateral_profissao = ""

        filtro_mensagens, params_mensagens_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            WITH clientes_janela AS (
                SELECT DISTINCT c.id_unidade, c.id_cliente
                  FROM chatbot.historico_mensagens h0
                  JOIN chatbot.conversa c ON c.id_conversa = h0.id_conversa
                  JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
                 WHERE h0.quem_enviou = 'cliente'
                   AND h0.received_data_hora >= %s
                   AND h0.received_data_hora < %s
                   {filtro_mensagens}
            )
            SELECT
                u.id_unidade,
                u.nome_unidade,
                c.id_cliente,
                cl.nome AS nome_cliente,
                cl.waid_telefone,
                cl.email,
                {expr_profissao_cliente} AS profissao_cliente,
                {expr_profissao_conversa} AS profissao_conversa_recente,
                c.id_conversa,
                c.status_ativa,
                c.status_dependente,
                c.id_etapa_atual,
                cl.idade AS idade_titular,
                d.idade AS idade_dependente,
                d.nome_dependente,
                h.id_mensagem,
                h.id_etapa,
                h.received_data_hora,
                h.quem_enviou,
                h.tipo_mensagem,
                h.conteudo_texto
              FROM clientes_janela cj
              JOIN chatbot.conversa c
                ON c.id_unidade = cj.id_unidade
               AND c.id_cliente = cj.id_cliente
              JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
              LEFT JOIN chatbot.dependente d
                ON d.id_conversa = c.id_conversa AND d.id_cliente = c.id_cliente
              JOIN chatbot.historico_mensagens h ON h.id_conversa = c.id_conversa
              {lateral_profissao}
             WHERE h.received_data_hora >= %s
               AND h.received_data_hora < %s
               AND (
                    h.quem_enviou = 'cliente'
                    OR (h.quem_enviou = 'bot' AND h.status_envio = 'sent')
               )
             ORDER BY u.id_unidade, c.id_cliente,
                      h.received_data_hora, h.id_mensagem
             LIMIT %s
            """,
            (
                inicio,
                fim,
                *params_mensagens_filtro,
                inicio,
                fim,
                max_mensagens + 1,
            ),
        )
        mensagens = cursor.fetchall()
        if len(mensagens) > max_mensagens:
            raise RuntimeError(
                "O intervalo excedeu o limite de mensagens; reduza a janela ou "
                "aumente --max-mensagens conscientemente."
            )

        filtro_funil, params_funil_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT DISTINCT
                u.id_unidade,
                c.id_cliente,
                c.id_conversa,
                c.status_dependente,
                cl.idade AS idade_titular,
                d.idade AS idade_dependente,
                d.nome_dependente
              FROM chatbot.funil_envios f
              JOIN chatbot.conversa c ON c.id_conversa = f.id_conversa
              JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
              LEFT JOIN chatbot.dependente d
                ON d.id_conversa = c.id_conversa AND d.id_cliente = c.id_cliente
             WHERE f.status = 'sent'
               AND f.enviado_em >= %s
               AND f.enviado_em < %s
               {filtro_funil}
            """,
            (inicio, fim, *params_funil_filtro),
        )
        funil = cursor.fetchall()

        filtro_pesquisa, params_pesquisa_filtro = _filtro_unidades(ids_unidade)
        cursor.execute(
            f"""
            SELECT
                u.id_unidade,
                c.id_cliente,
                c.id_conversa,
                cl.nome AS nome_cliente,
                cl.waid_telefone,
                {expr_profissao_cliente} AS profissao_cliente,
                {expr_profissao_conversa} AS profissao_conversa_recente,
                p.nota,
                p.comentario,
                p.criado_em
              FROM chatbot.pesquisa_satisfacao p
              JOIN chatbot.conversa c ON c.id_conversa = p.id_conversa
              JOIN chatbot.unidade u ON u.id_unidade = c.id_unidade
              JOIN chatbot.cliente cl ON cl.id_cliente = c.id_cliente
               {lateral_profissao}
             WHERE p.criado_em >= %s
               AND p.criado_em < %s
               {filtro_pesquisa}
             ORDER BY p.criado_em DESC, p.id_pesquisa_satisfacao DESC
            """,
            (inicio, fim, *params_pesquisa_filtro),
        )
        pesquisas = cursor.fetchall()

        snapshot = montar_snapshot(
            unidades=unidades,
            mensagens=mensagens,
            funil=funil,
            pesquisas=pesquisas,
            inicio=inicio,
            fim=fim,
        )
        conn.rollback()
        return snapshot
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


def _json_seguro(valor: Any) -> str:
    return (
        json.dumps(valor, ensure_ascii=False, separators=(",", ":"))
        .replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def renderizar_html(unidade: Mapping[str, Any], periodo: Mapping[str, Any]) -> str:
    """Cria um dashboard offline; dados do banco entram apenas como JSON seguro."""
    payload = {
        "unidade": {
            "id_unidade": unidade["id_unidade"],
            "nome_unidade": unidade["nome_unidade"],
            "nome_agente": unidade["nome_agente"],
            "conversas": unidade["conversas"],
            "pesquisas": unidade["pesquisas"],
            "metricas": unidade["metricas"],
        },
        "periodo": periodo,
    }
    nome_titulo = html_escape(str(unidade["nome_unidade"]), quote=True)
    dados_json = _json_seguro(payload)
    return f'''<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow">
  <title>Conversas — {nome_titulo}</title>
  <style>
    :root{{--verde:#00a884;--verde2:#008069;--fundo:#efeae2;--painel:#f7f9fa;
      --linha:#e5e7eb;--texto:#182229;--muted:#667781;--bot:#d9fdd3;--cliente:#fff;
      --sombra:0 18px 60px rgba(24,34,41,.16)}}
    *{{box-sizing:border-box}} html,body{{height:100%;margin:0}}
    body{{font:14px/1.45 "Segoe UI",Arial,sans-serif;color:var(--texto);
      background:linear-gradient(180deg,var(--verde2) 0 126px,#e9edef 126px)}}
    button,input{{font:inherit}} .app{{height:calc(100vh - 34px);min-height:620px;max-width:1500px;
      margin:17px auto;background:#fff;display:grid;grid-template-columns:390px 1fr;grid-template-rows:minmax(0,1fr);
      overflow:hidden;box-shadow:var(--sombra);border-radius:5px}}
    .sidebar{{display:flex;flex-direction:column;min-width:0;min-height:0;overflow:hidden;border-right:1px solid var(--linha);background:#fff}}
    .brand{{padding:18px 20px;background:#f0f2f5;border-bottom:1px solid var(--linha)}}
    .brand h1{{font-size:17px;margin:0 0 3px}} .brand p{{margin:0;color:var(--muted);font-size:12px}}
    .stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;padding:12px;border-bottom:1px solid var(--linha)}}
    .stat{{padding:10px 8px;border:1px solid #e6ecea;border-radius:10px;background:#fbfdfc;text-align:center}}
    .stat b{{display:block;font-size:18px;color:var(--verde2)}} .stat span{{font-size:10px;color:var(--muted)}}
    .search{{padding:9px 12px;background:var(--painel)}}
    .search input{{width:100%;border:0;border-radius:8px;background:#fff;padding:10px 13px;outline:none}}
    .list{{min-height:0;overflow-y:auto;overscroll-behavior:contain;flex:1}} .empty{{padding:32px;color:var(--muted);text-align:center}}
    .chat-item{{width:100%;display:grid;grid-template-columns:46px 1fr;gap:11px;text-align:left;
      padding:12px 14px;border:0;border-bottom:1px solid #edf0f2;background:#fff;cursor:pointer}}
    .chat-item:hover,.chat-item.active{{background:#f0f2f5}}
    .avatar{{width:46px;height:46px;border-radius:50%;background:linear-gradient(145deg,#cfd8dc,#90a4ae);
      color:#fff;display:grid;place-items:center;font-weight:700;font-size:17px}}
    .item-top{{display:flex;justify-content:space-between;gap:8px}} .item-top strong{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .item-top time{{font-size:11px;color:var(--muted);white-space:nowrap}}
    .preview{{color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:12px;margin-top:4px}}
    .main{{min-width:0;min-height:0;overflow:hidden;display:flex;flex-direction:column;background:var(--fundo)}}
    .topbar{{min-height:74px;padding:11px 18px;background:#f0f2f5;border-bottom:1px solid var(--linha);display:flex;align-items:center;gap:13px}}
    .identity{{min-width:0;flex:1}} .identity h2{{font-size:16px;margin:0 0 2px}} .identity p{{margin:0;color:var(--muted);font-size:12px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
    .tag{{border:1px solid #badfd7;background:#e8f7f3;color:#087966;border-radius:999px;padding:4px 9px;font-size:11px}}
    .messages{{flex:1;min-height:0;overflow-y:auto;overscroll-behavior:contain;padding:28px clamp(18px,6vw,84px);background-color:var(--fundo);
      background-image:radial-gradient(rgba(98,114,124,.09) .7px,transparent .7px);background-size:14px 14px}}
    .intro{{max-width:720px;margin:20vh auto 0;padding:26px;text-align:center;background:rgba(255,255,255,.82);border-radius:14px;color:var(--muted)}}
    .day,.conversation-cut{{width:max-content;max-width:95%;margin:14px auto;padding:5px 10px;border-radius:7px;background:#fff;color:var(--muted);font-size:11px;box-shadow:0 1px 2px rgba(0,0,0,.08)}}
    .conversation-cut{{background:#fff6cf;color:#665c25}}
    .row{{display:flex;margin:3px 0}} .row.bot{{justify-content:flex-end}}
    .bubble{{position:relative;max-width:min(72%,720px);padding:7px 9px 5px;border-radius:8px;background:var(--cliente);box-shadow:0 1px 1px rgba(0,0,0,.08);white-space:pre-wrap;overflow-wrap:anywhere}}
    .row.bot .bubble{{background:var(--bot)}} .meta{{display:flex;justify-content:flex-end;gap:7px;margin:4px 0 0 16px;color:var(--muted);font-size:10px}}
    .details{{padding:9px 18px;background:#f0f2f5;color:var(--muted);font-size:11px;border-top:1px solid var(--linha)}}
    @media(max-width:820px){{.app{{margin:0;height:100vh;min-height:0;border-radius:0;grid-template-columns:132px 1fr}}.brand p,.stats,.preview,.chat-item .item-top time{{display:none}}.chat-item{{grid-template-columns:40px 1fr;padding:10px 8px}}.avatar{{width:40px;height:40px}}.bubble{{max-width:90%}}}}
    @media print{{body{{background:#fff}}.app{{height:auto;margin:0;box-shadow:none}}}}
  </style>
  <style>
    :root{{--wa-bg:#0b141a;--wa-panel:#111b21;--wa-panel-2:#202c33;--wa-border:#2a3942;
      --wa-text:#e9edef;--wa-muted:#8696a0;--wa-green:#00a884;--wa-green-dark:#005c4b;
      --wa-client:#202c33;--wa-bot:#005c4b;--wa-blue:#53bdeb}}
    body{{color:var(--wa-text);background:var(--wa-bg)}}
    .app{{height:100vh;min-height:560px;max-width:none;margin:0;border-radius:0;
      grid-template-columns:390px minmax(0,1fr);background:var(--wa-bg);box-shadow:none}}
    .sidebar{{background:var(--wa-panel);border-color:var(--wa-border)}}
    .brand{{padding:17px 18px;background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .brand h1{{font-size:18px;color:var(--wa-text)}} .brand p{{color:var(--wa-muted)}}
    .stats{{grid-template-columns:repeat(4,1fr);gap:6px;padding:10px;background:var(--wa-panel);border-color:var(--wa-border)}}
    .stat{{padding:9px 4px;border-color:var(--wa-border);border-radius:8px;background:#18252d}}
    .stat b{{font-size:17px;color:#66d6bc}} .stat span{{font-size:9px;color:var(--wa-muted)}}
    .search{{padding:8px 12px;background:var(--wa-panel)}}
    .search input{{color:var(--wa-text);background:var(--wa-panel-2);padding:10px 14px}}
    .search input::placeholder{{color:var(--wa-muted)}}
    .filters{{display:flex;gap:6px;padding:0 12px 10px;overflow-x:auto;border-bottom:1px solid var(--wa-border)}}
    .filter{{border:1px solid var(--wa-border);border-radius:999px;padding:6px 10px;color:var(--wa-muted);
      background:transparent;cursor:pointer;white-space:nowrap;font-size:11px}}
    .filter:hover,.filter.active{{color:#d8fff5;background:#123c35;border-color:#1f6c5d}}
    .list{{background:var(--wa-panel)}} .empty{{color:var(--wa-muted)}}
    .chat-item{{grid-template-columns:49px 1fr;gap:12px;padding:12px 14px;color:var(--wa-text);
      border-color:var(--wa-border);background:var(--wa-panel)}}
    .chat-item:hover,.chat-item.active{{background:var(--wa-panel-2)}}
    .avatar{{width:49px;height:49px;background:#667781;color:#fff}}
    .item-top time,.preview{{color:var(--wa-muted)}}
    .item-bottom{{display:flex;align-items:center;gap:7px;margin-top:4px;min-width:0}}
    .item-bottom .preview{{flex:1;margin:0}} .count{{min-width:20px;padding:2px 6px;border-radius:999px;
      background:var(--wa-green);color:#061b16;text-align:center;font-size:10px;font-weight:700}}
    .flags{{display:flex;gap:4px;margin-top:5px;min-height:17px}}
    .flag{{padding:2px 6px;border-radius:4px;background:#23343e;color:#aebac1;font-size:9px}}
    .flag.green{{background:#12493f;color:#8de7d1}} .flag.gold{{background:#4a3e1f;color:#f2d57a}}
    .main{{position:relative;background-color:var(--wa-bg);
      background-image:radial-gradient(rgba(255,255,255,.035) .75px,transparent .75px);background-size:13px 13px}}
    .topbar{{min-height:66px;padding:8px 15px;background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .identity h2{{color:var(--wa-text)}} .identity p{{color:var(--wa-muted)}}
    .tag{{border-color:#1e6e5d;background:#123c35;color:#8de7d1}}
    .icon-button{{border:1px solid var(--wa-border);border-radius:8px;padding:7px 10px;color:var(--wa-muted);
      background:#18252d;cursor:pointer}} .icon-button:hover,.icon-button[aria-pressed="true"]{{color:#d8fff5;border-color:#1f6c5d}}
    .back{{display:none;font-size:25px;line-height:1;padding:3px 10px}}
    .messages{{padding:24px clamp(18px,6vw,82px);background:transparent}}
    .intro{{margin-top:18vh;background:rgba(32,44,51,.94);color:var(--wa-muted);border:1px solid var(--wa-border)}}
    .intro h2{{color:var(--wa-text)}}
    .day,.conversation-cut{{background:#18252d;color:#aebac1;box-shadow:0 1px 1px rgba(0,0,0,.35)}}
    .conversation-cut{{background:#23343e;color:#aebac1;border:1px solid #304652}}
    .conversation-cut.continuation{{background:#123c35;color:#8de7d1;border-color:#1f6c5d}}
    .bubble{{max-width:min(76%,760px);padding:7px 9px 6px;color:var(--wa-text);background:var(--wa-client);
      box-shadow:0 1px 1px rgba(0,0,0,.28)}} .row.bot .bubble{{background:var(--wa-bot)}}
    .message-kind{{display:inline-block;margin-bottom:4px;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,.09);
      color:#b7c7cf;font-size:9px;text-transform:uppercase;letter-spacing:.04em}}
    .meta{{color:#aebac1}} .ticks{{color:var(--wa-blue);font-weight:700}}
    .technical{{display:none;padding-top:4px;color:#8fa2ac;font-size:9px}} body.show-metadata .technical{{display:block}}
    .details{{padding:8px 18px;color:var(--wa-muted);background:var(--wa-panel-2);border-color:var(--wa-border)}}
    .scroll-bottom{{position:absolute;right:24px;bottom:50px;width:42px;height:42px;border:1px solid var(--wa-border);
      border-radius:50%;color:var(--wa-text);background:var(--wa-panel-2);box-shadow:0 4px 16px rgba(0,0,0,.35);
      cursor:pointer;font-size:22px}}
    @media(max-width:820px){{
      .app{{display:block;height:100vh}} .sidebar{{height:100vh}} .main{{display:none;height:100vh}}
      body.chat-open .sidebar{{display:none}} body.chat-open .main{{display:flex}} .back{{display:inline-block}}
      .brand p,.preview,.item-top time{{display:block}} .stats{{display:grid}}
      .chat-item{{grid-template-columns:46px 1fr;padding:11px 13px}} .avatar{{width:46px;height:46px}}
      .bubble{{max-width:90%}} .messages{{padding:18px 12px}} .tag{{display:none}}
    }}
    @media print{{body{{background:#fff;color:#111}}.app{{height:auto}}}}
  </style>
</head>
<body>
  <main class="app">
    <aside class="sidebar">
      <header class="brand"><h1 id="unitName"></h1><p id="period"></p></header>
      <section class="stats" aria-label="Resumo do período">
        <div class="stat"><b id="leadCount">0</b><span>LEADS</span></div>
        <div class="stat"><b id="messageCount">0</b><span>MENSAGENS</span></div>
        <div class="stat"><b id="funnelCount">0</b><span>FUNIL</span></div>
        <div class="stat"><b id="ratingAverage">—</b><span>NOTA MÉDIA</span></div>
      </section>
      <div class="search"><input id="search" type="search" placeholder="Pesquisar lead ou mensagem" aria-label="Pesquisar conversas"></div>
      <nav class="filters" aria-label="Filtrar conversas">
        <button type="button" class="filter active" data-filter="all">Todas</button>
        <button type="button" class="filter" data-filter="continued">Continuações</button>
        <button type="button" class="filter" data-filter="funnel">Funil</button>
        <button type="button" class="filter" data-filter="rated">Avaliadas</button>
      </nav>
      <div id="chatList" class="list"></div>
    </aside>
    <section class="main">
      <header id="topbar" class="topbar" hidden>
        <button id="backButton" class="icon-button back" type="button" aria-label="Voltar para conversas">‹</button>
        <div id="avatarMain" class="avatar"></div>
        <div class="identity"><h2 id="clientName"></h2><p id="clientDetails"></p></div>
        <span id="funnelTag" class="tag" hidden>Enviado ao funil</span>
        <button id="metadataButton" class="icon-button" type="button" aria-pressed="false">Detalhes</button>
      </header>
      <div id="messages" class="messages"><div class="intro"><h2>Conversas do período</h2><p>Selecione um lead para visualizar a sequência completa das conversas técnicas no período.</p></div></div>
      <button id="scrollBottom" class="scroll-bottom" type="button" aria-label="Ir para a mensagem mais recente" hidden>↓</button>
      <footer id="details" class="details">Relatório privado: contém dados pessoais e deve ser compartilhado somente com a unidade responsável.</footer>
    </section>
  </main>
  <script id="report-data" type="application/json">{dados_json}</script>
  <script>
  (() => {{
    'use strict';
    const data = JSON.parse(document.getElementById('report-data').textContent);
    const unit = data.unidade, conversations = unit.conversas || [];
    const $ = id => document.getElementById(id);
    const fmt = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{dateStyle:'short',timeStyle:'short',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const fmtDate = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{dateStyle:'short',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const fmtTime = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{hour:'2-digit',minute:'2-digit',timeZone:'America/Sao_Paulo'}}).format(new Date(iso)) : '—';
    const initials = name => (name || '?').split(/\\s+/).slice(0,2).map(x => x[0] || '').join('').toUpperCase();
    $('unitName').textContent = unit.nome_unidade;
    $('period').textContent = data.periodo.rotulo;
    $('leadCount').textContent = unit.metricas.leads_contato;
    $('funnelCount').textContent = unit.metricas.leads_funil;
    $('ratingAverage').textContent = unit.metricas.media_satisfacao ?? '—';

    function addText(parent, tag, className, text) {{
      const node = document.createElement(tag); node.className = className || ''; node.textContent = text; parent.appendChild(node); return node;
    }}
    function showConversation(item) {{
      document.querySelectorAll('.chat-item').forEach(x => x.classList.toggle('active', x.dataset.client === String(item.id_cliente)));
      $('topbar').hidden = false; $('clientName').textContent = item.nome; $('avatarMain').textContent = initials(item.nome);
      const parts = [item.waid_telefone && `WA ID: ${{item.waid_telefone}}`, item.email, item.profissao && `Profissão: ${{item.profissao}}`].filter(Boolean);
      $('clientDetails').textContent = parts.join(' • ') || `Cliente #${{item.id_cliente}}`;
      $('funnelTag').hidden = !item.foi_funil;
      const box = $('messages'); box.replaceChildren(); let lastDay = '', lastConversation = null;
      item.mensagens.forEach(msg => {{
        const d = new Date(msg.data); const day = new Intl.DateTimeFormat('pt-BR', {{dateStyle:'long',timeZone:'America/Sao_Paulo'}}).format(d);
        if (day !== lastDay) {{ addText(box,'div','day',day); lastDay = day; }}
        if (lastConversation !== null && lastConversation !== msg.id_conversa) addText(box,'div','conversation-cut',`Continuação técnica • conversa #${{msg.id_conversa}}`);
        lastConversation = msg.id_conversa;
        const row = document.createElement('div'); row.className = `row ${{msg.quem_enviou === 'bot' ? 'bot' : 'client'}}`;
        const bubble = document.createElement('div'); bubble.className = 'bubble'; addText(bubble,'div','',msg.texto);
        const meta = addText(bubble,'div','meta',''); addText(meta,'span','',`etapa ${{msg.id_etapa ?? '—'}}`); addText(meta,'time','',fmtTime(msg.data));
        row.appendChild(bubble); box.appendChild(row);
      }});
      $('details').textContent = `Cliente #${{item.id_cliente}} • conversas técnicas: ${{item.ids_conversa.join(', ')}} • ${{item.mensagens.length}} mensagens visíveis no período`;
      box.scrollTop = box.scrollHeight;
    }}
    function renderList(filter='') {{
      const needle = filter.trim().toLocaleLowerCase('pt-BR'); const list = $('chatList'); list.replaceChildren();
      const visible = conversations.filter(item => [item.nome,item.waid_telefone,item.email,item.profissao].filter(Boolean).join(' ').toLocaleLowerCase('pt-BR').includes(needle));
      if (!visible.length) {{ addText(list,'div','empty',conversations.length ? 'Nenhum lead encontrado.' : 'Nenhuma mensagem de cliente no período.'); return; }}
      visible.forEach(item => {{
        const button = document.createElement('button'); button.type='button'; button.className='chat-item'; button.dataset.client=String(item.id_cliente);
        addText(button,'div','avatar',initials(item.nome)); const body=document.createElement('div'); const top=document.createElement('div'); top.className='item-top';
        addText(top,'strong','',item.nome); addText(top,'time','',fmtDate(item.ultima_atividade)); body.appendChild(top);
        const last=item.mensagens[item.mensagens.length-1]; addText(body,'div','preview',last ? `${{last.quem_enviou==='bot'?'✓ ':''}}${{last.texto}}` : 'Sem mensagens'); button.appendChild(body);
        button.addEventListener('click',()=>showConversation(item)); list.appendChild(button);
      }});
    }}
    $('search').addEventListener('input',event=>renderList(event.target.value)); renderList(); if (conversations[0]) showConversation(conversations[0]);
  }})();
  </script>
  <script>
  (() => {{
    'use strict';
    const data = JSON.parse(document.getElementById('report-data').textContent);
    const unit = data.unidade;
    const conversations = unit.conversas || [];
    const surveys = unit.pesquisas || [];
    const $ = id => document.getElementById(id);
    const colors = ['#7e57c2','#00897b','#5c6bc0','#d97706','#0288d1','#c44569','#5f7c3a','#8d6e63'];
    const ratingsByClient = new Map();
    let activeFilter = 'all';
    let selectedClient = null;

    surveys.forEach(survey => {{
      if (survey.nota !== null && survey.nota !== undefined) {{
        ratingsByClient.set(String(survey.id_cliente), survey.nota);
      }}
    }});

    const fmtDate = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      dateStyle:'short', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const fmtTime = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      hour:'2-digit', minute:'2-digit', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const fmtDay = iso => iso ? new Intl.DateTimeFormat('pt-BR', {{
      dateStyle:'long', timeZone:'America/Sao_Paulo'
    }}).format(new Date(iso)) : '—';
    const initials = name => (name || '?').split(/\\s+/).slice(0,2)
      .map(part => part[0] || '').join('').toUpperCase();
    const avatarColor = id => colors[Math.abs(Number(id) || 0) % colors.length];

    function addText(parent, tag, className, value) {{
      const node = document.createElement(tag);
      node.className = className || '';
      node.textContent = value;
      parent.appendChild(node);
      return node;
    }}

    function preview(message) {{
      if (!message) return 'Sem mensagens';
      const content = message.texto || '[' + (message.tipo || 'mensagem') + ']';
      return (message.quem_enviou === 'bot' ? '✓✓ ' : '') + content;
    }}

    function matchesFilter(item) {{
      if (activeFilter === 'continued') return item.ids_conversa.length > 1;
      if (activeFilter === 'funnel') return Boolean(item.foi_funil);
      if (activeFilter === 'rated') return ratingsByClient.has(String(item.id_cliente));
      return true;
    }}

    function showConversation(item) {{
      selectedClient = String(item.id_cliente);
      document.body.classList.add('chat-open');
      document.querySelectorAll('.chat-item').forEach(button => {{
        button.classList.toggle('active', button.dataset.client === selectedClient);
      }});
      $('topbar').hidden = false;
      $('clientName').textContent = item.nome;
      $('avatarMain').textContent = initials(item.nome);
      $('avatarMain').style.backgroundColor = avatarColor(item.id_cliente);
      const parts = [
        item.waid_telefone ? 'WA ID: ' + item.waid_telefone : '',
        item.email || '',
        item.profissao ? 'Profissão: ' + item.profissao : ''
      ].filter(Boolean);
      $('clientDetails').textContent = parts.join(' • ') || 'Cliente #' + item.id_cliente;
      $('funnelTag').hidden = !item.foi_funil;

      const box = $('messages');
      box.replaceChildren();
      let lastDay = '';
      let lastConversation = null;
      item.mensagens.forEach(message => {{
        const day = fmtDay(message.data);
        if (day !== lastDay) {{
          addText(box,'div','day',day);
          lastDay = day;
        }}
        if (lastConversation !== message.id_conversa) {{
          const first = lastConversation === null;
          const label = (first ? 'Início técnico' : 'Continuação técnica') +
            ' • conversa #' + message.id_conversa;
          const separator = addText(
            box,'div','conversation-cut' + (first ? '' : ' continuation'),label
          );
          separator.title = 'As conversas foram unidas porque pertencem ao mesmo cliente e à mesma unidade.';
        }}
        lastConversation = message.id_conversa;
        const isBot = message.quem_enviou === 'bot';
        const row = document.createElement('div');
        row.className = 'row ' + (isBot ? 'bot' : 'client');
        const bubble = document.createElement('div');
        bubble.className = 'bubble';
        if (message.tipo && message.tipo !== 'text') {{
          addText(bubble,'span','message-kind',message.tipo);
        }}
        addText(
          bubble,'div','',
          message.texto || '[' + (message.tipo || 'mensagem sem texto') + ']'
        );
        const technical = addText(
          bubble,'div','technical',
          'mensagem #' + message.id_mensagem +
          ' • conversa #' + message.id_conversa +
          ' • etapa ' + (message.id_etapa ?? '—') +
          ' • tipo ' + (message.tipo || '—')
        );
        technical.setAttribute('aria-hidden','true');
        const meta = addText(bubble,'div','meta','');
        addText(meta,'time','',fmtTime(message.data));
        if (isBot) addText(meta,'span','ticks','✓✓');
        row.appendChild(bubble);
        box.appendChild(row);
      }});

      const rating = ratingsByClient.get(String(item.id_cliente));
      $('details').textContent =
        'Cliente #' + item.id_cliente +
        ' • conversas técnicas: ' + item.ids_conversa.join(', ') +
        ' • ' + item.mensagens.length + ' mensagens no período' +
        (rating === undefined ? '' : ' • satisfação: ' + rating);
      box.scrollTop = box.scrollHeight;
      $('scrollBottom').hidden = true;
    }}

    const oldSearch = $('search');
    const search = oldSearch.cloneNode(true);
    oldSearch.replaceWith(search);

    function renderList() {{
      const needle = search.value.trim().toLocaleLowerCase('pt-BR');
      const list = $('chatList');
      list.replaceChildren();
      const visible = conversations.filter(item => {{
        const searchable = [item.nome,item.waid_telefone,item.email,item.profissao]
          .concat(item.mensagens.map(message => message.texto))
          .filter(Boolean).join(' ').toLocaleLowerCase('pt-BR');
        return matchesFilter(item) && searchable.includes(needle);
      }});
      if (!visible.length) {{
        addText(
          list,'div','empty',
          conversations.length ? 'Nenhum lead encontrado.' : 'Nenhuma mensagem de cliente no período.'
        );
        return;
      }}
      visible.forEach(item => {{
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'chat-item';
        button.dataset.client = String(item.id_cliente);
        if (selectedClient === button.dataset.client) button.classList.add('active');
        const avatar = addText(button,'div','avatar',initials(item.nome));
        avatar.style.backgroundColor = avatarColor(item.id_cliente);
        const body = document.createElement('div');
        const top = document.createElement('div');
        top.className = 'item-top';
        addText(top,'strong','',item.nome);
        addText(top,'time','',fmtDate(item.ultima_atividade));
        body.appendChild(top);
        const bottom = document.createElement('div');
        bottom.className = 'item-bottom';
        addText(bottom,'div','preview',preview(item.mensagens[item.mensagens.length - 1]));
        addText(bottom,'span','count',String(item.mensagens.length));
        body.appendChild(bottom);
        const flags = document.createElement('div');
        flags.className = 'flags';
        if (item.ids_conversa.length > 1) {{
          addText(flags,'span','flag',item.ids_conversa.length + ' conversas unidas');
        }}
        if (item.foi_funil) addText(flags,'span','flag green','funil');
        const rating = ratingsByClient.get(String(item.id_cliente));
        if (rating !== undefined) addText(flags,'span','flag gold','nota ' + rating);
        body.appendChild(flags);
        button.appendChild(body);
        button.addEventListener('click',() => showConversation(item));
        list.appendChild(button);
      }});
    }}

    $('period').textContent =
      (unit.nome_agente ? 'Agente ' + unit.nome_agente + ' • ' : '') + data.periodo.rotulo;
    $('messageCount').textContent = conversations.reduce(
      (total,item) => total + item.mensagens.length, 0
    );
    search.addEventListener('input',renderList);
    document.querySelectorAll('.filter').forEach(button => {{
      button.addEventListener('click',() => {{
        activeFilter = button.dataset.filter;
        document.querySelectorAll('.filter').forEach(candidate => {{
          candidate.classList.toggle('active',candidate === button);
        }});
        renderList();
      }});
    }});
    $('metadataButton').addEventListener('click',() => {{
      const enabled = document.body.classList.toggle('show-metadata');
      $('metadataButton').setAttribute('aria-pressed',String(enabled));
      document.querySelectorAll('.technical').forEach(node => {{
        node.setAttribute('aria-hidden',String(!enabled));
      }});
    }});
    $('backButton').addEventListener('click',() => {{
      document.body.classList.remove('chat-open');
    }});
    $('messages').addEventListener('scroll',() => {{
      const box = $('messages');
      $('scrollBottom').hidden = box.scrollHeight - box.scrollTop - box.clientHeight < 140;
    }});
    $('scrollBottom').addEventListener('click',() => {{
      $('messages').scrollTo({{top:$('messages').scrollHeight,behavior:'smooth'}});
    }});
    renderList();
    if (conversations[0] && window.matchMedia('(min-width:821px)').matches) {{
      showConversation(conversations[0]);
    }}
  }})();
  </script>
</body>
</html>'''


def _registrar_fontes_pdf() -> tuple[str, str]:
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    candidatos = [
        (
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arial.ttf",
            Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/arialbd.ttf",
        ),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
    ]
    for regular, bold in candidatos:
        if regular.is_file() and bold.is_file():
            try:
                pdfmetrics.registerFont(TTFont("Monitoramento", str(regular)))
                pdfmetrics.registerFont(TTFont("Monitoramento-Bold", str(bold)))
                pdfmetrics.registerFontFamily(
                    "Monitoramento",
                    normal="Monitoramento",
                    bold="Monitoramento-Bold",
                )
                return "Monitoramento", "Monitoramento-Bold"
            except Exception:
                continue
    return "Helvetica", "Helvetica-Bold"


def renderizar_pdf(
    unidade: Mapping[str, Any],
    periodo: Mapping[str, Any],
    destino: Path,
) -> None:
    """Renderiza um PDF vetorial, paginado e adequado para impressão."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            CondPageBreak,
            HRFlowable,
            KeepTogether,
            LongTable,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError(
            "ReportLab não está instalado. Execute: "
            "pip install -r utilitarios/requirements-monitoramento.txt"
        ) from exc

    fonte, fonte_bold = _registrar_fontes_pdf()
    verde = colors.HexColor("#008069")
    cinza = colors.HexColor("#667781")
    cinza_claro = colors.HexColor("#F4F6F7")
    amarelo = colors.HexColor("#F4B400")
    texto = colors.HexColor("#182229")

    estilos_base = getSampleStyleSheet()
    estilos = {
        "titulo": ParagraphStyle(
            "Titulo",
            parent=estilos_base["Title"],
            fontName=fonte_bold,
            fontSize=20,
            leading=24,
            textColor=colors.white,
            alignment=TA_LEFT,
            spaceAfter=3 * mm,
        ),
        "subtitulo_capa": ParagraphStyle(
            "SubtituloCapa",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#D6F3EC"),
        ),
        "secao": ParagraphStyle(
            "Secao",
            parent=estilos_base["Heading2"],
            fontName=fonte_bold,
            fontSize=15,
            leading=19,
            textColor=verde,
            spaceBefore=4 * mm,
            spaceAfter=2.5 * mm,
        ),
        "corpo": ParagraphStyle(
            "Corpo",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=13,
            textColor=texto,
        ),
        "pequeno": ParagraphStyle(
            "Pequeno",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=7.5,
            leading=10,
            textColor=cinza,
        ),
        "centro": ParagraphStyle(
            "Centro",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=texto,
        ),
        "cabecalho_tabela": ParagraphStyle(
            "CabecalhoTabela",
            fontName=fonte_bold,
            fontSize=8,
            leading=11,
            textColor=colors.white,
        ),
        "indicador": ParagraphStyle(
            "Indicador",
            fontName=fonte_bold,
            fontSize=23,
            leading=28,
            alignment=TA_CENTER,
            textColor=verde,
        ),
        "rotulo_indicador": ParagraphStyle(
            "RotuloIndicador",
            fontName=fonte,
            fontSize=8,
            leading=11,
            alignment=TA_CENTER,
            textColor=texto,
        ),
        "comentario": ParagraphStyle(
            "Comentario",
            parent=estilos_base["BodyText"],
            fontName=fonte,
            fontSize=9,
            leading=14,
            leftIndent=4 * mm,
            rightIndent=3 * mm,
            borderColor=colors.HexColor("#B9E4D9"),
            borderWidth=0,
            borderPadding=(2 * mm, 3 * mm, 2 * mm, 3 * mm),
            backColor=colors.HexColor("#F5FBF9"),
            textColor=texto,
            spaceAfter=2 * mm,
        ),
    }

    def p(valor: Any, estilo: str = "corpo") -> Any:
        texto_seguro = html_escape(str(valor if valor not in (None, "") else "—"))
        return Paragraph(texto_seguro.replace("\n", "<br/>"), estilos[estilo])

    def percentual(valor: float) -> str:
        return f"{valor:.1f}%".replace(".", ",")

    nome_unidade = str(unidade["nome_unidade"])
    metricas = unidade["metricas"]
    gerado_em = datetime.now(timezone.utc)
    dias_periodo = float(periodo.get("dias") or 0)
    if periodo.get("tipo") == "total":
        selo_periodo = "HISTÓRICO TOTAL"
    elif dias_periodo.is_integer():
        selo_periodo = f"ÚLTIMOS {int(dias_periodo)} DIAS"
    else:
        selo_periodo = "JANELA DO RELATÓRIO"
    destino.parent.mkdir(parents=True, exist_ok=True)
    documento = SimpleDocTemplate(
        str(destino),
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Desempenho — {nome_unidade}",
        author="Monitoramento do chatbot",
        subject=f"Indicadores de {periodo['rotulo']}",
    )

    def cabecalho_rodape(canvas: Any, doc: Any) -> None:
        canvas.saveState()
        largura, altura = A4
        canvas.setStrokeColor(colors.HexColor("#DDE4E7"))
        canvas.line(16 * mm, 13 * mm, largura - 16 * mm, 13 * mm)
        canvas.setFont(fonte, 7.5)
        canvas.setFillColor(cinza)
        canvas.drawString(16 * mm, 8.5 * mm, nome_unidade)
        canvas.drawRightString(
            largura - 16 * mm,
            8.5 * mm,
            f"Página {doc.page} • gerado {_data_local(gerado_em)}",
        )
        canvas.setFont(fonte, 6.5)
        canvas.drawString(
            16 * mm, 4.5 * mm,
            "Documento privado • dados pessoais • uso exclusivo de pessoas autorizadas da unidade.",
        )
        canvas.restoreState()

    historia: list[Any] = []
    capa = Table(
        [
            [
                Paragraph("Relatório de desempenho", estilos["titulo"]),
                p(selo_periodo, "centro"),
            ],
            [
                Paragraph(
                    f"<b>{html_escape(nome_unidade)}</b><br/>{html_escape(str(periodo['rotulo']))}",
                    estilos["subtitulo_capa"],
                ),
                "",
            ],
        ],
        colWidths=[135 * mm, 32 * mm],
    )
    capa.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), verde),
                ("SPAN", (0, 1), (1, 1)),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TEXTCOLOR", (1, 0), (1, 0), verde),
                ("BACKGROUND", (1, 0), (1, 0), colors.white),
                ("BOX", (1, 0), (1, 0), 0.5, colors.white),
                ("LEFTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7 * mm),
                ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
                ("ROUNDEDCORNERS", [5]),
            ]
        )
    )
    historia.extend([capa, Spacer(1, 3 * mm)])

    valores_cards = [
        (metricas["leads_contato"], "Leads em contato"),
        (metricas["leads_funil"], "Enviados ao funil"),
        (metricas["leads_com_nota"], "Leads que avaliaram"),
        (
            f"{metricas['media_satisfacao']:.2f}".replace(".", ",")
            if metricas["media_satisfacao"] is not None
            else "—",
            "Nota média / 5",
        ),
    ]
    cards = []
    for valor, rotulo in valores_cards:
        cards.append(
            Table(
                [
                    [p(valor, "indicador")],
                    [p(rotulo, "rotulo_indicador")],
                ],
                colWidths=[38.75 * mm],
                style=[("LEFTPADDING", (0, 0), (-1, -1), 0),
                       ("RIGHTPADDING", (0, 0), (-1, -1), 0)],
            )
        )
    tabela_cards = Table(
        [cards],
        colWidths=[41.75 * mm] * 4,
        rowHeights=[26 * mm],
    )
    tabela_cards.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), cinza_claro),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#DCE4E7")),
                ("INNERGRID", (0, 0), (-1, -1), 3, colors.white),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 1.5 * mm),
                ("RIGHTPADDING", (0, 0), (-1, -1), 1.5 * mm),
            ]
        )
    )
    descricao_intervalo = (
        "todo o histórico disponível até o instante final do relatório"
        if periodo.get("tipo") == "total"
        else "eventos ocorridos dentro da janela móvel"
    )
    historia.extend(
        [
            Paragraph("Visão geral", estilos["secao"]),
            p(
                f"Os indicadores abaixo usam {descricao_intervalo}. "
                "Conversas técnicas do mesmo cliente foram consolidadas apenas quando "
                "pertencem à mesma unidade. "
                f"A taxa geral de envio ao funil foi de {percentual(metricas['taxa_funil'])}."
            ),
            Spacer(1, 3 * mm),
            tabela_cards,
            Spacer(1, 5 * mm),
        ]
    )

    segmentacao = metricas["segmentacao_perfis"]
    linhas_perfis: list[list[Any]] = [
        [
            p("Perfil atendido", "cabecalho_tabela"),
            p("Leads", "cabecalho_tabela"),
            p("Conversas", "cabecalho_tabela"),
            p("No funil", "cabecalho_tabela"),
            p("Taxa de envio", "cabecalho_tabela"),
        ]
    ]
    linhas_politica: list[int] = []
    for perfil in segmentacao["linhas"]:
        if perfil["funil_nao_aplicavel"]:
            valor_funil = "Não se aplica*"
            valor_taxa = "—"
            linhas_politica.append(len(linhas_perfis))
        else:
            valor_funil = perfil["leads_funil"]
            valor_taxa = percentual(perfil["taxa_funil"])
        linhas_perfis.append(
            [
                p(perfil["rotulo"], "pequeno"),
                p(perfil["leads"], "centro"),
                p(perfil["conversas"], "centro"),
                p(valor_funil, "centro"),
                p(valor_taxa, "centro"),
            ]
        )

    tabela_perfis = Table(
        linhas_perfis,
        colWidths=[67 * mm, 20 * mm, 24 * mm, 31 * mm, 25 * mm],
        repeatRows=1,
    )
    estilo_perfis = [
        ("BACKGROUND", (0, 0), (-1, 0), verde),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5 * mm),
    ]
    for indice_linha in linhas_politica:
        estilo_perfis.append(
            (
                "BACKGROUND",
                (0, indice_linha),
                (-1, indice_linha),
                colors.HexColor("#FFF4D6"),
            )
        )
    tabela_perfis.setStyle(TableStyle(estilo_perfis))

    total_conversas_perfil = (
        segmentacao["conversas_classificadas"]
        + segmentacao["conversas_sem_classificacao"]
    )
    leituras_rapidas: list[str] = []
    predominantes = segmentacao["perfis_predominantes"]
    if len(predominantes) == 1:
        leituras_rapidas.append(f"Maior volume: {predominantes[0]}.")
    elif predominantes:
        leituras_rapidas.append("Maior volume, em empate: " + "; ".join(predominantes) + ".")
    if segmentacao["leads_multiperfil"]:
        leituras_rapidas.append(
            f"{segmentacao['leads_multiperfil']} lead(s) apareceram em mais de um "
            "perfil de atendimento."
        )
    if segmentacao["conversas_sem_classificacao"]:
        leituras_rapidas.append(
            f"{segmentacao['conversas_sem_classificacao']} conversa(s) tinham "
            "tipo/idade ausente ou inválido, ou idade fora das faixas atuais."
        )
    if not leituras_rapidas:
        leituras_rapidas.append("Nenhum atendimento para classificar neste período.")

    bloco_perfis = [
        Paragraph("Perfil dos atendimentos", estilos["secao"]),
        p(
            "Leads representa clientes únicos dentro de cada perfil; Conversas "
            "mostra a demanda técnica. Um cliente pode aparecer em mais de um "
            "perfil quando iniciou atendimentos para pessoas diferentes, portanto "
            "as linhas não devem ser somadas para obter o total geral."
        ),
        Spacer(1, 2 * mm),
        tabela_perfis,
        Spacer(1, 2.5 * mm),
        p(
            f"Cobertura etária: {segmentacao['conversas_classificadas']} de "
            f"{total_conversas_perfil} conversa(s) ({percentual(segmentacao['cobertura_conversas'])}). "
            f"A faixa infantil começa aos {segmentacao['idade_minima_dependente']} "
            "anos conforme a configuração de BPA da unidade."
        ),
        p("Leitura rápida: " + " ".join(leituras_rapidas), "pequeno"),
    ]
    limite = segmentacao["idade_minima_suporte"]
    politica_suporte = (
        "Encaminhamento por idade: desativado."
        if limite is None
        else f"Encaminhamento ao comercial: titulares a partir de {limite} anos, na etapa de idade."
    )
    bloco_perfis.append(p(
        politica_suporte + " As faixas etárias permanecem fixas. Os números e taxas "
        "incluem os envios confirmados; a configuração atual não apaga o histórico "
        "nem comprova qual regra vigorava na época.",
        "pequeno",
    ))
    if segmentacao["conversas_funil_sem_classificacao"]:
        bloco_perfis.append(p(
            f"Envios fora das cinco faixas: {segmentacao['conversas_funil_sem_classificacao']} "
            "conversa(s) sem classificação, cujos leads continuam considerados "
            "no total geral de enviados.",
            "pequeno",
        ))
    historia.append(KeepTogether(bloco_perfis))
    if not metricas["leads_contato"]:
        historia.extend([
            Spacer(1, 4 * mm),
            p("Nenhum lead entrou em contato neste período. Não há notas, "
              "comentários ou relação de leads a apresentar."),
        ])
        documento.build(
            historia, onFirstPage=cabecalho_rodape, onLaterPages=cabecalho_rodape,
        )
        return
    historia.append(PageBreak())

    distribuicao = metricas["distribuicao_notas"]
    maximo = max([int(valor) for valor in distribuicao.values()] + [1])
    linhas_notas: list[list[Any]] = [[p("Nota", "cabecalho_tabela"), p("Distribuição", "cabecalho_tabela"), p("Respostas", "cabecalho_tabela")]]
    for nota in range(5, 0, -1):
        quantidade = int(distribuicao[str(nota)])
        barra: Any = ""
        if quantidade:
            barra = Table([[""]], colWidths=[90 * quantidade / maximo * mm], rowHeights=[4 * mm], hAlign="LEFT")
            barra.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), amarelo)]))
        linhas_notas.append([p(f"{nota} / 5"), barra, p(quantidade, "centro")])
    tabela_notas = Table(linhas_notas, colWidths=[23 * mm, 120 * mm, 24 * mm], repeatRows=1)
    tabela_notas.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), verde),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 2.3 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.3 * mm),
            ]
        )
    )
    historia.extend(
        [
            Paragraph("Satisfação", estilos["secao"]),
            p(
                f"Foram registradas {metricas['respostas_satisfacao']} nota(s) e "
                f"{metricas['comentarios']} comentário(s) no período. "
                f"Participação: {percentual(metricas['taxa_participacao_satisfacao'])} "
                "dos leads em contato deram pelo menos uma nota."
            ),
            Spacer(1, 2 * mm),
            tabela_notas,
            Spacer(1, 4 * mm),
            Paragraph("Como interpretar os números", estilos["secao"]),
            p(
                "No funil significa envio confirmado no registro local de integração, "
                "dentro do período; não significa agendamento ou venda. Cada faixa "
                "considera o envio da própria conversa, nunca de outro atendimento "
                "do mesmo contato.", "pequeno",
            ),
            p(
                "A idade do titular usa o cadastro atual; a do dependente usa o "
                "registro ligado à conversa. Idades e configurações de BPA/suporte "
                "ao idoso refletem o banco na extração, não um retrato histórico "
                "da época de cada atendimento. Idades fora de 1–99, ausentes e "
                "fora das faixas exibidas ficam sem classificação.", "pequeno",
            ),
            p(
                f"{segmentacao['leads_sem_classificacao']} lead(s) apenas sem "
                f"classificação; {segmentacao['leads_funil_apenas_sem_classificacao']} "
                "lead(s) enviados somente por conversas sem classificação. "
                f"{segmentacao['conversas_apenas_envio_funil']} conversa(s) foram "
                "incluídas nos perfis pelo envio confirmado, mesmo sem mensagem "
                "na janela, sempre de clientes que entraram em contato no período.",
                "pequeno",
            ),
        ]
    )

    cabecalho_leads = [
        p("Lead", "cabecalho_tabela"),
        p("Profissão atual", "cabecalho_tabela"),
        p("Conversa(s)", "cabecalho_tabela"),
        p("Última atividade", "cabecalho_tabela"),
        p("Funil", "cabecalho_tabela"),
    ]
    linhas_leads: list[list[Any]] = [cabecalho_leads]
    for lead in unidade["conversas"]:
        identificacao = lead["nome"]
        if lead.get("waid_telefone"):
            identificacao += f"\nWA ID: {lead['waid_telefone']}"
        linhas_leads.append(
            [
                p(identificacao, "pequeno"),
                p(lead.get("profissao"), "pequeno"),
                p(", ".join(map(str, lead["ids_conversa"])), "pequeno"),
                p(_data_local(lead["ultima_atividade"]), "pequeno"),
                p("Sim" if lead["foi_funil"] else "Não", "centro"),
            ]
        )
    if len(linhas_leads) == 1:
        linhas_leads.append([p("Nenhum lead no período"), "", "", "", ""])
    tabela_leads = LongTable(
        linhas_leads,
        colWidths=[52 * mm, 35 * mm, 26 * mm, 37 * mm, 17 * mm],
        repeatRows=1,
    )
    tabela_leads.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), verde),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#DCE4E7")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cinza_claro]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 1.8 * mm),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1.8 * mm),
                ("SPAN", (0, 1), (-1, 1)) if len(unidade["conversas"]) == 0 else ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.white),
            ]
        )
    )
    historia.extend([Spacer(1, 4 * mm), Paragraph("Comentários recebidos", estilos["secao"])])

    comentarios = [item for item in unidade["pesquisas"] if item["comentario"]]
    if not comentarios:
        historia.append(p("Nenhum comentário foi registrado no período."))
    else:
        for indice, item in enumerate(comentarios, 1):
            historia.append(CondPageBreak(28 * mm))
            cabecalho = (
                f"<b>{html_escape(item['nome'])}</b> • nota "
                f"{html_escape(str(item['nota'] if item['nota'] is not None else 'não informada'))}"
                f"<br/><font color='#667781'>Profissão: "
                f"{html_escape(item['profissao'] or 'não informada')} • "
                f"{html_escape(_data_local(item['criado_em']))} • "
                f"conversa #{item['id_conversa']}</font>"
            )
            historia.append(Paragraph(cabecalho, estilos["corpo"]))
            historia.append(
                Paragraph(
                    "“" + html_escape(item["comentario"]).replace("\n", "<br/>") + "”",
                    estilos["comentario"],
                )
            )
            if indice != len(comentarios):
                historia.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#DCE4E7"), spaceBefore=1 * mm, spaceAfter=2 * mm))

    historia.extend(
        [
            PageBreak(),
            Paragraph("Leads identificados no período", estilos["secao"]),
            p(
                "Relação consolidada por cliente da unidade. Os IDs abaixo remetem "
                "às conversas do dashboard de histórico, que permanece separado "
                "deste relatório de indicadores.",
                "pequeno",
            ),
            Spacer(1, 3 * mm),
            tabela_leads,
        ]
    )
    documento.build(
        historia,
        onFirstPage=cabecalho_rodape,
        onLaterPages=cabecalho_rodape,
    )


def _datas_nome_arquivo(periodo: Mapping[str, Any]) -> str:
    inicio = _ordenar_data(periodo["inicio"]).astimezone(FUSO_RELATORIO).date()
    fim = _ordenar_data(periodo["fim"]).astimezone(FUSO_RELATORIO).date()
    return f"{inicio.isoformat()}_a_{fim.isoformat()}"


def _arquivo_temporario(diretorio: Path, sufixo: str) -> Path:
    diretorio.mkdir(parents=True, exist_ok=True)
    descritor, caminho = tempfile.mkstemp(prefix=".gerando-", suffix=sufixo, dir=diretorio)
    os.close(descritor)
    return Path(caminho)


def _publicar_lote_recuperavel(pares: Sequence[tuple[Path, Path]]) -> None:
    """Publica um lote completo, restaurando os arquivos anteriores em erro.

    Uma troca verdadeiramente atômica de vários arquivos não existe no sistema
    de arquivos. O protocolo guarda todos os destinos antigos antes de publicar
    qualquer arquivo. Se uma troca falhar, restaura o lote anterior. Backups que
    não puderem ser restaurados são preservados para recuperação manual.
    """
    backups: dict[Path, Path] = {}
    publicados: list[Path] = []
    try:
        for _, destino in pares:
            if destino.exists():
                backup = _arquivo_temporario(
                    destino.parent, f"{destino.suffix}.backup"
                )
                backup.unlink()
                destino.replace(backup)
                backups[destino] = backup

        for temporario, destino in pares:
            temporario.replace(destino)
            publicados.append(destino)
    except Exception as erro_publicacao:
        erros_recuperacao: list[str] = []
        for destino in reversed(publicados):
            try:
                destino.unlink(missing_ok=True)
            except OSError as exc:
                erros_recuperacao.append(f"remover {destino}: {exc}")
        for destino, backup in backups.items():
            if backup.exists():
                try:
                    backup.replace(destino)
                except OSError as exc:
                    erros_recuperacao.append(
                        f"restaurar {destino} a partir de {backup}: {exc}"
                    )
        if erros_recuperacao:
            detalhes = "; ".join(erros_recuperacao)
            preservados = ", ".join(
                str(backup) for backup in backups.values() if backup.exists()
            )
            raise RuntimeError(
                "Falha ao publicar e ao restaurar o lote. "
                f"Backups preservados: {preservados or 'nenhum'}. {detalhes}"
            ) from erro_publicacao
        raise
    else:
        for backup in backups.values():
            backup.unlink(missing_ok=True)
    finally:
        for temporario, _ in pares:
            temporario.unlink(missing_ok=True)


def resolver_pastas_unidades(
    unidades: Sequence[Mapping[str, Any]],
) -> dict[int, str]:
    """Resolve nomes de pasta estáveis, inclusive quando nomes comerciais colidem."""
    pastas_usadas: set[str] = set()
    resultado: dict[int, str] = {}
    for unidade in unidades:
        id_unidade = int(unidade["id_unidade"])
        pasta_base = sanear_nome_unidade(unidade["nome_unidade"], id_unidade)
        pasta = pasta_base
        tentativa = 0
        while pasta.casefold() in pastas_usadas:
            tentativa += 1
            sufixo = str(id_unidade) if tentativa == 1 else f"{id_unidade}-{tentativa}"
            pasta = f"{pasta_base} ({sufixo})"
        pastas_usadas.add(pasta.casefold())
        resultado[id_unidade] = pasta
    return resultado


def gerar_artefatos(
    snapshot: Mapping[str, Any],
    raiz_saida: Path,
    nomes_pasta: Mapping[int, str] | None = None,
) -> list[dict[str, Path]]:
    """Gera os pares HTML/PDF e restaura o par anterior se a publicação falhar."""
    raiz_saida = raiz_saida.expanduser().resolve()
    periodo = snapshot["periodo"]
    tipo_periodo = str(periodo.get("tipo") or "semanal")
    if tipo_periodo not in {"semanal", "total"}:
        raise ValueError(f"Tipo de período inválido: {tipo_periodo!r}")
    intervalo = _datas_nome_arquivo(periodo)
    pastas = dict(nomes_pasta or resolver_pastas_unidades(snapshot["unidades"]))
    gerados: list[dict[str, Path]] = []
    publicacao: list[tuple[Path, Path]] = []

    try:
        for unidade in snapshot["unidades"]:
            id_unidade = int(unidade["id_unidade"])
            pasta = pastas.get(id_unidade)
            if not pasta:
                raise RuntimeError(f"Pasta não resolvida para a unidade {id_unidade}")
            raiz_unidade = raiz_saida / pasta / tipo_periodo
            diretorio_html = raiz_unidade / "dashbord"
            diretorio_pdf = raiz_unidade / "relatorios"
            destino_html = diretorio_html / f"conversas_{intervalo}.html"
            destino_pdf = diretorio_pdf / f"desempenho_{intervalo}.pdf"
            temporario_html = _arquivo_temporario(diretorio_html, ".html")
            temporario_pdf = _arquivo_temporario(diretorio_pdf, ".pdf")
            publicacao.extend(
                ((temporario_html, destino_html), (temporario_pdf, destino_pdf))
            )

            temporario_html.write_text(
                renderizar_html(unidade, periodo), encoding="utf-8", newline="\n"
            )
            renderizar_pdf(unidade, periodo, temporario_pdf)
            gerados.append({"html": destino_html, "pdf": destino_pdf})

        _publicar_lote_recuperavel(publicacao)
    except Exception:
        for temporario, _ in publicacao:
            temporario.unlink(missing_ok=True)
        raise
    return gerados


def executar(args: argparse.Namespace) -> list[dict[str, Path]]:
    from utilitarios.bootstrap import configurar_ambiente_utilitario

    configurar_ambiente_utilitario(args.env_file)
    # Import tardio: connection_aws lê o ambiente no momento do import.
    from core.database.connection_aws import get_conn

    inicio, fim = resolver_janela(args.dias, args.ate)
    conn = get_conn(application_name="utilitario_monitoramento_semanal")
    try:
        snapshot = coletar_snapshot(
            conn=conn,
            inicio=inicio,
            fim=fim,
            ids_unidade=args.ids_unidade,
            max_mensagens=args.max_mensagens,
            statement_timeout_ms=args.statement_timeout_ms,
        )
    finally:
        conn.close()
    return gerar_artefatos(snapshot, args.saida)


def main(argv: Sequence[str] | None = None) -> int:
    parser = criar_parser()
    args = parser.parse_args(argv)
    try:
        gerados = executar(args)
    except Exception as exc:
        parser.exit(1, f"Falha ao gerar monitoramento: {exc}\n")

    if not gerados:
        print("Nenhuma unidade encontrada; nenhum arquivo foi gerado.")
        return 0
    print(f"Monitoramento concluído para {len(gerados)} unidade(s):")
    for item in gerados:
        print(f"- HTML: {item['html']}")
        print(f"  PDF:  {item['pdf']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

## Parte 4 — testes e dados fictícios

### Passo 20 — `tests/fixtures/monitoramento_painel.py`

**Ação:** Alterar. Atualizar o contrato fictício de unidade e o indicador de relatórios.

Conteúdo completo do arquivo:

```python
"""Dados inteiramente fictícios usados pelos testes e pela revisão visual local."""


CONVERSAS = {
    'unidade': {'nome': 'Supera Santo Antônio de Jesus', 'agente': 'Suh', 'regras': {
        'idade_minima_suporte': 60, 'email_obrigatorio': True, 'bpa_ativo': True,
    }},
    'periodo': {'chave': 'total', 'rotulo': 'Todo o histórico',
                'inicio': '2026-07-29T23:55:00-03:00', 'fim': '2026-09-03T12:00:00-03:00',
                'texto': '29/07/2026 23:55 até agora'},
    'metricas': {'leads': 119, 'mensagens': 1864, 'funil': 31, 'avaliacoes': 17, 'nota_media': 4.53},
    'conversas': [
        {'id_cliente': 140, 'nome': 'Edcarlos', 'contato': '557194111866',
         'email': 'edcarlos@example.com', 'profissao': 'Empresário', 'ids_conversa': [157, 159],
         'perfis': ['adulto'], 'perfis_resumidos': ['adulto'],
         'dependentes': [], 'foi_funil': True, 'avaliada': True,
         'ultima_atividade': '2026-09-03T14:43:35Z', 'ultima_mensagem_id': 4,
         'ultima_mensagem': 'Podemos começar? ☺️'},
        {'id_cliente': 141, 'nome': 'Maria Souza', 'contato': '557599111222',
         'email': 'maria@example.com', 'profissao': 'Professora', 'ids_conversa': [158],
         'perfis': ['dependente', 'menor'], 'perfis_resumidos': ['dependente_menor'],
         'dependentes': ['Lucas'], 'foi_funil': True, 'avaliada': False,
         'ultima_atividade': '2026-09-03T13:31:17Z', 'ultima_mensagem_id': 141,
         'ultima_mensagem': 'Quero agendar'},
        {'id_cliente': 142, 'nome': 'Ariana', 'contato': '557791238060',
         'email': '', 'profissao': 'Aposentada', 'ids_conversa': [150], 'perfis': ['idoso'],
         'perfis_resumidos': ['idoso'],
         'dependentes': [], 'foi_funil': False, 'avaliada': True,
         'ultima_atividade': '2026-09-02T14:55:35Z', 'ultima_mensagem_id': 142,
         'ultima_mensagem': 'Obrigada pelo atendimento'},
        {'id_cliente': 143, 'nome': 'Joana Lima', 'contato': '557588000111',
         'email': 'joana@example.com', 'profissao': 'Autônoma', 'ids_conversa': [149],
         'perfis': ['dependente', 'adulto'], 'perfis_resumidos': ['dependente_adulto'],
         'dependentes': ['Beatriz'], 'foi_funil': False, 'avaliada': False,
         'ultima_atividade': '2026-09-01T11:41:00Z', 'ultima_mensagem_id': 143,
         'ultima_mensagem': 'Às vezes'},
    ],
    'atualizado_em': '2026-09-03T15:00:00Z',
}

MENSAGENS = {
    140: {'id_cliente': 140, 'mensagens': [
        {'id_mensagem': 1, 'id_conversa': 157, 'id_etapa': 1, 'data': '2026-09-03T14:40:00Z', 'quem_enviou': 'cliente', 'tipo': 'text', 'texto': 'Olá', 'botoes': []},
        {'id_mensagem': 2, 'id_conversa': 157, 'id_etapa': 2, 'data': '2026-09-03T14:40:04Z', 'quem_enviou': 'bot', 'tipo': 'interactive_button', 'texto': 'Esse atendimento é para você ou para um dependente?', 'botoes': ['Para mim', 'Para um dependente']},
        {'id_mensagem': 3, 'id_conversa': 157, 'id_etapa': 2, 'data': '2026-09-03T14:40:20Z', 'quem_enviou': 'cliente', 'tipo': 'interactive', 'texto': 'Para mim', 'botoes': []},
        {'id_mensagem': 4, 'id_conversa': 159, 'id_etapa': 11, 'data': '2026-09-03T14:43:35Z', 'quem_enviou': 'bot', 'tipo': 'interactive_button', 'texto': 'Vou fazer uma triagem rápida. Podemos começar? ☺️', 'botoes': ['Começar triagem']},
    ]},
}
for _id in (141, 142, 143):
    MENSAGENS[_id] = {'id_cliente': _id, 'mensagens': [
        {'id_mensagem': _id, 'id_conversa': _id + 17, 'id_etapa': 7,
         'data': '2026-09-03T13:31:17Z', 'quem_enviou': 'cliente',
         'tipo': 'text', 'texto': 'Mensagem fictícia de revisão visual', 'botoes': []},
    ]}

NOMES_ETAPAS = [
    'Saudação e nome do cliente', 'Destino do atendimento', 'Confirmação do destino',
    'Profissão do cliente', 'Nome do dependente', 'Idade do aluno', 'Oferta de aula',
    'Oferta adiada', 'Retorno ao atendimento', 'E-mail', 'Introdução à triagem',
    'Triagem · pergunta 1', 'Triagem · pergunta 2', 'Triagem · pergunta 3',
    'Triagem · pergunta 4', 'Triagem · pergunta 5', 'Triagem · pergunta 6',
    'Agendamento', 'Pesquisa · nota', 'Opção de comentário', 'Comentário', 'Finalização',
]
RELATORIO = {
    'unidade': {'nome': 'Supera Santo Antônio de Jesus', 'idade_minima_suporte': 60},
    'encaminhados_comercial_por_idade': 8,
    'periodo': CONVERSAS['periodo'], 'metricas': CONVERSAS['metricas'],
    'tendencias': {'leads': 12.4, 'mensagens': 8.1, 'funil': -3.2, 'avaliacoes': 5.0, 'nota_media': 2.1},
    'atividade': [
        {'periodo': f'2026-08-{dia:02d}T12:00:00-03:00', 'leads': 7 + dia % 5, 'mensagens': 80 + dia * 3}
        for dia in range(24, 31)
    ],
    'satisfacao': {'1': 0, '2': 0, '3': 1, '4': 6, '5': 10},
    'perfis': {'idade_minima_dependente': 4, 'sem_classificacao': 12, 'linhas': [
        {'rotulo': 'Dependentes de 4 a 17 anos', 'leads': 37, 'conversas': 37, 'funil': 24, 'taxa_funil': 64.9},
        {'rotulo': 'Dependentes de 18 a 59 anos', 'leads': 3, 'conversas': 3, 'funil': 1, 'taxa_funil': 33.3},
        {'rotulo': 'Dependentes com 60 anos ou mais', 'leads': 2, 'conversas': 2, 'funil': 0, 'taxa_funil': 0},
        {'rotulo': 'Titulares de 18 a 59 anos', 'leads': 54, 'conversas': 56, 'funil': 6, 'taxa_funil': 11.1},
        {'rotulo': 'Titulares com 60 anos ou mais', 'leads': 11, 'conversas': 11, 'funil': 0, 'taxa_funil': 0},
    ]},
    'etapas': [{'id_etapa': i + 1, 'nome_etapa': nome, 'quantidade': (i * 7) % 19} for i, nome in enumerate(NOMES_ETAPAS)],
    'atualizado_em': '2026-09-03T15:00:00Z',
}

CONTATOS = [
    {'id_cliente': 140, 'nome': 'Edcarlos Silva', 'email': 'edcarlos@example.com', 'waid_telefone': '557194111866'},
    {'id_cliente': 141, 'nome': None, 'email': None, 'waid_telefone': '557599111222'},
]
```

### Passo 21 — `tests/unit/test_suporte_idoso_email_obrigatorio.py`

**Ação:** Alterar. Adaptar os cenários antigos de suporte mantendo toda a cobertura independente de e-mail e Funil.

Conteúdo completo do arquivo:

```python
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from core.integrations.funil.oportunidades import montar_payload_oportunidade
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_suporte_idoso_etapa6,
)
from core.integrations.whatsapp.numero_comercial import (
    montar_link_numero_comercial_whatsapp,
    numero_comercial_whatsapp_valido,
)
from core.validacoes.email import (
    CLASSIFICACAO_EMAIL_AUSENTE,
    CLASSIFICACAO_EMAIL_NAO_INFORMADO,
    CLASSIFICACAO_EMAIL_VALIDO,
    calcular_email_obrigatorio_efetivo,
    classificar_resposta_email,
    eh_ausencia_email_explicita,
)
from workers.worker_flow.response_flow.etapas import (
    resolver_etapa6,
    resolver_etapa10,
)
from workers.worker_flow.transacoes import (
    efeitos_transicao,
    encerramento_atendimento,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[2]


def contexto_etapa6(idade, *, dependente=False, suporte=None):
    return {
        "id_conversa": 10,
        "id_cliente": 5,
        "id_etapa_atual": 6,
        "id_etapa_cliente": 6,
        "id_etapa_origem_transicao": 6,
        "transicoes_permitidas": {"idade_valida": 7},
        "status_dependente": dependente,
        "bpa_ativo_unidade": False,
        "idade_minima_suporte": suporte,
        "numero_comercial_unidade": "(71) 99999-9999",
        "nome_cliente": "Maria",
        "nome_dependente": "João" if dependente else None,
        "texto_cliente_atual": str(idade),
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
    }


def contexto_etapa10(
    texto,
    *,
    dependente=False,
    idade=40,
    email_obrigatorio=True,
):
    return {
        "id_conversa": 10,
        "id_cliente": 5,
        "id_etapa_atual": 10,
        "id_etapa_cliente": 10,
        "id_etapa_origem_transicao": 10,
        "transicoes_permitidas": {"email_valido": 11},
        "status_dependente": dependente,
        "idade_cliente": idade,
        "email_obrigatorio_unidade": email_obrigatorio,
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "phone-id",
        },
        "resposta_bot_para_mensagem_atual": None,
    }


def contexto_envio(etapa):
    return {
        "enviou": True,
        "resposta_ja_existia": False,
        "mensagem_bot": "mensagem",
        "id_hash_msg_bot": "wamid.bot",
        "id_etapa_resultante": etapa,
        "tipo_mensagem": "text",
    }


def dados_lead(*, resposta_email, email_global="novo@example.com"):
    return {
        "id_conversa": 122,
        "id_unidade": 1,
        "nome_unidade": "Santo Antônio de Jesus",
        "status_dependente": False,
        "nome_cliente": "Maria",
        "telefone_cliente": "5571999999999",
        "email_cliente": email_global,
        "resposta_email_conversa": resposta_email,
        "idade_cliente": 65,
        "profissao": "Aposentada",
        "nome_dependente": None,
        "idade_dependente": None,
        "triagem_respostas": [
            {"id_etapa": etapa, "resposta": "nunca"}
            for etapa in range(12, 18)
        ],
    }


class PoliticaEmailTests(unittest.TestCase):
    def test_matriz_da_politica_efetiva(self):
        casos = (
            (True, False, 59, True),
            (False, False, 59, False),
            (True, False, 60, False),
            (True, False, 99, False),
            (True, True, 70, True),
            (False, True, 70, False),
        )

        for configuracao, dependente, idade, esperado in casos:
            with self.subTest(
                configuracao=configuracao,
                dependente=dependente,
                idade=idade,
            ):
                self.assertEqual(
                    calcular_email_obrigatorio_efetivo(
                        configuracao,
                        dependente,
                        idade,
                    ),
                    esperado,
                )

    def test_classificacao_obrigatoria_e_opcional(self):
        valido = classificar_resposta_email(
            "Meu e-mail é Maria@EXEMPLO.COM.",
            email_obrigatorio=True,
        )
        self.assertTrue(valido.aceita)
        self.assertEqual(valido.classificacao, CLASSIFICACAO_EMAIL_VALIDO)
        self.assertEqual(valido.email, "Maria@exemplo.com")

        recusado = classificar_resposta_email(
            "Não tenho",
            email_obrigatorio=True,
        )
        self.assertFalse(recusado.aceita)

        ausencia = classificar_resposta_email(
            "Não tenho e-mail.",
            email_obrigatorio=False,
        )
        self.assertEqual(
            ausencia.classificacao,
            CLASSIFICACAO_EMAIL_AUSENTE,
        )
        self.assertIsNone(ausencia.email)

        comum = classificar_resposta_email(
            "prefiro continuar",
            email_obrigatorio=False,
        )
        self.assertEqual(
            comum.classificacao,
            CLASSIFICACAO_EMAIL_NAO_INFORMADO,
        )

    def test_ausencia_explicita_nao_engole_frase_financeira(self):
        self.assertFalse(eh_ausencia_email_explicita("não tenho dinheiro"))
        self.assertTrue(eh_ausencia_email_explicita("não possuo e-mail"))


class ResolverEtapa10Tests(unittest.TestCase):
    def test_titular_60_mais_avanca_sem_email_mesmo_com_flag_ativa(self):
        with patch.object(
            resolver_etapa10,
            "enviar_etapa11",
            return_value=contexto_envio(11),
        ):
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "Não tenho",
                    idade=60,
                    email_obrigatorio=True,
                )
            )

        self.assertEqual(resultado["evento_transicao"], "email_valido")
        self.assertEqual(
            resultado["resultado_coleta_email"],
            CLASSIFICACAO_EMAIL_AUSENTE,
        )
        self.assertIsNone(resultado["email_cliente"])
        self.assertFalse(resultado["email_obrigatorio_efetivo"])

    def test_dependente_60_mais_continua_obrigado_pela_unidade(self):
        tratamento = contexto_envio(10)
        tratamento["tratamento"] = True

        with patch.object(
            resolver_etapa10,
            "enviar_etapa10_contexto_email_invalido",
            return_value=tratamento,
        ) as enviar_tratamento:
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "Não tenho",
                    dependente=True,
                    idade=70,
                    email_obrigatorio=True,
                )
            )

        enviar_tratamento.assert_called_once()
        self.assertTrue(resultado["tratamento"])
        self.assertNotIn("evento_transicao", resultado)

    def test_financeiro_tem_prioridade_sobre_email_opcional(self):
        tratamento = contexto_envio(10)
        tratamento["tratamento"] = True

        with patch.object(
            resolver_etapa10,
            "validar_pergunta_financeira",
            return_value=True,
        ), patch.object(
            resolver_etapa10,
            "enviar_etapa10_financeiro",
            return_value=tratamento,
        ) as enviar_financeiro, patch.object(
            resolver_etapa10,
            "enviar_etapa11",
        ) as enviar_proxima:
            resultado = resolver_etapa10.resolve_etapa10(
                contexto_etapa10(
                    "não tenho dinheiro",
                    idade=70,
                    email_obrigatorio=False,
                )
            )

        enviar_financeiro.assert_called_once()
        enviar_proxima.assert_not_called()
        self.assertTrue(resultado["tratamento"])


class SuporteIdosoTests(unittest.TestCase):
    def test_fronteiras_e_dependente_preservam_a_ordem_aprovada(self):
        for idade, dependente, suporte, caminho in (
            (59, False, 60, "normal"),
            (60, False, 60, "suporte"),
            (99, False, 60, "suporte"),
            (100, False, 60, "cem_mais"),
            (70, True, 60, "normal_dependente"),
        ):
            with self.subTest(
                idade=idade,
                dependente=dependente,
                suporte=suporte,
            ), patch.object(
                resolver_etapa6,
                "enviar_etapa6_suporte_idoso",
                return_value=contexto_envio(6),
            ) as enviar_suporte, patch.object(
                resolver_etapa6,
                "enviar_etapa6_idade_acima_99",
                return_value=contexto_envio(6),
            ) as enviar_cem, patch.object(
                resolver_etapa6,
                "enviar_etapa7_cliente",
                return_value=contexto_envio(7),
            ) as enviar_cliente, patch.object(
                resolver_etapa6,
                "enviar_etapa7_dependente",
                return_value=contexto_envio(7),
            ) as enviar_dependente:
                resultado = resolver_etapa6.resolve_etapa6(
                    contexto_etapa6(
                        idade,
                        dependente=dependente,
                        suporte=suporte,
                    )
                )

            self.assertEqual(enviar_suporte.called, caminho == "suporte")
            self.assertEqual(enviar_cem.called, caminho == "cem_mais")
            self.assertEqual(enviar_cliente.called, caminho == "normal")
            self.assertEqual(
                enviar_dependente.called,
                caminho == "normal_dependente",
            )

            if caminho == "suporte":
                self.assertTrue(resultado["encerrar_atendimento"])
                self.assertEqual(
                    resultado["motivo_encerramento"],
                    "encaminhado_suporte_idoso",
                )

    def test_efeito_terminal_persiste_idade_do_titular(self):
        cursor = object()
        contexto = contexto_etapa6(65, suporte=60)
        envio = contexto_envio(6)
        envio.update(
            {
                "encerrar_atendimento": True,
                "motivo_encerramento": "encaminhado_suporte_idoso",
                "idade_aluno": 65,
            }
        )

        with patch.object(
            efeitos_transicao,
            "atualizar_idade_cliente",
        ) as atualizar:
            resultado = (
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(
                    contexto,
                    envio,
                    cursor,
                )
            )

        atualizar.assert_called_once_with(5, 65, cursor)
        self.assertTrue(resultado["encaminhamento_suporte_idoso"])

    def test_encerramento_e_replay_usam_motivo_novo_sem_bloqueio(self):
        contexto = contexto_etapa6(65, suporte=60)
        envio = contexto_envio(6)
        envio.update(
            {
                "encerrar_atendimento": True,
                "motivo_encerramento": "encaminhado_suporte_idoso",
            }
        )
        primeira = encerramento_atendimento.resolver_intencao_encerramento(
            contexto,
            envio,
            object(),
        )
        self.assertEqual(
            primeira["motivo_encerramento"],
            "encaminhado_suporte_idoso",
        )
        self.assertEqual(primeira["bloqueio_dias"], 0)

        contexto["resposta_bot_para_mensagem_atual"] = {
            "tipo_mensagem": "interactive_cta_url",
            "conteudo_texto": (
                "Que bom te ver aqui novamente, Maria!\n\n"
                + montar_mensagem_suporte_idoso_etapa6(60)
            ),
        }
        replay = encerramento_atendimento.resolver_intencao_encerramento(
            contexto,
            {
                "resposta_ja_existia": True,
                "id_etapa_resultante": 6,
            },
            object(),
        )
        self.assertEqual(
            replay["motivo_encerramento"],
            "encaminhado_suporte_idoso",
        )
        self.assertEqual(replay["bloqueio_dias"], 0)

    def test_numero_comercial_compartilha_a_mesma_validacao(self):
        self.assertTrue(numero_comercial_whatsapp_valido("(71) 99999-9999"))
        self.assertEqual(
            montar_link_numero_comercial_whatsapp("(71) 99999-9999"),
            "https://wa.me/5571999999999",
        )
        self.assertFalse(numero_comercial_whatsapp_valido("123"))


class PersistenciaEmailEFunilTests(unittest.TestCase):
    def test_ausencia_limpa_email_anterior_e_retry_reconstroi_sem_flag(self):
        cursor = object()
        contexto = contexto_etapa10(
            "Não tenho",
            idade=70,
            email_obrigatorio=False,
        )
        contexto["resposta_bot_para_mensagem_atual"] = {
            "id_etapa": 11,
        }
        envio = {
            "resposta_ja_existia": True,
            "id_etapa_resultante": 11,
            "evento_transicao": "email_valido",
        }

        with patch.object(
            efeitos_transicao,
            "atualizar_email_cliente",
        ) as atualizar:
            resultado = (
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(
                    contexto,
                    envio,
                    cursor,
                )
            )

        atualizar.assert_called_once_with(5, None, cursor)
        self.assertEqual(
            resultado["resultado_coleta_email"],
            CLASSIFICACAO_EMAIL_AUSENTE,
        )

    def test_funil_usa_resposta_historica_e_nao_email_global_novo(self):
        payload = montar_payload_oportunidade(
            dados_lead(resposta_email="Não tenho")
        )["oportunidades"][0]

        self.assertEqual(payload["contato"]["email"], "")
        observacoes = payload["personalizados"][0]["valor"]
        self.assertIn("E-mail do cliente: não tem", observacoes)
        self.assertNotIn("novo@example.com", observacoes)

    def test_funil_distingue_nao_informado_e_email_historico(self):
        comum = montar_payload_oportunidade(
            dados_lead(resposta_email="prefiro continuar")
        )["oportunidades"][0]
        self.assertIn(
            "E-mail do cliente: não informado",
            comum["personalizados"][0]["valor"],
        )

        antigo = montar_payload_oportunidade(
            dados_lead(resposta_email="antigo@EXEMPLO.COM")
        )["oportunidades"][0]
        self.assertEqual(antigo["contato"]["email"], "antigo@exemplo.com")

    def test_ddl_e_migracao_publicam_o_mesmo_contrato(self):
        ddl = (
            RAIZ_PROJETO
            / "core/database/deploy_database/bank_script.py"
        ).read_text(encoding="utf-8")
        migracao = (
            RAIZ_PROJETO
            / "deploy/migrations/20260829_adicionar_suporte_idoso_email_obrigatorio.sql"
        ).read_text(encoding="utf-8")

        for conteudo in (ddl, migracao):
            self.assertIn("email_obrigatorio", conteudo)
            self.assertIn("encaminhado_suporte_idoso", conteudo)

        self.assertIn("idade_minima_suporte", ddl)
        self.assertIn("suporte_idoso", migracao)
        self.assertNotIn("UPDATE chatbot.unidade", migracao)
        self.assertNotIn("INSERT INTO chatbot.unidade", migracao)


if __name__ == "__main__":
    unittest.main()
```

### Passo 22 — `tests/unit/test_monitoramento_painel.py`

**Ação:** Alterar. Adaptar os contratos do relatório preservando rotas, autorização e quatro CSVs.

Conteúdo completo do arquivo:

```python
"""Contratos de leitura, isolamento e exportação do painel de monitoramento."""

import csv
from datetime import datetime, timedelta, timezone
from io import StringIO
import unittest
from unittest.mock import patch

from django.test import Client

from monitoramento.apresentacao import (
    botoes_para_mensagem,
    consolidar_conversas,
    montar_relatorio,
    normalizar_telefone_google,
)
from monitoramento.periodos import PERIODOS, resolver_periodo
from monitoramento.services import _agrupar_perfis
from core.repositories.monitoramento import painel as repositorio_painel
from tests.fixtures.monitoramento_painel import CONTATOS, CONVERSAS, MENSAGENS, RELATORIO


CABECALHO_OFICIAL_GOOGLE_CONTATOS = [
    'Name Prefix', 'First Name', 'Middle Name', 'Last Name', 'Name Suffix',
    'Phonetic First Name', 'Phonetic Middle Name', 'Phonetic Last Name',
    'Nickname', 'File As', 'E-mail 1 - Label', 'E-mail 1 - Value',
    'Phone 1 - Label', 'Phone 1 - Value', 'Address 1 - Label',
    'Address 1 - Country', 'Address 1 - Street',
    'Address 1 - Extended Address', 'Address 1 - City', 'Address 1 - Region',
    'Address 1 - Postal Code', 'Address 1 - PO Box', 'Organization Name',
    'Organization Title', 'Organization Department', 'Birthday',
    'Event 1 - Label', 'Event 1 - Value', 'Relation 1 - Label',
    'Relation 1 - Value', 'Website 1 - Label', 'Website 1 - Value',
    'Custom Field 1 - Label', 'Custom Field 1 - Value', 'Notes', 'Labels',
]


class MonitoramentoPainelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from tests.unit.test_monitoramento_login import LoginMonitoramentoTests
        cls.cenario_classe = LoginMonitoramentoTests
        cls.cenario_classe.setUpClass()

    @classmethod
    def tearDownClass(cls):
        cls.cenario_classe.tearDownClass()
        super().tearDownClass()

    def setUp(self):
        self.cenario = self.cenario_classe(
            methodName='test_formulario_oculta_senha_e_nao_oferece_cadastro_ou_recuperacao'
        )
        self.cenario.setUp()
        self.cliente = self.cenario.cliente

    def tearDown(self):
        self.cenario.doCleanups()

    def autenticar(self, usuario=None):
        self.cliente.force_login(usuario or self.cenario.usuario_a)

    def test_painel_exige_sessao_e_entrega_interface_somente_leitura(self):
        self.assertEqual(self.cliente.get('/').status_code, 302)
        for rota in ('/dados/conversas/', '/dados/relatorio/', '/contatos.csv'):
            with self.subTest(rota=rota):
                self.assertEqual(self.cliente.get(rota).status_code, 401)
        self.autenticar()
        resposta = self.cliente.get('/')
        html = resposta.content.decode()
        self.assertEqual(resposta.status_code, 200)
        self.assertIn('Conversas', html)
        self.assertIn('Relatórios', html)
        self.assertIn('somente para monitoramento', html)
        self.assertNotIn('Enviar mensagem', html)
        self.assertIn("default-src 'self'", resposta.headers['Content-Security-Policy'])
        self.assertIn('no-store', resposta.headers['Cache-Control'])

    def test_endpoints_usam_unidade_do_usuario_autenticado(self):
        for usuario, unidade in ((self.cenario.usuario_a, 10), (self.cenario.usuario_b, 20)):
            with self.subTest(unidade=unidade):
                self.cliente = Client()
                self.autenticar(usuario)
                with patch('monitoramento.views.carregar_conversas', return_value=CONVERSAS) as carregar:
                    resposta = self.cliente.get('/dados/conversas/')
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(carregar.call_args.args[0].id_unidade, unidade)

    def test_mensagens_de_cliente_inexistente_ou_de_outro_escopo_nao_vazam(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_mensagens', return_value={'id_cliente': 999, 'mensagens': []}) as carregar:
            resposta = self.cliente.get('/dados/conversas/999/')
        self.assertEqual(resposta.status_code, 404)
        self.assertEqual(carregar.call_args.args[0].id_unidade, 10)
        self.assertNotIn('Unidade B', resposta.content.decode())

    def test_periodo_invalido_e_metodos_de_escrita_sao_recusados(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_conversas') as carregar:
            self.assertEqual(self.cliente.get('/dados/conversas/?periodo=qualquer').status_code, 400)
            carregar.assert_not_called()
        for rota in ('/dados/conversas/', '/dados/relatorio/', '/contatos.csv'):
            self.assertEqual(self.cliente.post(rota).status_code, 405)

    def test_csv_google_completo_e_elegivel(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_contatos', return_value=CONTATOS):
            completo = self.cliente.get('/contatos.csv?tipo=todos')
            elegivel = self.cliente.get('/contatos.csv?tipo=elegiveis')
        self.assertFalse(completo.content.startswith(b'\xef\xbb\xbf'))
        linhas = list(csv.reader(StringIO(completo.content.decode('utf-8'))))
        self.assertEqual(linhas[0], CABECALHO_OFICIAL_GOOGLE_CONTATOS)
        self.assertTrue(all(len(linha) == 36 for linha in linhas))
        self.assertEqual(linhas[1][1], 'Edcarlos')
        self.assertEqual(linhas[1][3], 'Silva')
        self.assertEqual(
            linhas[1][10:14],
            ['Work', 'edcarlos@example.com', 'Mobile', '+557194111866'],
        )
        self.assertTrue(all(not valor for valor in linhas[1][14:34]))
        self.assertEqual(
            linhas[1][34],
            'Contato exportado pelo monitoramento ESL Tech',
        )
        self.assertTrue(linhas[1][35])
        self.assertEqual(linhas[2][10:12], ['', ''])
        self.assertEqual(linhas[2][12:14], ['Mobile', '+557599111222'])
        self.assertEqual(len(linhas), 3)
        linhas_elegiveis = list(csv.reader(StringIO(elegivel.content.decode('utf-8'))))
        self.assertEqual(len(linhas_elegiveis), 2)
        self.assertTrue(all(len(linha) == 36 for linha in linhas_elegiveis))
        self.assertEqual(normalizar_telefone_google('(71) 94111-1866'), '+5571941111866')
        self.assertEqual(normalizar_telefone_google('123'), '')

        contato_invalido = [{
            'nome': 'Contato Inválido', 'email': 'sem-arroba',
            'waid_telefone': '557194111866',
        }]
        with patch('monitoramento.views.carregar_contatos', return_value=contato_invalido):
            elegivel = self.cliente.get('/contatos.csv?tipo=elegiveis')
        self.assertEqual(
            len(list(csv.reader(StringIO(elegivel.content.decode('utf-8'))))), 1
        )

    def test_csv_essencial_preserva_nome_completo_acentos_e_campos_vazios(self):
        self.autenticar()
        contatos = [
            {'nome': ' João da Silva ', 'email': 'joao@example.com', 'waid_telefone': '557194111866'},
            {'nome': None, 'email': None, 'waid_telefone': '557599111222'},
            {'nome': 'Sem telefone', 'email': 'outro@example.com', 'waid_telefone': None},
            {'nome': '=Nome; "especial"', 'email': '=1+1', 'waid_telefone': '123'},
        ]
        with patch('monitoramento.views.carregar_contatos', return_value=contatos):
            completo = self.cliente.get('/contatos.csv?formato=essencial&tipo=todos')
            elegivel = self.cliente.get('/contatos.csv?formato=essencial&tipo=elegiveis')
        self.assertTrue(completo.content.startswith(b'\xef\xbb\xbf'))
        linhas = list(csv.reader(StringIO(completo.content.decode('utf-8-sig')), delimiter=';'))
        self.assertEqual(linhas, [
            ['Nome', 'E-mail', 'Telefone'],
            ['João da Silva', 'joao@example.com', '7194111866'],
            ['', '', '7599111222'],
            ['Sem telefone', 'outro@example.com', ''],
            ["'=Nome; \"especial\"", "'=1+1", ''],
        ])
        self.assertEqual(
            list(csv.reader(StringIO(elegivel.content.decode('utf-8-sig')), delimiter=';')),
            linhas[:2],
        )
        self.assertIn('contatos_essenciais_total_todos.csv', completo['Content-Disposition'])
        self.assertIn('no-store', completo['Cache-Control'])

    def test_quatro_exports_respeitam_todos_periodos_e_unidade_autorizada(self):
        agora = datetime(2026, 9, 7, 12, tzinfo=timezone.utc)
        for usuario, unidade in ((self.cenario.usuario_a, 10), (self.cenario.usuario_b, 20)):
            self.cliente = Client()
            self.autenticar(usuario)
            for chave in ('total', *PERIODOS):
                periodo = resolver_periodo(chave, agora=agora)
                for formato in ('google', 'essencial'):
                    for tipo in ('todos', 'elegiveis'):
                        with self.subTest(unidade=unidade, periodo=chave, formato=formato, tipo=tipo):
                            with patch('monitoramento.views.resolver_periodo', return_value=periodo) as resolver, \
                                 patch('monitoramento.views.carregar_contatos', return_value=CONTATOS) as carregar:
                                resposta = self.cliente.get('/contatos.csv', {
                                    'formato': formato, 'tipo': tipo, 'periodo': chave,
                                    'id_unidade': 999,
                                })
                            self.assertEqual(resposta.status_code, 200)
                            resolver.assert_called_once_with(chave)
                            acesso, recebido = carregar.call_args.args
                            self.assertEqual(acesso.id_unidade, unidade)
                            self.assertEqual(recebido, periodo)
                            leitor = csv.reader(
                                StringIO(resposta.content.decode('utf-8-sig')),
                                delimiter=';' if formato == 'essencial' else ',',
                            )
                            linhas = list(leitor)
                            self.assertEqual(len(linhas), 2 if tipo == 'elegiveis' else 3)
                            self.assertTrue(all(len(linha) == (3 if formato == 'essencial' else 36) for linha in linhas))
                            self.assertEqual(
                                linhas[1][2 if formato == 'essencial' else 13],
                                '7194111866' if formato == 'essencial' else '+557194111866',
                            )
                            self.assertIn(f'_{chave}_{tipo}.csv', resposta['Content-Disposition'])

    def test_export_essencial_recusa_acesso_invalido_e_parametros_invalidos(self):
        rota = '/contatos.csv?formato=essencial'
        with patch('monitoramento.views.carregar_contatos') as carregar:
            self.assertEqual(self.cliente.get(rota).status_code, 401)
            self.autenticar()
            self.assertEqual(self.cliente.get(rota + '&periodo=invalido').status_code, 400)
            self.assertEqual(self.cliente.get('/contatos.csv?formato=invalido').status_code, 400)
            self.assertEqual(self.cliente.post(rota).status_code, 405)
            with self.cenario.banco.cursor() as cursor:
                cursor.execute('UPDATE unidade SET id_usuario_monitoramento = NULL WHERE id_unidade = 10')
            self.assertEqual(self.cliente.get(rota).status_code, 403)
            carregar.assert_not_called()

    def test_botoes_historicos_vem_do_catalogo_oficial(self):
        mensagem = {'quem_enviou': 'bot', 'tipo': 'interactive_button', 'id_etapa': 2}
        self.assertEqual(botoes_para_mensagem(mensagem), ['Para mim', 'Para um dependente'])
        mensagem['id_etapa'] = 12
        self.assertEqual(botoes_para_mensagem(mensagem), ['Nunca', 'Às vezes', 'Frequentemente'])
        mensagem['quem_enviou'] = 'cliente'
        self.assertEqual(botoes_para_mensagem(mensagem), [])

    def test_consolidacao_cria_tags_sem_misturar_unidades(self):
        linhas = [
            {'id_cliente': 1, 'id_conversa': 10, 'nome_cliente': 'Ana', 'waid_telefone': '5511',
             'status_dependente': True, 'idade_dependente': 12, 'foi_funil': False,
             'avaliada': False, 'ultima_atividade': '2026-09-01',
             'ultima_mensagem_id': 20, 'ultima_mensagem': 'Oi'},
            {'id_cliente': 1, 'id_conversa': 11, 'nome_cliente': 'Ana', 'waid_telefone': '5511',
             'status_dependente': False, 'idade_titular': 65, 'foi_funil': True,
             'avaliada': True, 'ultima_atividade': '2026-09-01',
             'ultima_mensagem_id': 21, 'ultima_mensagem': 'Olá'},
        ]
        resultado = consolidar_conversas(linhas)
        self.assertEqual(resultado[0]['ids_conversa'], [10, 11])
        self.assertEqual(resultado[0]['perfis'], ['dependente', 'menor', 'idoso'])
        self.assertEqual(resultado[0]['perfis_resumidos'], ['dependente_menor', 'idoso'])
        self.assertEqual(resultado[0]['ultima_mensagem'], 'Olá')

    def test_perfis_resumidos_distinguem_dependentes_e_titulares(self):
        cenarios = (
            (1, True, 12, 'dependente_menor'),
            (2, True, 35, 'dependente_adulto'),
            (3, True, 65, 'dependente_idoso'),
            (4, False, 35, 'adulto'),
            (5, False, 65, 'idoso'),
        )
        linhas = []
        for id_cliente, dependente, idade, esperado in cenarios:
            linhas.append({
                'id_cliente': id_cliente,
                'id_conversa': id_cliente * 10,
                'nome_cliente': f'Cliente {id_cliente}',
                'waid_telefone': f'551{id_cliente}',
                'status_dependente': dependente,
                'idade_dependente': idade if dependente else None,
                'idade_titular': None if dependente else idade,
                'foi_funil': False,
                'avaliada': False,
                'ultima_atividade': f'2026-09-0{id_cliente}',
                'ultima_mensagem_id': id_cliente,
                'ultima_mensagem': esperado,
            })

        resultado = {item['id_cliente']: item for item in consolidar_conversas(linhas)}
        for id_cliente, _dependente, _idade, esperado in cenarios:
            self.assertEqual(resultado[id_cliente]['perfis_resumidos'], [esperado])

    def test_periodos_finitos_possuem_comparacao_e_total_nao(self):
        finito = resolver_periodo('7d')
        total = resolver_periodo('total')
        self.assertEqual(finito.fim_anterior, finito.inicio)
        self.assertIsNotNone(finito.inicio_anterior)
        self.assertIsNone(total.inicio)
        self.assertIsNone(total.inicio_anterior)

    def test_comparacao_aceita_periodo_atual_sem_avaliacoes(self):
        relatorio = montar_relatorio(
            {'leads': 2, 'mensagens': 4, 'funil': 1, 'avaliacoes': 0, 'nota_media': None},
            {'leads': 1, 'mensagens': 2, 'funil': 0, 'avaliacoes': 1, 'nota_media': 5.0},
            {}, {}, [], [], encaminhados_comercial_por_idade=0,
        )
        self.assertIsNone(relatorio['tendencias']['nota_media'])

    def test_perfil_so_conta_lead_totalmente_sem_classificacao(self):
        perfis = _agrupar_perfis([
            {'id_cliente': 1, 'status_dependente': None, 'idade_titular': 35,
             'idade_dependente': None, 'foi_funil': False},
            {'id_cliente': 1, 'status_dependente': False, 'idade_titular': 35,
             'idade_dependente': None, 'foi_funil': True},
            {'id_cliente': 2, 'status_dependente': None, 'idade_titular': 44,
             'idade_dependente': None, 'foi_funil': False},
        ], bpa_ativo=False)
        titular_adulto = next(
            item for item in perfis['linhas'] if item['chave'] == 'titular_adulto'
        )
        self.assertEqual(titular_adulto['leads'], 1)
        self.assertEqual(perfis['sem_classificacao'], 1)

    def test_relatorio_e_conversas_sao_serializados_sem_consultar_rds(self):
        self.autenticar()
        with patch('monitoramento.views.carregar_relatorio', return_value=RELATORIO):
            resposta = self.cliente.get('/dados/relatorio/?periodo=7d')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(len(resposta.json()['etapas']), 22)
        with patch('monitoramento.views.carregar_mensagens', return_value=MENSAGENS[140]):
            resposta = self.cliente.get('/dados/conversas/140/')
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json()['mensagens'][1]['botoes'][0], 'Para mim')

    def test_todas_as_consultas_recebem_escopo_e_parametros_completos(self):
        class CursorContrato:
            description = [('valor',)]

            def __init__(self):
                self.execucoes = []

            def execute(self, sql, parametros):
                self.execucoes.append((sql, parametros))
                if sql.count('%s') != len(parametros):
                    raise AssertionError(
                        f'placeholders={sql.count("%s")} parametros={len(parametros)}'
                    )

            def fetchall(self):
                return []

            def fetchone(self):
                return None

        agora = datetime.now(timezone.utc)
        inicio = agora - timedelta(days=7)
        chamadas = (
            lambda c: repositorio_painel.buscar_unidade(10, c),
            lambda c: repositorio_painel.listar_conversas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_mensagens(10, 99, inicio, agora, c),
            lambda c: repositorio_painel.buscar_metricas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_perfis(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_satisfacao(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_etapas(10, inicio, agora, c),
            lambda c: repositorio_painel.buscar_atividade(10, inicio, agora, c, 'dia'),
            lambda c: repositorio_painel.listar_contatos(10, inicio, agora, c),
        )
        for chamada in chamadas:
            with self.subTest(chamada=chamada):
                cursor = CursorContrato()
                chamada(cursor)
                sql, parametros = cursor.execucoes[0]
                self.assertIn(10, parametros)
                self.assertIn('id_unidade', sql)
```

### Passo 23 — `tests/unit/test_metricas_perfis_relatorios.py`

**Ação:** Alterar. Provar que todas as seis configurações preservam os envios observados e as faixas.

Conteúdo completo do arquivo:

```python
from __future__ import annotations

import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from utilitarios.reports_functions import weekly


class MetricasPerfisRelatoriosTests(unittest.TestCase):
    FIM = datetime(2026, 8, 30, 15, tzinfo=timezone.utc)
    INICIO = FIM - timedelta(days=7)

    @staticmethod
    def _perfil(
        id_cliente: int,
        id_conversa: int,
        *,
        id_unidade: int = 1,
        status_dependente: object = False,
        idade_titular: object = 35,
        idade_dependente: object = None,
    ) -> dict[str, object]:
        return {
            "id_unidade": id_unidade,
            "id_cliente": id_cliente,
            "id_conversa": id_conversa,
            "status_dependente": status_dependente,
            "idade_titular": idade_titular,
            "idade_dependente": idade_dependente,
        }

    def _mensagem(self, perfil: dict[str, object], id_mensagem: int) -> dict[str, object]:
        return {
            **perfil,
            "id_mensagem": id_mensagem,
            "received_data_hora": self.INICIO + timedelta(minutes=id_mensagem),
            "quem_enviou": "cliente",
            "tipo_mensagem": "text",
            "conteudo_texto": "Olá",
        }

    @staticmethod
    def _unidade(
        id_unidade: int = 1, *, idade_minima_suporte: int | None = None, bpa_ativo: bool = False
    ) -> dict[str, object]:
        return {
            "id_unidade": id_unidade,
            "nome_unidade": f"Unidade {id_unidade}",
            "idade_minima_suporte": idade_minima_suporte,
            "bpa_ativo": bpa_ativo,
        }

    @staticmethod
    def _linhas(segmentacao: dict[str, object]) -> dict[str, dict[str, object]]:
        return {linha["chave"]: linha for linha in segmentacao["linhas"]}

    def _segmentacao(
        self,
        perfis: list[dict[str, object]],
        enviados: set[int] | None = None,
        *,
        idade_minima_suporte: int | None = None,
        bpa_ativo: bool = False,
    ) -> dict[str, object]:
        return weekly._montar_segmentacao_perfis(
            perfis,
            enviados or set(),
            idade_minima_suporte=idade_minima_suporte,
            bpa_ativo=bpa_ativo,
        )

    def _snapshot(
        self,
        mensagens: list[dict[str, object]],
        funil: list[dict[str, object]],
        unidades: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        return weekly.montar_snapshot(
            [self._unidade()] if unidades is None else unidades,
            mensagens,
            funil,
            [],
            self.INICIO,
            self.FIM,
        )

    def test_fronteiras_dependentes_com_minimo_padrao_e_bpa(self) -> None:
        casos = {
            3: (None, None),
            4: (None, "dependente_infantil"),
            5: ("dependente_infantil", "dependente_infantil"),
            17: ("dependente_infantil", "dependente_infantil"),
            18: ("dependente_adulto", "dependente_adulto"),
            45: ("dependente_adulto", "dependente_adulto"),
            59: ("dependente_adulto", "dependente_adulto"),
            60: ("dependente_idoso", "dependente_idoso"),
            99: ("dependente_idoso", "dependente_idoso"),
            100: (None, None),
        }
        for idade, resultados in casos.items():
            for minimo, esperado in zip((5, 4), resultados):
                with self.subTest(idade=idade, minimo=minimo):
                    self.assertEqual(
                        weekly._classificar_perfil_atendimento(
                            status_dependente=True,
                            idade_titular=60,
                            idade_dependente=idade,
                            idade_minima_dependente=minimo,
                        ),
                        esperado,
                    )

    def test_fronteiras_titulares_e_45_permanece_adulto(self) -> None:
        casos = {
            3: None,
            4: None,
            5: None,
            17: None,
            18: "titular_adulto",
            45: "titular_adulto",
            59: "titular_adulto",
            60: "titular_idoso",
            99: "titular_idoso",
            100: None,
        }
        for idade, esperado in casos.items():
            with self.subTest(idade=idade):
                self.assertEqual(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=False,
                        idade_titular=idade,
                        idade_dependente=10,
                        idade_minima_dependente=5,
                    ),
                    esperado,
                )

    def test_idades_nulas_booleanas_fracionarias_e_legadas_sao_desconhecidas(self) -> None:
        for idade in (None, True, False, 18.0, 18.5, "18", "", -1, 0, 100):
            for dependente in (True, False):
                with self.subTest(idade=idade, tipo=type(idade), dependente=dependente):
                    self.assertIsNone(
                        weekly._classificar_perfil_atendimento(
                            status_dependente=dependente,
                            idade_titular=60 if dependente else idade,
                            idade_dependente=idade if dependente else 10,
                            idade_minima_dependente=4,
                        )
                    )

    def test_status_desconhecido_nao_e_inferido_das_idades(self) -> None:
        for status in (None, 0, 1, "true", "false", "", 1.0):
            with self.subTest(status=status, tipo=type(status)):
                self.assertIsNone(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=status,
                        idade_titular=35,
                        idade_dependente=10,
                        idade_minima_dependente=5,
                    )
                )

    def test_so_a_idade_da_pessoa_atendida_classifica_o_perfil(self) -> None:
        for status, titular, dependente, esperado in (
            (True, None, 10, "dependente_infantil"),
            (True, 70, 20, "dependente_adulto"),
            (True, 35, None, None),
            (False, 70, None, "titular_idoso"),
            (False, 35, 70, "titular_adulto"),
            (False, None, 10, None),
        ):
            with self.subTest(status=status, titular=titular, dependente=dependente):
                self.assertEqual(
                    weekly._classificar_perfil_atendimento(
                        status_dependente=status,
                        idade_titular=titular,
                        idade_dependente=dependente,
                        idade_minima_dependente=5,
                    ),
                    esperado,
                )

    def test_bpa_altera_apenas_o_minimo_infantil_e_seu_rotulo(self) -> None:
        perfis = [
            self._perfil(1, 101, status_dependente=True, idade_dependente=4),
            self._perfil(2, 102, status_dependente=True, idade_dependente=5),
        ]
        for bpa, minimo, leads in ((False, 5, 1), (True, 4, 2)):
            with self.subTest(bpa=bpa):
                segmentacao = self._segmentacao(perfis, {101, 102}, bpa_ativo=bpa)
                infantil = self._linhas(segmentacao)["dependente_infantil"]
                self.assertEqual(segmentacao["idade_minima_dependente"], minimo)
                self.assertEqual(infantil["rotulo"], f"Dependentes de {minimo} a 17 anos")
                self.assertEqual(infantil["leads"], leads)
                self.assertEqual(infantil["leads_funil"], leads)

    def test_duas_conversas_do_mesmo_perfil_contam_um_lead(self) -> None:
        segmentacao = self._segmentacao(
            [self._perfil(1, 101), self._perfil(1, 102), self._perfil(2, 103)],
            {101, 102},
        )
        adulto = self._linhas(segmentacao)["titular_adulto"]
        self.assertEqual(adulto["leads"], 2)
        self.assertEqual(adulto["conversas"], 3)
        self.assertEqual(adulto["leads_funil"], 1)
        self.assertEqual(adulto["leads_funil_observados"], 1)
        self.assertEqual(adulto["conversas_funil"], 2)
        self.assertEqual(adulto["conversas_funil_observadas"], 2)
        self.assertEqual(adulto["taxa_funil"], 50.0)
        self.assertEqual(segmentacao["leads_classificados"], 2)
        self.assertEqual(segmentacao["leads_multiperfil"], 0)

    def test_envio_do_dependente_nao_e_herdado_pelo_titular(self) -> None:
        titular = self._perfil(1, 101)
        dependente = self._perfil(1, 102, status_dependente=True, idade_dependente=10)
        snapshot = self._snapshot(
            [self._mensagem(titular, 1), self._mensagem(dependente, 2)],
            [dependente],
        )
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        linhas = self._linhas(segmentacao)

        self.assertEqual(unidade["metricas"]["leads_contato"], 1)
        self.assertEqual(unidade["metricas"]["leads_funil"], 1)
        self.assertTrue(unidade["conversas"][0]["foi_funil"])
        self.assertEqual(linhas["dependente_infantil"]["leads_funil"], 1)
        self.assertEqual(linhas["titular_adulto"]["leads_funil"], 0)
        self.assertEqual(linhas["titular_adulto"]["leads_funil_observados"], 0)
        self.assertEqual(segmentacao["leads_classificados"], 1)
        self.assertEqual(segmentacao["leads_multiperfil"], 1)

    def test_mensagens_e_envios_repetidos_nao_duplicam_perfis_no_snapshot(self) -> None:
        perfil = self._perfil(1, 101)
        snapshot = self._snapshot(
            [self._mensagem(perfil, 1), self._mensagem(perfil, 2)],
            [perfil, perfil],
        )
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        adulto = self._linhas(segmentacao)["titular_adulto"]
        self.assertEqual(len(unidade["perfis_atendimento"]), 1)
        self.assertEqual(len(unidade["conversas"][0]["mensagens"]), 2)
        self.assertEqual(adulto["conversas"], 1)
        self.assertEqual(adulto["conversas_funil"], 1)
        self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 0)

    def test_cliente_compartilhado_nao_mistura_envios_entre_unidades(self) -> None:
        perfil_a = self._perfil(1, 101, id_unidade=1)
        perfil_b = self._perfil(1, 201, id_unidade=2)
        snapshot = self._snapshot(
            [self._mensagem(perfil_a, 1), self._mensagem(perfil_b, 2)],
            [perfil_a],
            [self._unidade(1), self._unidade(2)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        for id_unidade, enviado in ((1, 1), (2, 0)):
            with self.subTest(id_unidade=id_unidade):
                metricas = unidades[id_unidade]["metricas"]
                linha = self._linhas(metricas["segmentacao_perfis"])["titular_adulto"]
                self.assertEqual(metricas["leads_contato"], 1)
                self.assertEqual(metricas["leads_funil"], enviado)
                self.assertEqual(linha["leads_funil"], enviado)
                self.assertEqual(linha["conversas"], 1)

    def test_configuracao_bpa_e_aplicada_por_unidade(self) -> None:
        perfis = [
            self._perfil(1, unidade * 100, id_unidade=unidade,
                         status_dependente=True, idade_dependente=4)
            for unidade in (1, 2)
        ]
        snapshot = self._snapshot(
            [self._mensagem(perfil, indice) for indice, perfil in enumerate(perfis, 1)],
            perfis,
            [self._unidade(1), self._unidade(2, bpa_ativo=True)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        for id_unidade, esperado in ((1, 0), (2, 1)):
            with self.subTest(id_unidade=id_unidade):
                segmentacao = unidades[id_unidade]["metricas"]["segmentacao_perfis"]
                infantil = self._linhas(segmentacao)["dependente_infantil"]
                self.assertEqual(infantil["leads"], esperado)
                self.assertEqual(infantil["leads_funil"], esperado)

    def test_retry_de_conversa_antiga_preserva_perfil_sem_importar_mensagens(self) -> None:
        antiga = self._perfil(1, 101, status_dependente=True, idade_dependente=17)
        nova = self._perfil(1, 102, idade_titular=45)
        snapshot = self._snapshot([self._mensagem(nova, 1)], [antiga])
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        linhas = self._linhas(segmentacao)

        self.assertEqual(unidade["metricas"]["leads_funil"], 1)
        self.assertEqual(unidade["conversas"][0]["ids_conversa"], [102])
        self.assertEqual(len(unidade["conversas"][0]["mensagens"]), 1)
        self.assertEqual({p["id_conversa"] for p in unidade["perfis_atendimento"]}, {101, 102})
        self.assertEqual(linhas["dependente_infantil"]["leads_funil"], 1)
        self.assertEqual(linhas["titular_adulto"]["leads_funil"], 0)
        self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 1)
        self.assertEqual(segmentacao["conversas_classificadas"], 2)
        self.assertEqual(segmentacao["leads_multiperfil"], 1)

    def test_funil_fora_da_coorte_nao_acrescenta_lead_nem_perfil(self) -> None:
        contato = self._perfil(1, 101)
        fora_da_coorte = self._perfil(2, 201, idade_titular=60)
        outra_unidade = self._perfil(1, 301, id_unidade=2, idade_titular=60)
        snapshot = self._snapshot(
            [self._mensagem(contato, 1)],
            [fora_da_coorte, outra_unidade],
            [self._unidade(1), self._unidade(2)],
        )
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}
        self.assertEqual(unidades[1]["metricas"]["leads_contato"], 1)
        self.assertEqual(unidades[2]["metricas"]["leads_contato"], 0)
        for unidade in unidades.values():
            segmentacao = unidade["metricas"]["segmentacao_perfis"]
            self.assertEqual(unidade["metricas"]["leads_funil"], 0)
            self.assertEqual(self._linhas(segmentacao)["titular_idoso"]["leads"], 0)
            self.assertEqual(segmentacao["conversas_apenas_envio_funil"], 0)

    def test_idade_minima_suporte_nao_apaga_envios_observados_nem_afeta_dependente(self) -> None:
        perfis = [
            self._perfil(1, 101, idade_titular=60),
            self._perfil(1, 102, idade_titular=60),
            self._perfil(2, 201, status_dependente=True, idade_dependente=60),
        ]
        for suporte in (None, 50, 60, 70, 80, 90):
            with self.subTest(suporte=suporte):
                segmentacao = self._segmentacao(perfis, {101, 102, 201}, idade_minima_suporte=suporte)
                linhas = self._linhas(segmentacao)
                titular = linhas["titular_idoso"]
                self.assertEqual(titular["leads"], 1)
                self.assertEqual(titular["conversas"], 2)
                self.assertEqual(titular["leads_funil_observados"], 1)
                self.assertEqual(titular["conversas_funil_observadas"], 2)
                self.assertEqual(titular["leads_funil"], 1)
                self.assertEqual(titular["conversas_funil"], 2)
                self.assertEqual(titular["taxa_funil"], 100.0)
                self.assertFalse(titular["funil_nao_aplicavel"])
                self.assertEqual(linhas["dependente_idoso"]["leads_funil"], 1)
                self.assertEqual(linhas["dependente_idoso"]["taxa_funil"], 100.0)
                self.assertFalse(linhas["dependente_idoso"]["funil_nao_aplicavel"])

    def test_suporte_atual_preserva_funil_geral_do_snapshot(self) -> None:
        perfil = self._perfil(1, 101, idade_titular=60)
        snapshot = self._snapshot(
            [self._mensagem(perfil, 1)], [perfil], [self._unidade(idade_minima_suporte=60)]
        )
        metricas = snapshot["unidades"][0]["metricas"]
        titular = self._linhas(metricas["segmentacao_perfis"])["titular_idoso"]
        self.assertEqual(metricas["leads_funil"], 1)
        self.assertEqual(titular["leads_funil_observados"], 1)
        self.assertEqual(titular["leads_funil"], 1)
        self.assertEqual(titular["taxa_funil"], 100.0)

    def test_todos_os_perfis_empatados_sao_predominantes_por_leads(self) -> None:
        perfis = [
            self._perfil(1, 101),
            self._perfil(1, 102),
            self._perfil(2, 201, status_dependente=True, idade_dependente=10),
        ]
        segmentacao = self._segmentacao(perfis)
        self.assertCountEqual(
            segmentacao["perfis_predominantes"],
            ["Titulares de 18 a 59 anos", "Dependentes de 5 a 17 anos"],
        )

    def test_desconhecidos_separam_leads_conversas_e_envios_nao_classificados(self) -> None:
        perfis = [
            self._perfil(1, 101, status_dependente=None),
            self._perfil(1, 102),
            self._perfil(2, 201, status_dependente=None),
            self._perfil(2, 202),
            self._perfil(3, 301, idade_titular=None),
        ]
        # O envio do cliente 1 só tem perfil desconhecido; o do cliente 2 tem ambos.
        segmentacao = self._segmentacao(perfis, {101, 201, 202})
        self.assertEqual(segmentacao["leads_classificados"], 2)
        self.assertEqual(segmentacao["leads_sem_classificacao"], 1)
        self.assertEqual(segmentacao["conversas_classificadas"], 2)
        self.assertEqual(segmentacao["conversas_sem_classificacao"], 3)
        self.assertEqual(segmentacao["conversas_funil_sem_classificacao"], 2)
        self.assertEqual(segmentacao["leads_funil_apenas_sem_classificacao"], 1)
        self.assertEqual(segmentacao["cobertura_conversas"], 40.0)

    def test_snapshot_vazio_mantem_cinco_perfis_sem_divisao_por_zero(self) -> None:
        snapshot = self._snapshot([], [])
        unidade = snapshot["unidades"][0]
        segmentacao = unidade["metricas"]["segmentacao_perfis"]
        self.assertEqual(unidade["conversas"], [])
        self.assertEqual(unidade["perfis_atendimento"], [])
        self.assertEqual(unidade["metricas"]["leads_contato"], 0)
        self.assertEqual(unidade["metricas"]["taxa_funil"], 0.0)
        self.assertEqual(segmentacao["perfis_predominantes"], [])
        self.assertEqual(segmentacao["cobertura_conversas"], 0.0)
        self.assertEqual(segmentacao["leads_funil_apenas_sem_classificacao"], 0)
        self.assertEqual(set(self._linhas(segmentacao)), set(weekly.PERFIS_ATENDIMENTO))
        for linha in segmentacao["linhas"]:
            with self.subTest(perfil=linha["chave"]):
                for campo in ("leads", "conversas", "leads_funil", "conversas_funil",
                              "leads_funil_observados", "conversas_funil_observadas"):
                    self.assertEqual(linha[campo], 0)
                self.assertEqual(linha["taxa_funil"], 0.0)
        self.assertEqual(self._snapshot([], [], unidades=[])["unidades"], [])

    def test_sql_seleciona_perfis_por_conversa_com_janela_semiaberta_e_so_leitura(self) -> None:
        cursor = mock.MagicMock()
        cursor.fetchall.side_effect = [[self._unidade()], [], [], []]
        cursor.fetchone.return_value = {"existe": False}
        conn = mock.MagicMock()
        conn.cursor.return_value = cursor
        driver = types.ModuleType("psycopg")
        rows = types.ModuleType("psycopg.rows")
        rows.dict_row = object()
        driver.rows = rows

        with mock.patch.dict(sys.modules, {"psycopg": driver, "psycopg.rows": rows}):
            snapshot = weekly.coletar_snapshot(
                conn, self.INICIO, self.FIM, ids_unidade=[1], max_mensagens=100
            )

        consultas = [
            (" ".join(chamada.args[0].lower().split()), chamada.args[1:])
            for chamada in cursor.execute.call_args_list
        ]
        self.assertEqual(
            consultas[0][0],
            "begin transaction isolation level repeatable read read only",
        )
        sql_mensagens, params_mensagens = next(
            item for item in consultas if "with clientes_janela as" in item[0]
        )
        sql_funil, params_funil = next(
            item for item in consultas if "from chatbot.funil_envios f" in item[0]
        )
        for sql in (sql_mensagens, sql_funil):
            with self.subTest(consulta="funil" if sql == sql_funil else "mensagens"):
                for coluna in (
                    "c.id_conversa", "c.status_dependente", "cl.idade as idade_titular",
                    "d.idade as idade_dependente", "d.nome_dependente",
                ):
                    self.assertIn(coluna, sql)
                self.assertIn(
                    "left join chatbot.dependente d on d.id_conversa = c.id_conversa "
                    "and d.id_cliente = c.id_cliente",
                    sql,
                )
                self.assertIn("u.id_unidade = any(%s)", sql)
        self.assertIn("h0.quem_enviou = 'cliente'", sql_mensagens)
        self.assertIn("h0.received_data_hora >= %s", sql_mensagens)
        self.assertIn("h0.received_data_hora < %s", sql_mensagens)
        self.assertIn("h.received_data_hora >= %s", sql_mensagens)
        self.assertIn("h.received_data_hora < %s", sql_mensagens)
        self.assertIn("f.status = 'sent'", sql_funil)
        self.assertIn("f.enviado_em >= %s", sql_funil)
        self.assertIn("f.enviado_em < %s", sql_funil)
        self.assertEqual(
            params_mensagens,
            ((self.INICIO, self.FIM, [1], self.INICIO, self.FIM, 101),),
        )
        self.assertEqual(params_funil, ((self.INICIO, self.FIM, [1]),))
        for sql, _ in consultas:
            self.assertNotRegex(sql, r"\b(insert|update|delete|drop|truncate|alter)\b")
        conn.cursor.assert_called_once_with(row_factory=rows.dict_row)
        conn.rollback.assert_called_once_with()
        conn.commit.assert_not_called()
        cursor.close.assert_called_once_with()
        self.assertEqual(snapshot["unidades"][0]["metricas"]["leads_contato"], 0)


if __name__ == "__main__":
    unittest.main()
```

### Passo 24 — `tests/unit/test_gerar_monitoramento_unidades.py`

**Ação:** Alterar. Atualizar os snapshots e resultados dos relatórios sem apagar o Funil de titulares 60+.

Conteúdo completo do arquivo:

```python
from __future__ import annotations

import re
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from utilitarios.reports_functions import total
from utilitarios.reports_functions import weekly as monitoramento


class GerarMonitoramentoUnidadesTests(unittest.TestCase):
    FIM = datetime(2026, 8, 27, 15, 0, tzinfo=timezone.utc)
    INICIO = FIM - timedelta(days=7)

    @staticmethod
    def _mensagem(
        *,
        id_unidade: int,
        id_cliente: int,
        id_conversa: int,
        id_mensagem: int,
        quando: datetime,
        profissao_cliente: str | None = None,
        profissao_conversa: str | None = None,
        nome: str = "Maria",
        texto: str = "Olá",
        quem_enviou: str = "cliente",
        status_dependente: bool | None = False,
        idade_titular: int | None = 35,
        idade_dependente: int | None = None,
    ) -> dict[str, object]:
        return {
            "id_unidade": id_unidade,
            "id_cliente": id_cliente,
            "nome_cliente": nome,
            "waid_telefone": f"55{id_cliente}",
            "email": f"cliente{id_cliente}@example.test",
            "profissao_cliente": profissao_cliente,
            "profissao_conversa_recente": profissao_conversa,
            "id_conversa": id_conversa,
            "status_ativa": id_conversa == 122,
            "status_dependente": status_dependente,
            "id_etapa_atual": 5,
            "idade_titular": idade_titular,
            "idade_dependente": idade_dependente,
            "id_mensagem": id_mensagem,
            "id_etapa": 4,
            "received_data_hora": quando,
            "quem_enviou": quem_enviou,
            "tipo_mensagem": "text",
            "conteudo_texto": texto,
        }

    def _snapshot(self) -> dict[str, object]:
        unidades = [
            {
                "id_unidade": 1,
                "nome_unidade": "Supera SAJ",
                "nome_agente": "Suh",
                "idade_minima_suporte": None,
                "bpa_ativo": False,
            },
            {
                "id_unidade": 2,
                "nome_unidade": "Supera Rio Vermelho",
                "nome_agente": "Lia",
                "idade_minima_suporte": None,
                "bpa_ativo": False,
            },
        ]
        mensagens = [
            self._mensagem(
                id_unidade=1,
                id_cliente=10,
                id_conversa=121,
                id_mensagem=1,
                quando=self.INICIO + timedelta(hours=1),
                profissao_cliente="Professora",
                profissao_conversa="Autônoma",
            ),
            self._mensagem(
                id_unidade=1,
                id_cliente=10,
                id_conversa=122,
                id_mensagem=2,
                quando=self.INICIO + timedelta(days=1),
                profissao_cliente="Professora",
                profissao_conversa="Autônoma",
                texto="Continuação",
            ),
            self._mensagem(
                id_unidade=1,
                id_cliente=20,
                id_conversa=123,
                id_mensagem=3,
                quando=self.INICIO + timedelta(days=2),
                profissao_cliente="  ",
                profissao_conversa="Pedreira",
                nome="Joana",
            ),
            self._mensagem(
                id_unidade=2,
                id_cliente=10,
                id_conversa=130,
                id_mensagem=4,
                quando=self.INICIO + timedelta(days=3),
                profissao_cliente="Professora",
                nome="Maria",
            ),
        ]
        funil = [
            {"id_unidade": 1, "id_cliente": 10, "id_conversa": 122},
            {"id_unidade": 1, "id_cliente": 999},  # não contatou na janela
            {"id_unidade": 2, "id_cliente": 10, "id_conversa": 130},
        ]
        return monitoramento.montar_snapshot(
            unidades, mensagens, funil, [], self.INICIO, self.FIM
        )

    def test_resolver_janela_de_sete_dias(self) -> None:
        inicio, fim = monitoramento.resolver_janela(dias=7, ate=self.FIM)

        self.assertEqual(fim, self.FIM)
        self.assertEqual(inicio, self.INICIO)
        self.assertEqual(fim - inicio, timedelta(days=7))

    def test_saida_padrao_continua_na_raiz_do_projeto_apos_mover_modulo(self) -> None:
        esperado = Path(monitoramento.__file__).resolve().parents[2] / "monitoramento"

        self.assertEqual(monitoramento.SAIDA_PADRAO, esperado)
        self.assertEqual(total.SAIDA_PADRAO, esperado)

    def test_nome_de_unidade_e_seguro_inclusive_para_reservados_windows(self) -> None:
        self.assertEqual(
            monitoramento.sanear_nome_unidade(" Supera Rio: Vermelho/ ", 2),
            "Rio Vermelho",
        )
        self.assertEqual(
            monitoramento.sanear_nome_unidade("Supera Santo Antônio de Jesus", 1),
            "SAJ",
        )
        self.assertEqual(monitoramento.sanear_nome_unidade("CON", 7), "CON 7")
        self.assertNotIn(
            monitoramento.sanear_nome_unidade("Supera <SAJ>|*?", 1).upper(),
            {"CON", "PRN", "AUX", "NUL"},
        )

    def test_resolver_pastas_revalida_tambem_o_nome_alternativo(self) -> None:
        unidades = [
            {"id_unidade": 1, "nome_unidade": "Supera Centro"},
            {"id_unidade": 2, "nome_unidade": "Supera Centro"},
            {"id_unidade": 3, "nome_unidade": "Supera Centro (2)"},
        ]

        pastas = monitoramento.resolver_pastas_unidades(unidades)

        self.assertEqual(len({nome.casefold() for nome in pastas.values()}), 3)

    def test_conversas_do_mesmo_cliente_e_unidade_sao_unificadas(self) -> None:
        snapshot = self._snapshot()
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}

        conversas_saj = {
            item["id_cliente"]: item for item in unidades[1]["conversas"]
        }
        self.assertEqual(conversas_saj[10]["ids_conversa"], [121, 122])
        self.assertEqual(len(conversas_saj[10]["mensagens"]), 2)
        self.assertEqual(unidades[2]["conversas"][0]["ids_conversa"], [130])

    def test_funil_e_limitado_a_coorte_que_contatou_na_janela(self) -> None:
        snapshot = self._snapshot()
        unidades = {item["id_unidade"]: item for item in snapshot["unidades"]}

        self.assertEqual(unidades[1]["metricas"]["leads_contato"], 2)
        self.assertEqual(unidades[1]["metricas"]["leads_funil"], 1)
        self.assertEqual(unidades[1]["metricas"]["taxa_funil"], 50.0)
        self.assertEqual(unidades[2]["metricas"]["leads_funil"], 1)

    def test_segmentacao_etaria_usa_conversa_exata_e_evitar_sobreposicao(self) -> None:
        unidade = {
            "id_unidade": 1,
            "nome_unidade": "Supera SAJ",
            "nome_agente": "Suh",
            "idade_minima_suporte": None,
            "bpa_ativo": False,
        }
        perfis = [
            (1, 501, True, None, 5),
            (2, 502, True, None, 17),
            (3, 503, True, None, 18),
            (4, 504, True, None, 59),
            (5, 505, True, None, 60),
            (6, 506, False, 18, None),
            (7, 507, False, 59, None),
            (8, 508, False, 60, None),
            (9, 509, None, 30, None),
            # O mesmo contato também iniciou um atendimento para si.
            (1, 510, False, 40, None),
        ]
        mensagens = [
            self._mensagem(
                id_unidade=1,
                id_cliente=id_cliente,
                id_conversa=id_conversa,
                id_mensagem=indice,
                quando=self.INICIO + timedelta(minutes=indice),
                status_dependente=status_dependente,
                idade_titular=idade_titular,
                idade_dependente=idade_dependente,
            )
            for indice, (
                id_cliente,
                id_conversa,
                status_dependente,
                idade_titular,
                idade_dependente,
            ) in enumerate(perfis, 1)
        ]
        funil = [
            {"id_unidade": 1, "id_cliente": id_cliente, "id_conversa": id_conversa}
            for id_cliente, id_conversa in (
                (1, 501),
                (3, 503),
                (5, 505),
                (6, 506),
                (8, 508),
                (1, 510),
            )
        ]

        snapshot = monitoramento.montar_snapshot(
            [unidade], mensagens, funil, [], self.INICIO, self.FIM
        )
        segmentacao = snapshot["unidades"][0]["metricas"]["segmentacao_perfis"]
        linhas = {item["chave"]: item for item in segmentacao["linhas"]}

        self.assertEqual(
            (linhas["dependente_infantil"]["leads"], linhas["dependente_infantil"]["leads_funil"]),
            (2, 1),
        )
        self.assertEqual(
            (linhas["dependente_adulto"]["leads"], linhas["dependente_adulto"]["leads_funil"]),
            (2, 1),
        )
        self.assertEqual(
            (linhas["dependente_idoso"]["leads"], linhas["dependente_idoso"]["leads_funil"]),
            (1, 1),
        )
        self.assertEqual(
            (
                linhas["titular_adulto"]["leads"],
                linhas["titular_adulto"]["conversas"],
                linhas["titular_adulto"]["leads_funil"],
            ),
            (3, 3, 2),
        )
        self.assertEqual(
            (linhas["titular_idoso"]["leads"], linhas["titular_idoso"]["leads_funil"]),
            (1, 1),
        )
        self.assertEqual(segmentacao["conversas_classificadas"], 9)
        self.assertEqual(segmentacao["conversas_sem_classificacao"], 1)
        self.assertEqual(segmentacao["leads_multiperfil"], 1)

    def test_bpa_altera_rotulo_sem_ocultar_funil_por_politica(self) -> None:
        unidade = {
            "id_unidade": 2,
            "nome_unidade": "Supera Rio Vermelho",
            "nome_agente": "Lia",
            "idade_minima_suporte": 60,
            "bpa_ativo": True,
        }
        mensagens = [
            self._mensagem(
                id_unidade=2,
                id_cliente=1,
                id_conversa=601,
                id_mensagem=1,
                quando=self.INICIO + timedelta(minutes=1),
                status_dependente=True,
                idade_titular=None,
                idade_dependente=4,
            ),
            self._mensagem(
                id_unidade=2,
                id_cliente=2,
                id_conversa=602,
                id_mensagem=2,
                quando=self.INICIO + timedelta(minutes=2),
                status_dependente=False,
                idade_titular=60,
            ),
            self._mensagem(
                id_unidade=2,
                id_cliente=3,
                id_conversa=603,
                id_mensagem=3,
                quando=self.INICIO + timedelta(minutes=3),
                status_dependente=True,
                idade_titular=None,
                idade_dependente=60,
            ),
        ]
        funil = [
            {"id_unidade": 2, "id_cliente": indice, "id_conversa": 600 + indice}
            for indice in range(1, 4)
        ]

        snapshot = monitoramento.montar_snapshot(
            [unidade], mensagens, funil, [], self.INICIO, self.FIM
        )
        segmentacao = snapshot["unidades"][0]["metricas"]["segmentacao_perfis"]
        linhas = {item["chave"]: item for item in segmentacao["linhas"]}

        self.assertEqual(segmentacao["idade_minima_dependente"], 4)
        self.assertIn("4 a 17", linhas["dependente_infantil"]["rotulo"])
        self.assertEqual(linhas["dependente_infantil"]["leads_funil"], 1)
        self.assertEqual(linhas["dependente_idoso"]["leads_funil"], 1)
        self.assertFalse(linhas["titular_idoso"]["funil_nao_aplicavel"])
        self.assertEqual(linhas["titular_idoso"]["leads_funil"], 1)
        self.assertEqual(linhas["titular_idoso"]["taxa_funil"], 100.0)

    def test_profissao_prioriza_cliente_e_faz_fallback_para_conversa(self) -> None:
        snapshot = self._snapshot()
        saj = next(item for item in snapshot["unidades"] if item["id_unidade"] == 1)
        conversas = {item["id_cliente"]: item for item in saj["conversas"]}

        self.assertEqual(conversas[10]["profissao"], "Professora")
        self.assertEqual(conversas[20]["profissao"], "Pedreira")

    def test_html_nao_permite_encerrar_script_pelo_conteudo(self) -> None:
        snapshot = self._snapshot()
        unidade = snapshot["unidades"][0]
        ataque = "</script><script>alert('x')</script>"
        unidade["conversas"][0]["nome"] = ataque
        unidade["conversas"][0]["mensagens"][0]["texto"] = ataque

        html = monitoramento.renderizar_html(unidade, snapshot["periodo"])

        self.assertNotIn(ataque, html)
        self.assertIn(r"\u003c/script\u003e", html)

    def test_html_preserva_rolagem_independente_de_conversas_e_mensagens(
        self,
    ) -> None:
        snapshot = self._snapshot()

        html = monitoramento.renderizar_html(
            snapshot["unidades"][0], snapshot["periodo"]
        )

        def declaracoes(selector: str) -> str:
            blocos = re.findall(rf"{re.escape(selector)}\{{([^}}]*)\}}", html)
            self.assertTrue(blocos, f"Regra CSS ausente: {selector}")
            return ";".join(blocos).replace(" ", "").replace("\n", "")

        self.assertIn("grid-template-rows:minmax(0,1fr)", declaracoes(".app"))
        for selector in (".sidebar", ".main"):
            regra = declaracoes(selector)
            self.assertIn("min-height:0", regra)
            self.assertIn("overflow:hidden", regra)
        for selector in (".list", ".messages"):
            regra = declaracoes(selector)
            self.assertIn("min-height:0", regra)
            self.assertIn("overflow-y:auto", regra)
            self.assertIn("overscroll-behavior:contain", regra)

        self.assertIn('<div id="chatList" class="list"></div>', html)
        self.assertIn('<div id="messages" class="messages">', html)

    def test_gera_estrutura_por_unidade_sem_expor_arquivos_temporarios(self) -> None:
        snapshot = self._snapshot()

        def pdf_falso(unidade, periodo, destino: Path) -> None:
            del unidade, periodo
            destino.write_bytes(b"%PDF-1.4\nmock")

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento, "renderizar_pdf", side_effect=pdf_falso
            ) as renderizar:
                gerados = monitoramento.gerar_artefatos(snapshot, raiz)

            self.assertEqual(renderizar.call_count, 2)
            self.assertEqual(len(gerados), 2)
            self.assertEqual(
                {item["html"].parent.name for item in gerados}, {"dashbord"}
            )
            self.assertEqual(
                {item["html"].parent.parent.name for item in gerados}, {"semanal"}
            )
            self.assertEqual(
                {item["pdf"].parent.name for item in gerados}, {"relatorios"}
            )
            self.assertEqual(
                {item["pdf"].parent.parent.name for item in gerados}, {"semanal"}
            )
            for item in gerados:
                self.assertTrue(item["html"].is_file())
                self.assertTrue(item["pdf"].is_file())
                self.assertEqual(item["pdf"].read_bytes(), b"%PDF-1.4\nmock")
            self.assertEqual(list(raiz.rglob(".gerando-*")), [])

    def test_falha_do_pdf_nao_publica_metade_do_par(self) -> None:
        snapshot = self._snapshot()
        snapshot["unidades"] = snapshot["unidades"][:1]

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento,
                "renderizar_pdf",
                side_effect=RuntimeError("falha simulada"),
            ):
                with self.assertRaisesRegex(RuntimeError, "falha simulada"):
                    monitoramento.gerar_artefatos(snapshot, raiz)

            self.assertEqual(list(raiz.rglob("*.html")), [])
            self.assertEqual(list(raiz.rglob("*.pdf")), [])
            self.assertEqual(list(raiz.rglob(".gerando-*")), [])

    def test_falha_na_segunda_unidade_preserva_todo_o_lote_anterior(self) -> None:
        snapshot = self._snapshot()

        def pdf_antigo(unidade, periodo, destino: Path) -> None:
            del periodo
            destino.write_bytes(f"PDF-antigo-{unidade['id_unidade']}".encode())

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento, "renderizar_pdf", side_effect=pdf_antigo
            ):
                anteriores = monitoramento.gerar_artefatos(snapshot, raiz)

            conteudos_anteriores = {
                caminho: caminho.read_bytes()
                for item in anteriores
                for caminho in (item["html"], item["pdf"])
            }
            chamadas = 0

            def pdf_novo_com_falha(unidade, periodo, destino: Path) -> None:
                nonlocal chamadas
                del unidade, periodo
                chamadas += 1
                if chamadas == 2:
                    raise RuntimeError("falha na segunda unidade")
                destino.write_bytes(b"PDF-novo")

            with mock.patch.object(
                monitoramento,
                "renderizar_pdf",
                side_effect=pdf_novo_com_falha,
            ):
                with self.assertRaisesRegex(
                    RuntimeError, "falha na segunda unidade"
                ):
                    monitoramento.gerar_artefatos(snapshot, raiz)

            for caminho, conteudo in conteudos_anteriores.items():
                self.assertEqual(caminho.read_bytes(), conteudo)
            self.assertEqual(list(raiz.rglob(".gerando-*")), [])

    def test_periodo_total_publica_na_arvore_total_com_o_mesmo_renderizador(self) -> None:
        snapshot = self._snapshot()
        snapshot["periodo"]["tipo"] = "total"
        snapshot["unidades"] = snapshot["unidades"][:1]

        def pdf_falso(unidade, periodo, destino: Path) -> None:
            del unidade
            self.assertEqual(periodo["tipo"], "total")
            destino.write_bytes(b"%PDF-1.4\nmock-total")

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento, "renderizar_pdf", side_effect=pdf_falso
            ):
                gerados = monitoramento.gerar_artefatos(snapshot, raiz)

            self.assertEqual(len(gerados), 1)
            self.assertEqual(gerados[0]["html"].parent.parent.name, "total")
            self.assertEqual(gerados[0]["pdf"].parent.parent.name, "total")
            self.assertTrue(gerados[0]["html"].is_file())
            self.assertEqual(
                gerados[0]["pdf"].read_bytes(), b"%PDF-1.4\nmock-total"
            )

    def test_semanal_e_total_coexistem_sem_sobrescrever_um_ao_outro(self) -> None:
        semanal = self._snapshot()
        total_snapshot = self._snapshot()
        total_snapshot["periodo"]["tipo"] = "total"
        semanal["unidades"] = semanal["unidades"][:1]
        total_snapshot["unidades"] = total_snapshot["unidades"][:1]

        def pdf_falso(unidade, periodo, destino: Path) -> None:
            del unidade
            destino.write_bytes(f"PDF-{periodo['tipo']}".encode())

        with tempfile.TemporaryDirectory() as temporario:
            raiz = Path(temporario) / "monitoramento"
            with mock.patch.object(
                monitoramento, "renderizar_pdf", side_effect=pdf_falso
            ):
                gerado_semanal = monitoramento.gerar_artefatos(semanal, raiz)[0]
                gerado_total = monitoramento.gerar_artefatos(total_snapshot, raiz)[0]

            self.assertNotEqual(gerado_semanal["html"], gerado_total["html"])
            self.assertNotEqual(gerado_semanal["pdf"], gerado_total["pdf"])
            self.assertTrue(gerado_semanal["html"].is_file())
            self.assertTrue(gerado_semanal["pdf"].is_file())
            self.assertTrue(gerado_total["html"].is_file())
            self.assertTrue(gerado_total["pdf"].is_file())

    def test_total_usa_inicio_independente_por_unidade_e_fim_congelado(self) -> None:
        primeiro_saj = self.FIM - timedelta(days=90)
        primeiro_rio = self.FIM - timedelta(days=30)
        unidades = [
            {
                "id_unidade": 1,
                "nome_unidade": "Supera SAJ",
                "primeiro_registro": primeiro_saj,
            },
            {
                "id_unidade": 2,
                "nome_unidade": "Supera Rio Vermelho",
                "primeiro_registro": primeiro_rio,
            },
        ]
        coletas: list[dict[str, object]] = []
        publicacoes: list[dict[str, object]] = []

        def coletar_falso(**kwargs):
            coletas.append(kwargs)
            id_unidade = kwargs["ids_unidade"][0]
            unidade = next(
                item for item in unidades if item["id_unidade"] == id_unidade
            )
            return {
                "periodo": {
                    "tipo": "semanal",
                    "inicio": kwargs["inicio"].isoformat(),
                    "fim": kwargs["fim"].isoformat(),
                    "dias": (
                        kwargs["fim"] - kwargs["inicio"]
                    ).total_seconds()
                    / 86_400,
                    "rotulo": "intervalo de teste",
                },
                "unidades": [
                    {
                        "id_unidade": id_unidade,
                        "nome_unidade": unidade["nome_unidade"],
                    }
                ],
            }

        def gerar_falso(snapshot, raiz_saida, nomes_pasta=None):
            publicacoes.append(
                {
                    "snapshot": snapshot,
                    "raiz_saida": raiz_saida,
                    "nomes_pasta": nomes_pasta,
                }
            )
            return [
                {
                    "html": raiz_saida / "mock.html",
                    "pdf": raiz_saida / "mock.pdf",
                }
            ]

        with mock.patch.object(
            monitoramento, "coletar_snapshot", side_effect=coletar_falso
        ), mock.patch.object(
            monitoramento, "gerar_artefatos", side_effect=gerar_falso
        ):
            gerados = total.gerar_totais(
                conn=object(),
                unidades=unidades,
                fim=self.FIM,
                raiz_saida=Path("monitoramento"),
            )

        self.assertEqual(len(gerados), 2)
        self.assertEqual([item["inicio"] for item in coletas], [primeiro_saj, primeiro_rio])
        self.assertEqual([item["fim"] for item in coletas], [self.FIM, self.FIM])
        self.assertEqual(
            [item["snapshot"]["periodo"]["tipo"] for item in publicacoes],
            ["total", "total"],
        )

    def test_total_sem_primeiro_registro_ainda_gera_snapshot_vazio(self) -> None:
        unidades = [
            {
                "id_unidade": 9,
                "nome_unidade": "Supera Unidade Nova",
                "primeiro_registro": None,
            }
        ]
        publicacoes: list[dict[str, object]] = []

        def coletar_falso(**kwargs):
            self.assertEqual(kwargs["inicio"], self.FIM)
            self.assertEqual(kwargs["fim"], self.FIM)
            return {
                "periodo": {
                    "tipo": "semanal",
                    "inicio": self.FIM.isoformat(),
                    "fim": self.FIM.isoformat(),
                    "dias": 0,
                    "rotulo": "sem registros",
                },
                "unidades": [
                    {"id_unidade": 9, "nome_unidade": "Supera Unidade Nova"}
                ],
            }

        def gerar_falso(snapshot, raiz_saida, nomes_pasta=None):
            del raiz_saida, nomes_pasta
            publicacoes.append(snapshot)
            return [{"html": Path("mock.html"), "pdf": Path("mock.pdf")}]

        with mock.patch.object(
            monitoramento, "coletar_snapshot", side_effect=coletar_falso
        ), mock.patch.object(
            monitoramento, "gerar_artefatos", side_effect=gerar_falso
        ):
            total.gerar_totais(
                conn=object(),
                unidades=unidades,
                fim=self.FIM,
                raiz_saida=Path("monitoramento"),
            )

        self.assertEqual(len(publicacoes), 1)
        self.assertTrue(publicacoes[0]["periodo"]["sem_registros"])
        self.assertEqual(publicacoes[0]["periodo"]["tipo"], "total")


if __name__ == "__main__":
    unittest.main()
```

### Passo 25 — `tests/unit/test_suporte_por_idade.py`

**Ação:** Criar. Cobrir domínio, Admin, matriz de idades, persistência, recuperação atual e SQL de contagem com banco SQLite em memória.

Conteúdo completo do arquivo:

```python
"""Fronteiras da política, recuperação atual e encaminhamentos registrados."""

from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
import sqlite3
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch

from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from core.validacoes.suporte_por_idade import validar_idade_minima_suporte
from core.repositories.fluxo.contextos.etapa6 import buscar_contexto_etapa6
from core.repositories.monitoramento import painel as repositorio
from core.integrations.whatsapp.messages.etapa6_messages import montar_mensagem_suporte_idoso_etapa6
from core.integrations.whatsapp.pywa_functions.pywa_senders import etapa6 as sender
from monitoramento import services
from monitoramento.apresentacao import montar_relatorio, classificar_faixa
from monitoramento.periodos import PERIODOS, resolver_periodo
from webhook.admin import UnidadeAdmin
from webhook.models import Unidade
from tests.helpers import FakeCursor
from tests.unit.test_suporte_idoso_email_obrigatorio import contexto_etapa6, contexto_envio
from workers.worker_flow.response_flow.etapas import resolver_etapa6
from workers.worker_flow.transacoes import efeitos_transicao, encerramento_atendimento


LIMITES = (None, 50, 60, 70, 80, 90)


class SuportePorIdadeTests(unittest.TestCase):
    def test_dominio_contexto_e_formulario_modelo(self):
        campo = Unidade._meta.get_field('idade_minima_suporte')
        for limite in LIMITES:
            with self.subTest(limite=limite):
                self.assertEqual(validar_idade_minima_suporte(limite), limite)
                self.assertEqual(campo.clean(limite, Unidade()), limite)
                contexto = buscar_contexto_etapa6(10, 1, FakeCursor(
                    fetchone_result=('5571999999999', False, limite, 'Maria', None)
                ))
                self.assertEqual(contexto['idade_minima_suporte'], limite)
        self.assertEqual(list(campo.formfield().choices), [(None, 'Desativado')] + [
            (idade, f'{idade}+') for idade in LIMITES[1:]
        ])
        for invalido in (True, False, 0, -1, 49, 55, 100, '60', 60.0):
            with self.subTest(invalido=invalido), self.assertRaises(ValueError):
                validar_idade_minima_suporte(invalido)
        with self.assertRaises(ValueError):
            buscar_contexto_etapa6(10, 1, FakeCursor(
                fetchone_result=(None, False, True, None, None)
            ))

    def test_admin_exige_contato_ao_ativar_e_ao_remover_numero(self):
        admin = UnidadeAdmin(Unidade, AdminSite())
        request = RequestFactory().get('/admin/')
        request.user = SimpleNamespace(has_perm=lambda *_: True)
        instance = Unidade(id_unidade=1)
        with patch.object(admin, '_validar_cache_unidades_form'), patch.object(
            admin, '_preparar_meta_antes_de_salvar'
        ) as meta:
            form_class = admin.get_form(request, instance, change=True,
                                        fields=['idade_minima_suporte', 'numero_comercial'])
            for limite in LIMITES:
                for telefone in ('', '123', '(71) 99999-9999'):
                    with self.subTest(limite=limite, telefone=telefone):
                        form = form_class(data={
                            'idade_minima_suporte': '' if limite is None else str(limite),
                            'numero_comercial': telefone,
                        }, instance=instance)
                        esperado = limite is None or telefone == '(71) 99999-9999'
                        self.assertEqual(form.is_valid(), esperado, form.errors)
                        if not esperado:
                            self.assertIn('numero_comercial', form.errors)
            for invalido in ('55', '100', 'True'):
                form = form_class(data={'idade_minima_suporte': invalido,
                                        'numero_comercial': '(71) 99999-9999'}, instance=instance)
                self.assertFalse(form.is_valid())
            meta.assert_not_called()

    def test_matriz_titulares_dependentes_e_100_mais(self):
        caminhos = {
            'suporte': 'enviar_etapa6_suporte_idoso',
            'cem': 'enviar_etapa6_idade_acima_99',
            'menor': 'enviar_etapa6_cliente_menor_18',
            'crianca': 'enviar_etapa6_dependente_menor_5',
            'titular': 'enviar_etapa7_cliente',
            'dependente': 'enviar_etapa7_dependente',
        }
        for limite in LIMITES:
            idades = {4, 5, 17, 18, 49, 50, 59, 60, 69, 70, 79, 80, 89, 90, 99, 100}
            for idade in sorted(idades):
                for dependente in (False, True):
                    for bpa in (False, True):
                        contexto = contexto_etapa6(idade, suporte=limite, dependente=dependente)
                        contexto['bpa_ativo_unidade'] = bpa
                        esperado = (
                            'cem' if idade >= 100 else
                            'suporte' if not dependente and limite is not None and idade >= limite else
                            'menor' if not dependente and idade < 18 else
                            'crianca' if dependente and idade < (4 if bpa else 5) else
                            'dependente' if dependente else 'titular'
                        )
                        with self.subTest(limite=limite, idade=idade, dependente=dependente, bpa=bpa), ExitStack() as stack:
                            mocks = {nome: stack.enter_context(patch.object(
                                resolver_etapa6, funcao,
                                return_value=contexto_envio(7 if nome in ('titular', 'dependente') else 6),
                            )) for nome, funcao in caminhos.items()}
                            resultado = resolver_etapa6.resolve_etapa6(contexto)
                            self.assertEqual([n for n,m in mocks.items() if m.called], [esperado])
                            if esperado == 'suporte':
                                self.assertEqual(mocks['suporte'].call_args.args[-1], limite)
                                self.assertEqual(resultado['id_etapa_resultante'], 6)
                                self.assertNotIn('evento_transicao', resultado)
                                self.assertEqual(resultado['idade_aluno'], idade)

    def test_chave_ausente_erro_nao_desativa_silenciosamente(self):
        contexto = contexto_etapa6(65)
        del contexto['idade_minima_suporte']
        with self.assertRaises(KeyError), patch.object(sender, 'conta_wa') as conta:
            resolver_etapa6.resolve_etapa6(contexto)
        conta.assert_not_called()

    def test_mensagem_sender_preservam_contrato_e_60_legado(self):
        legado = (
            'Entendi. Para oferecer um atendimento mais adequado, esta unidade '
            'realiza o suporte a clientes com 60 anos ou mais diretamente com a '
            'nossa equipe comercial.\n\n'
            'Vou te passar o contato para continuar o atendimento. Basta clicar '
            'no botão abaixo.'
        )
        self.assertEqual(montar_mensagem_suporte_idoso_etapa6(60), legado)
        for limite in LIMITES[1:]:
            with self.subTest(limite=limite), patch.object(sender, 'conta_wa') as conta:
                conta.return_value.send_message.return_value = SimpleNamespace(id='wamid.teste')
                envio = sender.enviar_etapa6_suporte_idoso('5571888888888', 'phone', '5571999999999', limite)
                enviado = conta.return_value.send_message.call_args.kwargs
                self.assertEqual(enviado['text'], envio['mensagem_bot'])
                self.assertIn(f'com {limite} anos', enviado['text'])
                self.assertEqual(enviado['buttons'].url, 'https://wa.me/5571999999999')
                self.assertEqual(enviado['buttons'].title, 'Falar com Comercial')
                self.assertEqual(envio['tipo_mensagem'], 'interactive_cta_url')
        with self.assertRaises(ValueError):
            montar_mensagem_suporte_idoso_etapa6(None)

    def test_persistencia_50_a_99_e_encerramento_sem_bloqueio(self):
        for idade in (50, 59, 60, 99):
            contexto = contexto_etapa6(idade, suporte=50)
            envio = contexto_envio(6)
            envio.update(encerrar_atendimento=True, motivo_encerramento='encaminhado_suporte_idoso', idade_aluno=idade)
            cursor = object()
            with patch.object(efeitos_transicao, 'atualizar_idade_cliente') as salvar:
                efeitos_transicao.atualizar_banco_conforme_transicao_de_etapa(contexto, envio, cursor)
            salvar.assert_called_once_with(5, idade, cursor)
            intencao = encerramento_atendimento.resolver_intencao_encerramento(contexto, envio, cursor)
            self.assertEqual(intencao['bloqueio_dias'], 0)
            self.assertFalse(intencao['excluir_dependente'])

    def test_recuperacao_reconhece_variantes_mas_usa_limite_atual(self):
        for antigo in LIMITES[1:]:
            for atual, idade, encerra in ((70, 65, False), (70, 75, True), (None, 95, False), (50, 55, True)):
                contexto = contexto_etapa6(idade, suporte=atual)
                contexto['resposta_bot_para_mensagem_atual'] = {
                    'tipo_mensagem': 'interactive_cta_url',
                    'conteudo_texto': 'Olá novamente, Maria!\n\n' + montar_mensagem_suporte_idoso_etapa6(antigo),
                }
                with self.subTest(antigo=antigo, atual=atual, idade=idade):
                    intencao = encerramento_atendimento.resolver_intencao_encerramento(
                        contexto, {'resposta_ja_existia': True, 'id_etapa_resultante': 6}, object()
                    )
                    self.assertEqual(intencao is not None, encerra)
        for texto, tipo in (('Procure o comercial', 'interactive_cta_url'),
                            (montar_mensagem_suporte_idoso_etapa6(50), 'text')):
            contexto['idade_minima_suporte'] = 50
            contexto['resposta_bot_para_mensagem_atual'] = {'tipo_mensagem': tipo, 'conteudo_texto': texto}
            self.assertIsNone(encerramento_atendimento.resolver_intencao_encerramento(
                contexto, {'resposta_ja_existia': True}, object()
            ))


class EncaminhamentosRelatorioTests(unittest.TestCase):
    def test_sql_deduplica_por_unidade_data_e_motivo_sem_depender_da_ultima_conversa(self):
        conn = sqlite3.connect(':memory:')
        self.addCleanup(conn.close)
        conn.execute("ATTACH DATABASE ':memory:' AS chatbot")
        conn.execute('''CREATE TABLE chatbot.conversa (
            id_conversa INTEGER, id_unidade INTEGER, id_cliente INTEGER,
            status_ativa BOOLEAN, motivo_encerramento TEXT, finalizou_em TEXT
        )''')
        motivo = 'encaminhado_suporte_idoso'
        conn.executemany('INSERT INTO chatbot.conversa VALUES (?, ?, ?, ?, ?, ?)', [
            (1, 10, 1, False, motivo, '2026-09-01'),
            (2, 10, 1, False, motivo, '2026-09-02'),
            (3, 10, 1, True, None, None),
            (4, 10, 2, False, motivo, '2026-08-31'),
            (5, 10, 3, False, motivo, '2026-10-01'),
            (6, 20, 4, False, motivo, '2026-09-05'),
            (7, 10, 5, False, 'idade_invalida', '2026-09-05'),
            (8, 10, 6, True, motivo, '2026-09-05'),
            (9, 10, 7, False, motivo, None),
        ])

        class CursorSQLite:
            def execute(self, sql, params): self.cursor = conn.execute(sql.replace('%s', '?'), params)
            def fetchone(self): return self.cursor.fetchone()

        cursor = CursorSQLite()
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(10, '2026-09-01', '2026-10-01', cursor), 1)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(10, None, '2026-10-01', cursor), 2)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(20, '2026-09-01', '2026-10-01', cursor), 1)
        self.assertEqual(repositorio.contar_encaminhados_comercial_por_idade(30, None, '2026-10-01', cursor), 0)

    def test_servico_propaga_unidade_periodos_politica_e_falha(self):
        fim = datetime(2026, 9, 11, tzinfo=timezone.utc)
        for chave in PERIODOS:
            periodo = resolver_periodo(chave, agora=fim)
            with self.subTest(periodo=chave), ExitStack() as stack:
                stack.enter_context(patch.object(services, 'connection', MagicMock()))
                stack.enter_context(patch.object(repositorio, 'buscar_unidade', return_value={
                    'nome_unidade': 'Teste', 'bpa_ativo': False, 'idade_minima_suporte': None,
                    'inicio_historico': fim - timedelta(days=300),
                }))
                stack.enter_context(patch.object(repositorio, 'buscar_metricas', return_value={}))
                for nome in ('buscar_perfis', 'buscar_satisfacao', 'buscar_etapas', 'buscar_atividade'):
                    stack.enter_context(patch.object(repositorio, nome, return_value=[]))
                contar = stack.enter_context(patch.object(repositorio, 'contar_encaminhados_comercial_por_idade', return_value=3))
                payload = services.carregar_relatorio(SimpleNamespace(id_unidade=10), periodo)
                self.assertEqual(contar.call_args.args[:3], (10, periodo.inicio, periodo.fim))
                self.assertEqual(payload['encaminhados_comercial_por_idade'], 3)
                self.assertIsNone(payload['unidade']['idade_minima_suporte'])
                contar.side_effect = RuntimeError('banco indisponível')
                with self.assertRaises(RuntimeError):
                    services.carregar_relatorio(SimpleNamespace(id_unidade=10), periodo)

    def test_card_nao_inventa_zero_e_tags_permanecem_fixas(self):
        for invalido in (None, True, -1, '1'):
            with self.assertRaises(ValueError):
                montar_relatorio({}, None, {}, {}, [], [], encaminhados_comercial_por_idade=invalido)
        self.assertEqual(classificar_faixa(59), 'adulto')
        self.assertEqual(classificar_faixa(60), 'idoso')
        perfis = services._agrupar_perfis([
            {'id_cliente': 1, 'status_dependente': False, 'idade_titular': 65, 'foi_funil': True},
        ], bpa_ativo=False)
        idoso = next(p for p in perfis['linhas'] if p['chave'] == 'titular_idoso')
        self.assertEqual(idoso['funil'], 1)
        self.assertEqual(idoso['taxa_funil'], 100.0)


if __name__ == '__main__':
    unittest.main()
```

### Passo 26 — `tests/integration/test_suporte_por_idade_postgres.py`

**Ação:** Criar. Homologar SQL integral, domínio, instalação limpa, schema parcial, rollback e reversão em PostgreSQL local descartável explícito.

Conteúdo completo do arquivo:

```python
"""Migração real somente em PostgreSQL local descartável explicitamente indicado."""

from contextlib import contextmanager
import os
from pathlib import Path
import re
import unittest
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.database.deploy_database import bank_script


DSN = os.environ.get('SUPORTE_IDADE_TEST_DSN')
MIGRACAO = Path(__file__).resolve().parents[2] / 'deploy/migrations/20260911_idade_minima_suporte.sql'
REVERSAO = Path(__file__).resolve().parents[2] / 'deploy/rollback/20260911_idade_minima_suporte.sql'


@unittest.skipUnless(DSN, 'Defina SUPORTE_IDADE_TEST_DSN para banco local vazio test_chatbot_suporte_idade')
class SuporteIdadePostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        params = conninfo_to_dict(DSN)
        locais = {'127.0.0.1', '::1', 'localhost'}
        if (params.get('host') not in locais
                or params.get('dbname') != 'test_chatbot_suporte_idade'
                or (params.get('hostaddr') and params['hostaddr'] not in locais)
                or params.get('service')):
            raise RuntimeError('Exige host loopback explícito e dbname=test_chatbot_suporte_idade')
        cls.conn = psycopg.connect(DSN, connect_timeout=5, autocommit=True)
        if cls.conn.info.host not in locais or cls.conn.info.dbname != 'test_chatbot_suporte_idade':
            cls.conn.close()
            raise RuntimeError('Conexão efetiva não corresponde ao banco descartável')
        if cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0] is not None:
            cls.conn.close()
            raise RuntimeError('Schema chatbot já existe: use um banco de teste vazio')

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.conn.execute('CREATE SCHEMA chatbot')
        self.addCleanup(self.limpar_schema)
        self.conn.execute('''CREATE TABLE chatbot.unidade (
            id_unidade SERIAL PRIMARY KEY, nome_unidade TEXT NOT NULL,
            suporte_idoso BOOLEAN NOT NULL DEFAULT FALSE,
            email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE,
            bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE,
            numero_comercial TEXT
        );
        INSERT INTO chatbot.unidade(nome_unidade, suporte_idoso, email_obrigatorio, numero_comercial)
        VALUES ('Ativa', TRUE, FALSE, '5571999999999'), ('Desativada', FALSE, TRUE, NULL);
        CREATE TABLE chatbot.conversa (id_conversa INTEGER, followup_stage INTEGER, status_ativa BOOLEAN);
        INSERT INTO chatbot.conversa VALUES (1, 1, TRUE), (2, 0, FALSE);
        ''')

    def limpar_schema(self):
        self.conn.execute('ROLLBACK')
        # Este schema foi criado pelo próprio teste após recusar um preexistente.
        self.conn.execute('DROP SCHEMA chatbot CASCADE')

    def migrar(self, sql=None):
        self.conn.execute(sql or MIGRACAO.read_text(encoding='utf-8'))

    def assert_dominio(self):
        for idade in (None, 50, 60, 70, 80, 90):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (idade,))
        for idade in (0, -1, 49, 55, 100):
            with self.assertRaises(psycopg.errors.CheckViolation):
                self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (idade,))

    def test_conversao_preserva_unidades_conversas_e_dominio(self):
        self.migrar()
        self.assertEqual(self.conn.execute('''SELECT idade_minima_suporte, email_obrigatorio,
            bpa_ativo, numero_comercial FROM chatbot.unidade ORDER BY id_unidade''').fetchall(),
            [(60, False, False, '5571999999999'), (None, True, False, None)])
        self.assertEqual(self.conn.execute('SELECT * FROM chatbot.conversa ORDER BY id_conversa').fetchall(),
                         [(1, 1, True), (2, 0, False)])
        self.assert_dominio()
        self.conn.execute("INSERT INTO chatbot.unidade(nome_unidade) VALUES ('Nova')")
        self.assertIsNone(self.conn.execute("SELECT idade_minima_suporte FROM chatbot.unidade WHERE nome_unidade='Nova'").fetchone()[0])

    def test_reaplicacao_recusada_sem_perder_configuracao_nova(self):
        self.migrar()
        self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=70 WHERE id_unidade=1')
        with self.assertRaisesRegex(psycopg.Error, 'já aplicada ou schema parcial'):
            self.migrar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade WHERE id_unidade=1').fetchone()[0], 70)

    def test_schema_parcial_recusado(self):
        self.conn.execute('ALTER TABLE chatbot.unidade ADD COLUMN idade_minima_suporte INTEGER')
        with self.assertRaisesRegex(psycopg.Error, 'schema parcial'):
            self.migrar()
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT suporte_idoso FROM chatbot.unidade ORDER BY id_unidade').fetchall(), [(True,), (False,)])

    def test_falha_pos_conversao_reverte_toda_a_transacao(self):
        sql = MIGRACAO.read_text(encoding='utf-8').replace(
            'DO $poscondicoes$\nBEGIN',
            "DO $poscondicoes$\nBEGIN\n    RAISE EXCEPTION 'Falha injetada de teste';",
        )
        with self.assertRaisesRegex(psycopg.Error, 'Falha injetada'):
            self.migrar(sql)
        self.conn.execute('ROLLBACK')
        self.assertEqual(self.conn.execute('SELECT suporte_idoso FROM chatbot.unidade ORDER BY id_unidade').fetchall(), [(True,), (False,)])
        self.assertEqual(self.conn.execute("""SELECT COUNT(*) FROM information_schema.columns
            WHERE table_schema='chatbot' AND table_name='unidade' AND column_name='idade_minima_suporte'""").fetchone()[0], 0)

    def test_instalacao_limpa_usa_o_mesmo_dominio(self):
        comandos = []

        class CapturaDDL:
            def execute(self, sql, *args): comandos.append(sql)

        @contextmanager
        def capturar(*args): yield CapturaDDL()

        with patch.object(bank_script, 'transacao_deploy', capturar):
            bank_script.criar_tabelas()
        ddl_unidade = re.search(
            r'CREATE TABLE IF NOT EXISTS chatbot\.unidade\s*\(.*?\n\s*\);',
            '\n'.join(comandos), re.S,
        ).group(0)
        self.conn.execute('DROP TABLE chatbot.unidade; CREATE TABLE chatbot.auth_user (id SERIAL PRIMARY KEY)')
        self.conn.execute(ddl_unidade)
        self.conn.execute('''INSERT INTO chatbot.unidade
            (id_unidade, nome_unidade, nome_agente, genero, cnpj, email_responsavel, telefone,
             waba_id, phone_number_id, link_agendamento)
            VALUES (1, 'Nova', 'Suh', 'feminino', 'teste', 'teste@example.com', '5571999999999',
                    'waba', 'phone', 'https://example.com')''')
        self.assertIsNone(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade').fetchone()[0])
        self.assert_dominio()

    def test_reversao_preserva_politica_null_60(self):
        self.migrar()
        self.conn.execute(REVERSAO.read_text(encoding='utf-8'))
        self.assertEqual(self.conn.execute(
            'SELECT suporte_idoso, email_obrigatorio FROM chatbot.unidade ORDER BY id_unidade'
        ).fetchall(), [(True, False), (False, True)])

    def test_reversao_recusa_faixas_novas(self):
        self.migrar()
        for limite in (50, 70, 80, 90):
            self.conn.execute('UPDATE chatbot.unidade SET idade_minima_suporte=%s WHERE id_unidade=1', (limite,))
            with self.assertRaisesRegex(psycopg.Error, 'Há faixas novas configuradas'):
                self.conn.execute(REVERSAO.read_text(encoding='utf-8'))
            self.conn.execute('ROLLBACK')
            self.assertEqual(self.conn.execute('SELECT idade_minima_suporte FROM chatbot.unidade WHERE id_unidade=1').fetchone()[0], limite)


if __name__ == '__main__':
    unittest.main()
```

## Parte 5 — documentação da implementação

### Passo 27 — `REGRAS_DE_NEGOCIO.md`

**Ação:** Alterar. Documentar a política final, sua independência do e-mail, tags e regra do indicador.

Conteúdo completo do arquivo:

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
- Cada unidade possui `idade_minima_suporte` (NULL/50/60/70/80/90, padrão NULL)
  e `email_obrigatorio` (padrão TRUE). A migração da política anterior conserva
  TRUE como 60 e FALSE como NULL; novas unidades começam sem suporte ativado.
- Na etapa 6, mídia, reforço escolar e financeiro precedem a validação de idade.
  Pessoas de 100+ conservam o encaminhamento próprio para titular ou dependente,
  independentemente do suporte. Depois, titulares com idade válida maior ou igual
  ao limite recebem o contato comercial e encerram na etapa 6 com
  `motivo_encerramento = 'encaminhado_suporte_idoso'`, sem bloqueio ou Funil.
  A idade é persistida. Dependentes e titulares menores mantêm as regras atuais.
- O proprietário configura o limite no Admin. Habilitar ou manter a política
  requer `numero_comercial` brasileiro válido, inclusive ao editar o número.
- Retry reconhece as cinco variantes oficiais e o prefixo de saudação. O texto
  identifica uma resposta existente, sem recuperar o limite antigo. Reavaliações
  usam a configuração atual; não autorizam reenvio, reescrita do histórico ou
  avanço sem resposta correspondente. A reação ao follow-up apenas repete a etapa.
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

A resposta do bot a uma mensagem enfileirada é vinculada à entrada original por:

- `id_conversa`;
- `id_mensagem_fila`;
- `id_hash_cliente_origem`.

O lembrete proativo não responde a uma entrada enfileirada: deixa os dois campos
de origem nulos e usa recibo próprio por conversa e âncora do ciclo. Ele não
serve como prova de resposta para liberar um turno A/B/C.

Se `resposta_bot_para_mensagem_atual` já existir:

- a Meta não deverá ser chamada novamente;
- o histórico do bot não deverá ser duplicado;
- o contexto da conversa deverá ser reparado a partir dos dados persistidos;
- no retry normal, `last_message_from` deverá terminar como `bot`;
- a fila poderá seguir para `sent`.

O replay de uma retomada de follow-up já concluída reutiliza a resposta persistida
sem alterar a interação atual ou zerar um ciclo posterior. Essa recuperação fica
em `workers/worker_flow/transacoes/retorno_followup.py`.

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

Recuperar uma retomada de follow-up já concluída não sobrescreve o estado de
uma interação posterior. A confirmação do lembrete proativo também registra
o bot como último lado, junto do histórico e do recibo de envio.

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
deverá fazer a resposta começar com `Olá novamente, {nome}!` no caminho normal
com `followup_stage = 0`. Stage positivo ou retomada já registrada segue o
[contrato de follow-up](#follow-up-de-inatividade-e-reação-do-cliente), com a
saudação própria e repetição da etapa.

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

O worker de atendimento possui checkpoints duráveis separados:

1. claim da fila como `processing`;
2. espera por mensagem anterior, quando necessária;
3. validação do cliente e da conversa no banco;
4. aquisição do lock da conversa;
5. vínculo, releitura e histórico do cliente, incluindo o marcador de retomada quando aplicável;
6. renovação do lock antes do envio;
7. histórico e contexto do bot; na retomada, conclusão do marcador e reset do stage;
8. fila marcada como `sent`, depois de conferir novamente a posse do lock;
9. unlock da conversa.

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
- `idade_minima_suporte` e `email_obrigatorio` são editáveis no Admin; a ativação do
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
- As opções `idade_minima_suporte`, `email_obrigatorio` e `bpa_ativo` são lidas
  da unidade. O limite é apresentado como política; não modifica tags 18–59/60+
  ou de dependentes nem esconde envios ao Funil registrados em qualquer faixa.
- Relatórios possui o card Encaminhados ao comercial, abaixo dos quatro KPIs.
  Conta clientes distintos da unidade com conversa encerrada por
  `encaminhado_suporte_idoso`, usando `finalizou_em >= início` e `< fim` do período.
  Inclui os registros históricos independentemente da configuração atual e da
  conversa mais recente; não inclui outros motivos nem o tratamento de 100+.
  Não comprova clique, atendimento humano, matrícula, venda ou envio ao Funil.
  Falha de consulta não é zero. O card não é duplicado na seção Conversas.
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
  Somente nesses dois CSVs essenciais, o telefone brasileiro é exibido sem o
  prefixo internacional `+55`, preservando o DDD e o número.

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
- o worker de follow-up isola erros por candidata e usa espera exponencial de
  5 até 300 segundos quando a consulta do lote falha;
- `flow_worker.py` mantém o loop de consumo e os tratamentos por tipo de exceção;
- se `worker_flow()` escapar com uma exceção, `iniciar_flow_worker.py` registra a falha,
  aguarda 5 segundos e inicia outro loop;
- o webhook responde de maneira controlada a entradas inválidas e falhas
  conhecidas;
- chamadas externas à Meta falham de forma controlada, sem confirmar no banco
  uma operação recusada pela Meta;
- caches degradam para fallback ou negam uma operação administrativa que
  produziria inconsistência.

Na produção atual, webhook, worker de atendimento, worker do Funil e worker de
follow-up são quatro serviços systemd independentes. Os três primeiros usam
`Restart=always`; follow-up usa `Restart=on-failure`. Todos têm `RestartSec=5s`.
As camadas de recuperação são complementares:

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
- `workers/worker_followup/iniciar_worker_followup.py`
- `workers/worker_followup/followup_worker.py`
- `deploy/systemd/chatbot-worker-followup.service`

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
| Follow-up antes do agendamento | Implementada | Um lembrete por ciclo nas etapas 1–17, após sete horas sem resposta e dentro da janela do cliente; retomada repete a etapa sem avançar. |
| Supervisão dos quatro processos | Implementada | Webhook, flow e Funil usam `Restart=always`; follow-up usa `Restart=on-failure`. Nginx encaminha o endpoint público ao webhook. |

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

Implementado na V1.2.0. As instruções de operação vivem nos
[workers](workers/README.md#worker-de-follow-up) e no
[deploy](deploy/README.md#ativação-do-follow-up); não dependem dos planos de implementação.

O worker proativo envia somente `Você viu a minha mensagem?` depois de sete horas
sem reação à última resposta comum confirmada do bot. NULL equivale a stage zero.
O envio exige conversa ativa em etapa 1–17, unidade válida e adimplente, ausência
de bloqueios, de entrada posterior no histórico e de fila pending/processing do
mesmo par cliente/unidade, mesmo se ainda não vinculada à conversa. Uma fila
respondida mas ainda aberta também adia o proativo até sua finalização.

O canal exige janela aberta desde a última mensagem do cliente; este envio em texto
livre não usa template. A implementação reserva um minuto antes de completar 24h
para evitar despacho na borda. Isso não altera o limiar de sete horas do bot.

São dois relógios distintos: a última mensagem de toda a conversa precisa ser
do bot há pelo menos sete horas, e a mensagem mais recente do cliente, anterior
a ela, precisa estar dentro de 23h59. Bot há oito horas com cliente há 25 horas
é inelegível; bot há oito horas com cliente há nove horas pode ser elegível.

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

### Passo 28 — `PADROES_DE_ARQUITETURA.md`

**Ação:** Alterar. Registrar o domínio puro e o novo nome da configuração, sem mudar as fronteiras.

Conteúdo completo do arquivo:

````markdown
# Padrões de arquitetura do Chatbot

## Finalidade

Este documento define onde cada responsabilidade deve ser implementada e quais
dependências são permitidas no projeto.

Antes de alterar código, leia também
[`REGRAS_DE_NEGOCIO.md`](REGRAS_DE_NEGOCIO.md). Os documentos possuem papéis
diferentes:

- `REGRAS_DE_NEGOCIO.md` define o comportamento esperado do sistema;
- `PADROES_DE_ARQUITETURA.md` define a organização e as fronteiras do código.

Uma reorganização nunca pode alterar silenciosamente uma regra de negócio. Caso
uma necessidade não se encaixe neste documento, a exceção deve ser discutida e
documentada antes da implementação.

## Princípios gerais

1. Cada módulo deve possuir uma responsabilidade principal clara.
2. Fluxo de negócio, persistência e integração externa não devem ser misturados.
3. Funções de baixo nível não devem controlar transações de alto nível.
4. O código deve depender de camadas mais internas, nunca do ponto de entrada.
5. Comportamentos críticos devem possuir testes em `tests/`.
6. Refatorações estruturais devem preservar entradas, saídas, logs relevantes e
   efeitos persistidos.
7. Não criar abstrações apenas para movimentar código; cada pasta deve representar
   uma fronteira real.

## Modelo de execução da V1 e evolução para a V2

Na V1, a implantação mantém uma instância do `worker_flow`, uma do `worker_funil`
e, após a migração e ativação específica, uma do `worker_followup`, além do webhook.
Cada serviço possui seu próprio ciclo de vida.

"Uma única instância ativa na V1" não deve ser confundida com a regra "um worker
por conversa". A primeira é uma decisão operacional desta versão; a segunda é
uma proteção que continuará válida mesmo quando existirem vários workers no
sistema: dois workers nunca poderão processar simultaneamente a mesma conversa.

Processamento paralelo permitido:

```text
Worker 1 -> conversa do cliente A
Worker 2 -> conversa do cliente B
```

Processamento que deverá continuar bloqueado:

```text
Worker 1 -> conversa do cliente A
Worker 2 -> conversa do cliente A ao mesmo tempo
```

Assim, vários workers poderão atender clientes diferentes em paralelo, mas cada
conversa ficará sob responsabilidade de apenas um worker por vez.

Embora a V1 execute apenas uma instância de cada worker, seus ciclos preservam as
proteções necessárias para concorrência e recuperação:

- dequeue atômico com `FOR UPDATE SKIP LOCKED`;
- exclusão mútua por conversa com `lock_version`;
- ordenação de mensagens anteriores ainda abertas;
- timeout e retomada de mensagens abandonadas em `processing`;
- idempotência pelo histórico vinculado à mensagem da fila;
- checkpoints, commits, rollbacks e fechamento da conexão por ciclo;
- `sent` somente depois da persistência da resposta do bot.

O objetivo arquitetural da V2 será permitir múltiplas instâncias de worker para
atender maior volume sem descartar essas garantias. Cada instância deverá
reutilizar os mesmos contratos de ordenação, lock, retry, idempotência e
recuperação estabelecidos na V1.

A forma de implementação da V2 permanece aberta. Classe, processos, containers,
threads ou um controlador dedicado são opções técnicas, não requisitos por si
só. A escolha deverá ser guiada por testes de concorrência, capacidade do banco,
observabilidade, desligamento gracioso e demanda real de produção.

## Mapa de responsabilidades

```text
callback/webhook  -> entrada HTTP e enfileiramento
callback/monitoramento -> login e autorização do painel por unidade
workers           -> processamento assíncrono e fluxo da conversa
core/repositories -> SQL e persistência
core/database     -> conexão, DDL e preparação do banco
core/cache        -> Redis, fallback e autocura detectável
core/integrations -> comunicação com serviços externos
core/triagem      -> catálogo puro compartilhado de perguntas
core/validacoes   -> validação pura compartilhada de e-mail e domínio de suporte por idade
utilitarios       -> diagnóstico, monitoramento e manutenção manuais
tests             -> testes, mocks, fakes e contratos
```

Direção esperada das dependências:

```text
webhook ────────┐
monitoramento ──┤──> core/repositories
worker ────────┤──> core/cache
admin ─────────┤──> core/integrations
utilitários ───┘

core nunca importa webhook ou worker
```

## Documentação por camada

O [`README.md`](README.md) da raiz é o portal da documentação. Cada README local
explica somente a responsabilidade e os contratos da sua camada:

- [`callback/README.md`](callback/README.md): aplicativos Django, webhook e estrutura do monitoramento;
- [`core/README.md`](core/README.md): mapa dos recursos compartilhados;
- [`workers/README.md`](workers/README.md): ciclo, checkpoints e recuperação;
- [`tests/README.md`](tests/README.md): estratégia e execução dos testes;
- [`core/cache/README.md`](core/cache/README.md): Redis, fallback e autocura;
- [`core/database/README.md`](core/database/README.md): conexão, DDL e setup;
- [`core/repositories/README.md`](core/repositories/README.md): contratos SQL;
- [`core/integrations/README.md`](core/integrations/README.md): integrações externas;
- [`core/integrations/whatsapp/README.md`](core/integrations/whatsapp/README.md):
  organização da integração Meta/PyWa.
- [`core/integrations/funil/README.md`](core/integrations/funil/README.md):
  envio de oportunidades e contrato do lead;
- [`utilitarios/README.md`](utilitarios/README.md): relatórios e comandos manuais;
- [`deploy/README.md`](deploy/README.md): arquivos dos serviços e migrações.

Os planos de evolução ficam separados em `docs/` e não descrevem, por si só,
funcionalidades implementadas.

READMEs locais não devem copiar regras completas. Eles apontam para
`REGRAS_DE_NEGOCIO.md` quando uma decisão de produto precisa ser interpretada e
para este documento quando a dúvida é sobre organização do código.

## `core`

`core` contém recursos compartilhados pelos diferentes pontos de entrada do
sistema. Um módulo pertence a `core` quando pode ser utilizado por webhook,
worker, Admin ou scripts sem depender do fluxo específico de nenhum deles.

Responsabilidades permitidas:

- conexão e preparação do banco;
- funções SQL de repositório;
- cache e fallback;
- integrações externas;
- validações puras reutilizadas e catálogos neutros de domínio;
- configuração por ambiente;
- configuração de logging;
- exceções compartilhadas.

Responsabilidades que não pertencem a `core`:

- laço infinito do worker;
- resposta HTTP do webhook;
- decisão de rota específica de uma etapa do worker;
- controle completo de uma transação de negócio;
- mocks ou dados exclusivos de teste.

## SQL e repositórios

### Localização

Consultas e alterações de dados da aplicação devem ficar em
`core/repositories/`.

Os repositórios são agrupados por domínio e entidade:

- `atendimento/`: clientes, conversas, dependentes, fila e histórico;
- `fluxo/`: políticas, transições, respostas da triagem e contextos por etapa;
- `unidades/`: consultas de unidade e controle de versão do cache;
- `seguranca/`: regra de turno e persistência de bloqueios Meta;
- `funil/`: configuração da integração por unidade e estado dos envios;
- `monitoramento/`: vínculo e autorização de recursos por conta/unidade.

Não agrupe operações apenas pelo verbo SQL. Uma mesma entidade pode concentrar
consultas, inserções, atualizações e exclusões relacionadas ao seu contrato.

DDL, criação de funções PostgreSQL e preparação de ambiente pertencem a
`core/database/deploy_database/`; migrações incrementais versionadas ficam em
`deploy/migrations/`. Nenhuma das duas áreas é repositório de runtime.

Os relatórios manuais em `utilitarios/reports_functions/` possuem consultas
analíticas próprias, somente leitura. Essa fronteira não autoriza mover SQL de
persistência do chatbot para os utilitários nem importá-los nos serviços.

### Contrato das funções SQL

Uma função de repositório deve:

- receber `cursor` como argumento;
- executar SQL parametrizado;
- retornar dados ou quantidade de linhas afetadas;
- validar invariantes persistidas quando necessário;
- registrar logs técnicos sem dados sensíveis completos.

Uma função de repositório não deve:

- abrir conexão com `get_conn`;
- executar `commit`, `rollback` ou `close`;
- decidir retry do worker;
- retornar `JsonResponse`;
- chamar Meta, PyWa ou Redis;
- esconder falha de persistência necessária para a regra de negócio.

Evite SQL em worker, webhook, integração ou cache quando a operação representa
persistência da aplicação. O ponto de entrada chama o repositório apropriado.

## Conexões e transações

O arquivo que conhece o fluxo completo é o dono da transação.

### Workers

Cada worker controla a conexão e os commits de seu próprio domínio:

```text
workers/worker_flow/response_flow/flow_worker.py
workers/worker_funil/funil_worker.py
workers/worker_followup/followup_worker.py
```

Repositórios e funções auxiliares recebem o cursor aberto pelo orquestrador.
Commits intermediários devem representar estados recuperáveis documentados nas
regras de negócio. Um worker não reutiliza a conexão do outro. Flow e follow-up
disputam o mesmo lock de conversa, com versão e expiração; somente seu proprietário
pode persistir o resultado. O Funil mantém sua reserva independente por envio.

### Webhook

A transação de enfileiramento pertence a:

```text
callback/webhook/services/post_flow.py
```

As transações independentes dos controles de abuso pertencem aos serviços:

```text
callback/webhook/services/flood_guard.py
callback/webhook/services/bloqueio_meta_guard.py
```

O módulo `populating_fila_mensagens.py` prepara, valida e insere usando o cursor
recebido, mas não abre ou finaliza conexão.

### Scripts e Admin

Scripts operacionais podem controlar a própria conexão quando são o ponto de
entrada completo da operação. No Django Admin, preserve o comportamento
Meta-first definido nas regras de negócio e utilize o gerenciamento transacional
do Django ou uma fronteira explícita quando necessário.

## Webhook

`callback/webhook` é a fronteira HTTP de recebimento dos eventos da Meta.

Responsabilidades:

- validar método, `Content-Type`, tamanho e assinatura;
- interpretar o payload da Meta;
- aplicar anti-flood;
- verificar se a mensagem pode entrar no turno;
- inserir a mensagem válida na fila;
- devolver a resposta HTTP apropriada;
- oferecer operações administrativas do Django relacionadas ao webhook.

O webhook não deve:

- responder a etapa da conversa;
- executar o fluxo do bot;
- retirar mensagens da fila;
- avançar etapa;
- manter textos de resposta do bot;
- importar PyWa diretamente.

Serviços HTTP pequenos ficam em `callback/webhook/services/`. `views.py` deve ser
uma borda fina e delegar o fluxo para esses serviços.

## Monitoramento

`callback/monitoramento` é um aplicativo Django próprio, registrado em
`INSTALLED_APPS`. Reúne login, autorização e interface do painel por
unidade, sem participar do recebimento de eventos da Meta. Compartilha o projeto
Django, a autenticação e o banco existentes. Login, conversas, relatórios e
exportação de contatos pertencem ao mesmo aplicativo.

`callback/monitoramento/monitoramento_guard.py` valida a sessão Django e usa um
cursor do Django para a leitura autoritativa em
`core/repositories/monitoramento/acessos.py`.
O repositório recebe o cursor, não abre conexão nem importa Django. Não há cache
do vínculo: ele é lido de `unidade.id_usuario_monitoramento`, sem tabela
intermediária. O login valida o vínculo antes de criar a sessão e ao mostrar a
confirmação de acesso. Cada rota de dados chama o guard e aplica explicitamente
o `id_unidade` retornado em todas as consultas.

`forms.py` estende a autenticação nativa do Django, sem SQL próprio para senhas.
`views.py` controla login, logout por POST, respostas HTML, APIs GET e CSV;
`urls.py` publica `/`, `/login/`, `/sair/`, `/dados/...` e `/contatos.csv`.
`services.py` coordena as leituras e `apresentacao.py` mantém transformações
puras. Os contratos completos estão no
[README dos aplicativos](callback/README.md#cadastro-e-autorização-do-monitoramento).

Templates e arquivos estáticos do painel pertencem, respectivamente, a
`callback/monitoramento/templates/monitoramento/` e
`callback/monitoramento/static/monitoramento/`. CSS, JavaScript e logo são locais,
sem recursos de terceiros na página. SQL de runtime continua em
`core/repositories/monitoramento/`, inclusive as leituras em `painel.py`; testes
continuam em `tests/`. O modelo `Unidade` e seu Admin permanecem em
`callback/webhook`.

A atualização automática é iniciada pelo JavaScript da página e gera requisições
GET comuns: 10 segundos para conversas e 30 segundos para relatórios. Ela não é
um worker, orquestrador ou serviço systemd. O mesmo processo web atende webhook,
Admin e monitoramento; o navegador só consulta a seção ativa e visível.

## Workers

`workers` contém processamento assíncrono e decisões do fluxo da conversa.

### `worker_flow`

Responsabilidades:

- selecionar mensagem da fila;
- validar cliente, unidade e conversa;
- adquirir e liberar lock da conversa;
- reconhecer estados intermediários e retries;
- validar histórico;
- rotear resposta ou tratamento;
- persistir resposta e contexto;
- reconhecer a reação com stage positivo ou marcador anterior e repetir a etapa
  sem resolver transições, zerando o stage na persistência final;
- marcar a fila como `sent` somente após a persistência necessária.

### `worker_followup`

Seleciona conversas elegíveis por inatividade no PostgreSQL, sem consumir a fila.
Cada candidata tem conexão, lock de conversa e transação próprios. O envio usa
`core/integrations/whatsapp`; elegibilidade, recibos e fencing ficam em
`core/repositories/atendimento/followup.py`.

A releitura após adquirir o lock verifica as etapas 1–17, sete horas sem resposta
ao bot e a janela da última mensagem do cliente. Confirmação do lembrete, histórico
e stage 1 são persistidos juntos. Uma falha individual não interrompe o lote.

O retorno pertence ao `worker_flow`: `transacoes/retorno_followup.py` prepara o
checkpoint da reação e persiste a repetição, sem controlar commits.
`response_flow/repeticao_followup.py` seleciona os senders da etapa sem executar
validadores, transições ou efeitos de negócio. O stage só é zerado junto da
persistência da repetição confirmada. Essa exceção reativa está documentada nas
regras de negócio e não altera o fluxo normal de stage zero.

### `worker_funil`

Responsabilidades:

- materializar conversas cuja política de etapa é `elegivel_funil`;
- reservar um `funil_envios` com `FOR UPDATE SKIP LOCKED`;
- obter o snapshot persistido do lead;
- encerrar a transação de leitura antes do HTTP;
- chamar `core/integrations/funil` uma oportunidade por vez;
- reagendar falha externa sem interromper os demais leads;
- confirmar `lead_no_funil` e `funil_envios = sent` no mesmo commit local;
- recuperar reservas abandonadas por lease.

`funil_worker.py` é o processo duradouro: executa ciclos isolados, aguarda o
intervalo `FUNIL_INTERVALO_SEGUNDOS` (padrão: 1.800 segundos, ou 30 minutos)
entre ciclos bem-sucedidos e recupera indisponibilidade operacional do
banco com espera linear de 5 em 5 segundos, limitada a 60. O arquivo
`iniciar_worker_funil.py` forma o laço supervisor externo; somente uma falha
crítica que escape do worker chega nele, provocando a recriação do worker após
5 segundos fixos. Esse padrão evita nomes `flow_worker.py` duplicados e mantém
recuperação operacional separada da supervisão do processo.

SQL permanece em `core/repositories/funil`. Payload, URL e interpretação da API
permanecem em `core/integrations/funil`. O worker é o único dono do retry e da
fronteira transacional.

`worker_funil` não importa `worker_flow`, não usa lock de conversa e não acessa
Redis. As duas áreas compartilham apenas recursos verdadeiramente centrais,
como conexão, configuração, logging e o tratamento genérico de reconexão em
`workers/tratamento_erros_externos`.

Não tente manter uma transação PostgreSQL aberta durante o POST. PostgreSQL e
Funil não formam uma transação distribuída; a pequena janela entre sucesso
externo e commit local deve ser documentada e reconciliável.

### `response_flow`

Contém orquestração de respostas:

- `flow_worker.py`: ciclo e transações;
- `flow_sender.py`: preservação da idempotência e seleção do resolver da etapa
  atual;
- `etapas/resolver_etapa<n>.py`: validação da etapa atual e encaminhamento para o
  destino autorizado;
- `etapas/validadores_universais/`: validações reutilizáveis entre etapas;
- `etapas/validadores_contexto/`: validações específicas da pergunta atual;
- `transicoes/contexto_transicao.py`: montagem explícita da fotografia de
  origem e destinos permitidos no contexto histórico;
- `transicoes/resolver_transicao.py`: resolução de
  `origem + evento -> destino`;

Na pasta irmã `workers/worker_flow/transacoes/` ficam
`movimento_conversa.py` (inicialização, transição ou permanência) e
`efeitos_transicao.py` (efeitos de banco de cada aresta autorizada).

Esses arquivos podem escolher qual integração chamar, mas não devem criar cliente
PyWa, montar `Button` ou manter textos de saída.

A navegação não utiliza `id_etapa + 1`. O worker identifica o evento, consulta
as transições permitidas para a origem e transporta a decisão no contexto. A
persistência final revalida a mesma aresta no PostgreSQL antes do commit.

Tratamentos não produzem evento de transição e permanecem na etapa atual.

Contextos específicos de idade e e-mail são carregados pelos repositórios. Os
resolvers aplicam as políticas da unidade, e os efeitos transacionais persistem
a decisão. A validação de formato de e-mail é pura e compartilhada em
`core/validacoes/email.py`; não depende de um resolver ou do Funil.

O prefixo de retorno após três horas é preparado com o histórico persistido e
aplicado pelo `flow_sender` somente depois da barreira de idempotência, no escopo
do resolver corrente. Não muda o destino nem autoriza um novo envio no replay.

### Escolha entre validador universal e contextual

Um validador só pertence a `validadores_universais` quando:

- é usado por mais de uma etapa;
- possui o mesmo significado em todas elas;
- apenas identifica tratamento/permanência ou permite seguir o fluxo;
- não escolhe entre diferentes arestas do mapa.

Mídia, o classificador-base de dúvida sobre reforço escolar, financeiro e nome
atendem a esse contrato. O resultado-base deles não muda de significado
conforme a etapa que os chama.

Quando o vocabulário universal também puder representar uma resposta legítima
de uma etapa específica, a desambiguação deverá ficar em
`validadores_contexto/` e delegar ao classificador universal depois de aplicar
somente a exceção local. Esse adaptador não envia mensagem, não acessa banco,
não altera contexto e não modifica o classificador compartilhado. A etapa 4
usa esse padrão para distinguir dúvida sobre reforço escolar de uma declaração
de profissão ou vínculo de trabalho com banca, cursinho, supletivo ou reforço.

Um validador pertence a `validadores_contexto` quando a resposta produz eventos
próprios daquela etapa, especialmente quando pode pular ou retroceder no mapa.
Mesmo que duas etapas reconheçam textos idênticos, cada uma mantém seu
validador quando devolve eventos diferentes:

```text
validar_etapa7("Quero agendar") -> oferta_aceita
validar_etapa9("Quero agendar") -> retorno_confirmado
```

Nesse caso, a semelhança da gramática não transforma o validador em universal.
O contrato relevante é o evento de negócio produzido para a origem atual.

O resolver deve receber diretamente esse evento:

```python
evento_transicao = validar_etapa7(texto_cliente)

destinos_esperados = _destinos_esperados_por_evento(evento_transicao)
etapa_destino = resolver_destino_transicao(
    contexto_historico,
    evento_transicao,
    destinos_esperados=destinos_esperados,
)
```

Não criar uma decisão neutra intermediária para depois traduzi-la em evento no
resolver. A interpretação de uma resposta que escolhe arestas pertence ao
validador contextual da própria etapa.

Todo resolver de etapa deve marcar explicitamente a fronteira entre validação e
resolução do destino. O marcador fica depois de todos os retornos de tratamento
e imediatamente antes da consulta ao mapa:

```python
# VALIDANDO DESTINO(S)
# A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
etapa_destino = resolver_destino_transicao(...)
```

Antes dessa fronteira, o resolver apenas valida a resposta e pode permanecer na
etapa atual. Depois dela, a resposta já é válida: o código resolve o destino,
chama o sender correspondente e anexa a transição ao contexto de envio.

Quando o resolver produz somente um evento e possui um único destino possível,
o conjunto esperado deve ficar explícito na chamada:

```python
etapa_destino = resolver_destino_transicao(
    contexto_historico,
    EVENTO_RESPOSTA_VALIDA,
    destinos_esperados={ETAPA_DESTINO},
)
```

Quando a mesma origem produz múltiplos eventos e destinos, o resolver deve
centralizar essa correspondência em
`_destinos_esperados_por_evento(evento_transicao)`. A função interna não é
necessária em fluxos lineares, pois apenas esconderia uma constante sem
representar uma decisão real.

### Constantes e efeitos de etapa

Toda constante de estado deve mostrar o número persistido e o significado:

```python
ETAPA_1_NOME_CLIENTE = 1
ETAPA_2_DESTINO_ATENDIMENTO = 2
ETAPA_3_CONFIRMACAO_DESTINO = 3
ETAPA_4_PROFISSAO = 4
ETAPA_5_NOME_DEPENDENTE = 5
ETAPA_6_IDADE_ALUNO = 6
```

Não usar números mágicos como `etapa_origem == 2` e não omitir o número no nome
da constante. Esse padrão permite localizar a etapa sem perder seu significado.

Em `transacoes/efeitos_transicao.py`, os efeitos devem ser agrupados primeiro
pela etapa de origem e depois pelo evento:

```python
# ETAPA 2
if etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO:
    if evento == EVENTO_DESTINO_ATENDIMENTO_DEFINIDO:
        # 2 -> 3: persiste a escolha inicial antes da confirmação.

# ETAPA 3
if etapa_origem == ETAPA_3_CONFIRMACAO_DESTINO:
    if evento == EVENTO_DESTINO_ATENDIMENTO_CONFIRMADO:
        # 3 -> 4: aplica o status final absoluto e sempre pede a profissão.

# ETAPA 4
if etapa_origem == ETAPA_4_PROFISSAO:
    if evento == EVENTO_PROFISSAO_DEPENDENTE_VALIDA:
        # 4 -> 5

    if evento == EVENTO_PROFISSAO_TITULAR_VALIDA:
        # 4 -> 6
```

Cada comentário de evento deve mostrar `origem -> destino`. A tabela
`etapa_transicao` continua sendo a fonte de verdade, e o código apenas torna
visíveis os efeitos de cada aresta autorizada.

Confirmação e profissão não podem transformar ausência de estado em titular.
Resolvers, replay e efeitos dessas pontes exigem `status_dependente` booleano;
um valor ausente ou inválido falha para retry em vez de usar `bool(None)`.

### Tratamento de erros

`workers/tratamento_erros_externos/` concentra decisões de retry, exclusão e
tratamentos específicos de falhas externas. Repositórios executam a alteração
solicitada, mas não escolhem a política de retry.

## Integrações externas

Toda integração externa compartilhada pertence a `core/integrations/<serviço>/`.

As integrações implementadas são `whatsapp` e `funil`. A pasta `google/` não
possui integração de runtime implementada.

Uma integração deve:

- encapsular a biblioteca ou API externa;
- receber dados já validados pelo chamador;
- converter retorno externo para um contrato simples da aplicação;
- traduzir falhas quando houver uma exceção de domínio apropriada;
- não controlar banco, fila, retry ou transação.

## WhatsApp e PyWa

Estrutura oficial:

```text
core/integrations/whatsapp/
├── exceptions.py
├── messages/
├── pywa_functions/
└── tools/
```

### `messages`

Armazena o catálogo de conteúdo enviado ao WhatsApp:

- textos;
- títulos de botão;
- callbacks;
- templates;
- funções puras de formatação ou seleção de template.

Não pode conter:

- `import pywa`;
- envio para a Meta;
- banco ou Redis;
- logging de integração;
- decisão de retry, lock ou etapa persistida.

Novos textos não devem ser escritos diretamente no worker ou em
`pywa_functions`. Organize-os por responsabilidade, como
`etapa<n>_messages.py` e `tratamentos_universais.py`.

Componentes compartilhados por um grupo de etapas podem possuir um helper
próprio. `triagem_componentes.py`, por exemplo, atende exclusivamente às etapas
12 a 17 e centraliza botões e rodapé, sem conter envio ou decisão de fluxo.

Quando o mesmo conteúdo de negócio for consumido por canais diferentes, ele
deve possuir uma fonte neutra fora das integrações. A triagem por faixa etária
usa `core/triagem/perguntas.py` como catálogo único das etapas 12 a 17. Os
arquivos de `messages` selecionam a pergunta para o WhatsApp e a integração do
Funil reutiliza exatamente o mesmo catálogo; nenhum dos dois deve manter uma
cópia independente dos textos ou da fronteira infantil/adulta.

A elegibilidade por idade continua na regra de negócio que antecede a triagem.
O catálogo apenas classifica uma idade persistida válida como infantil (`< 18`)
ou adulta (`>= 18`) e monta o texto. Consulta ao banco, BPA, transição e envio
não pertencem a esse módulo.

Componentes visuais usados por diferentes etapas pertencem a
`componentes_compartilhados.py`. Esse helper pode armazenar textos comuns e
funções puras de composição. A saudação de retorno recebe nome, etapa e horários
já carregados pelo chamador; não consulta histórico, não altera conversa e não
escolhe evento ou destino. Usar esses valores para formatar o texto não transfere
ao helper a decisão de fluxo.

Na PyWa utilizada pelo projeto, `header` e `footer` só são enviados quando a
mensagem possui botões e se torna interativa. Em mensagens de texto simples,
esses argumentos são ignorados.

O WhatsApp aplica estilos diferentes ao `header` nativo conforme o tipo da
mensagem interativa e não oferece controle do tamanho da fonte. Por isso, os
cabeçalhos textuais do fluxo — etapas 11 a 17 e 19 a 21 — são incorporados ao
início do corpo, em negrito, por `montar_texto_com_cabecalho`. Os senders não
devem passar `header` para a Meta. Novos cabeçalhos textuais devem reutilizar
esse helper para manter a apresentação uniforme entre listas e botões.

Rodapés continuam permitidos nos pontos definidos pelo produto e devem aparecer
em itálico. Como o Markdown não produz efeito no campo `footer` de uma mensagem
interativa, o projeto incorpora o rodapé ao próprio corpo usando `_texto_`,
mesmo quando a mensagem possui botões. O sender não deve passar `footer` para a
Meta nesses casos.

### `pywa_functions`

Concentra a criação do cliente PyWa e o transporte de mensagens do atendimento.
As operações compartilhadas de bloqueio/desbloqueio atualmente ficam em
`tools/usuarios.py` e reutilizam a mesma fábrica de cliente.

Responsabilidades:

- criar o cliente `WhatsApp`;
- criar tipos PyWa, como `Button`;
- chamar `send_message`;
- extrair IDs retornados;
- produzir o contexto de envio esperado pelo worker;
- converter falhas de envio para `ErroEnvioMeta` quando aplicável.

Não pode conter:

- SQL;
- Redis;
- `commit`, `rollback` ou `close`;
- decisão sobre limite de retry;
- mutação direta de conversa, histórico ou fila.

Quando várias etapas compartilham exatamente o mesmo contrato de transporte,
um sender-base pode centralizar apenas a mecânica comum. `triagem_base.py`
atende às etapas 12 a 17: monta os componentes PyWa, envia, extrai o ID da
mensagem e produz o contexto de envio. Os senders públicos de cada etapa
continuam responsáveis pelo conteúdo e o helper-base não pode validar respostas,
produzir eventos ou escolher destinos.

Separação interna atual:

- `cliente.py`: criação e normalização do cliente;
- `resposta_envio.py`: normalização da confirmação e do ID de envio;
- `saudacao.py`: saudação inicial;
- `pywa_senders/etapa<n>.py`: envios normais e tratamentos da respectiva etapa;
- `pywa_senders/triagem_base.py`: transporte comum das seis perguntas.

`cliente.py` também mantém o escopo temporário do prefixo de retorno, restaurado
mesmo sob exceção. O texto enviado e o texto persistido devem permanecer iguais.

### `tools`

Dentro de uma integração, contém operações administrativas que pertencem ao
domínio daquela integração e são reutilizadas pelo Django Admin, como ativação
de número e inscrição do WABA.

Na estrutura atual há também primitivas compartilhadas: `usuarios.py` é usado
pelo webhook e Admin, e `config.py` pela fábrica de cliente. Portanto, essa pasta
não é exclusivamente administrativa. Essas primitivas não decidem retry,
admissão, persistência ou transações; tais decisões continuam nos chamadores.

Comandos iniciados conscientemente por uma pessoa apenas para diagnóstico,
monitoramento, manutenção ou probe pertencem à pasta `utilitarios`, não a
`core/integrations/<serviço>/tools`. Nenhum dos quatro pontos de entrada —
webhook, `worker_flow`, `worker_funil` e Django Admin — importa `utilitarios`.

Configuração operacional:

```text
core/integrations/whatsapp/tools/config.py
```

Esse arquivo fornece a configuração compartilhada da integração WhatsApp, mas os
valores vêm de `core/config_env.py` e das variáveis de ambiente. Ele não deve
armazenar token, WABA ID, phone number ID ou outro valor sensível diretamente no
código.

## Cache

`core/cache` concentra Redis, cache local e mecanismos de fallback.

Regras:

- banco continua sendo a fonte persistida da verdade;
- cache deve possuir fallback quando a regra de negócio exigir disponibilidade;
- falhas detectáveis de cache stale devem permitir reparo seguro;
- chaves devem ser normalizadas e centralizadas;
- cache não controla transações do banco;
- uma falha de Redis não deve ser silenciosamente tratada como dado válido;
- logs devem informar fallback e autocura sem expor dados completos.

`core/cache/runtime/` contém caches utilizados durante a execução normal.
Operações administrativas de reset devem permanecer separadas do caminho comum.

## Django Admin

O Admin é uma interface operacional, não uma segunda implementação das regras.

Regras:

- reutilizar funções de integração e repositório existentes;
- não duplicar chamadas PyWa;
- preservar operações Meta-first;
- se a Meta falhar, não confirmar alteração correspondente no banco ou Redis;
- manter tabelas de auditoria majoritariamente somente para leitura;
- ações permitidas devem seguir `REGRAS_DE_NEGOCIO.md`.

## Logging e exceções

- utilizar `logging`, não `print`, nos fluxos de runtime;
- obter logger por responsabilidade, como `worker.*`, `webhook.*` e
  `whatsapp.*`;
- utilizar `short_value` para dados identificadores nos logs;
- nunca registrar tokens, segredos, payloads completos ou credenciais;
- usar `logger.exception` quando o traceback é necessário;
- não capturar `Exception` apenas para ocultar erro sem fallback definido;
- exceções de integração devem carregar contexto mínimo útil, sem segredo.

`print` é aceitável em scripts de relatório executados manualmente e em saídas de
desenvolvimento já delimitadas.

## Configuração e segredos

- não adicionar novos tokens ou credenciais diretamente no código;
- usar `core/config_env.py` para leitura e validação de variáveis de ambiente;
- documentar apenas os nomes das variáveis, nunca seus valores secretos;
- manter `.env` fora do Git;
- IDs públicos e limites podem ser constantes quando não forem segredos;
- configurações de infraestrutura não devem alterar silenciosamente regras de
  negócio; políticas explícitas da unidade, como `idade_minima_suporte` e
  `email_obrigatorio`, são lidas e aplicadas pelos contextos e resolvers próprios;
- testes devem usar valores fictícios e nunca credenciais reais.

## Testes

Todo teste, mock, fake e payload exclusivo de teste deve ficar em `tests/`.

Estrutura atual:

```text
tests/
├── helpers.py
├── fixtures/
├── unit/
│   └── test_*.py
└── integration/
    └── test_followup_postgres.py
```

Regras:

- não criar testes em módulos de produção;
- não adicionar `Mock`, `MagicMock`, `patch` ou classes `Fake*` fora de `tests/`;
- testar comportamento e contratos, não somente linhas internas;
- falhas externas devem ser simuladas sem acessar Meta, Redis ou AWS reais;
- alterações de fluxo crítico devem cobrir sucesso, falha e retry;
- alterações estruturais devem possuir testes que impeçam regressão da
  organização quando isso for relevante;
- a suíte completa deve permanecer executável por descoberta.

A integração PostgreSQL exige `FOLLOWUP_TEST_DSN` apontando para loopback e um
banco descartável chamado `test_chatbot_followup`, sem schema `chatbot` prévio.
Sem essa variável, é pulada. Não usa as credenciais de produção do `.env`; Meta
continua simulada. Consulte o [guia de testes](tests/README.md#follow-up).

Comando padrão:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py" -v
```

Fluxos críticos que não podem perder cobertura:

- A/B/C e primeira mensagem do turno;
- idempotência após resposta persistida;
- falha do banco após envio confirmado pela Meta;
- limite de retries e exclusão;
- ordenação e locks;
- retrocesso e salto de etapa;
- `last_message_from` semântico;
- fallback e autocura de cache;
- transações de worker e webhook;
- elegibilidade proativa, recibos, migração do legado e retorno sem avanço de etapa;
- intenção local antes dos bloqueios automáticos e desbloqueio administrativo
  Meta-first.

## Nomes e organização de arquivos

- arquivos e funções devem usar `snake_case`;
- nomes devem descrever responsabilidade, não detalhes passageiros;
- evitar arquivos genéricos como `utils.py` quando existe um domínio claro;
- uma função reutilizada deve morar na camada proprietária da responsabilidade;
- constantes de um domínio devem ficar próximas ao domínio;
- não criar pasta nova para apenas um arquivo sem perspectiva clara de fronteira;
- não criar arquivo que apenas reexporta outro sem necessidade real de
  compatibilidade.

## Imports e dependências

- preferir imports absolutos a partir da raiz do projeto;
- evitar import circular por meio de fronteiras claras, não por imports tardios
  espalhados;
- worker e webhook podem importar `core`;
- `core` não importa worker ou webhook;
- `messages` não importa `pywa_functions`;
- `pywa_functions` pode importar `messages`, cliente e exceções da integração;
- repositórios não importam integrações;
- testes podem importar qualquer módulo necessário para validar contratos.

## Anti-padrões proibidos

- SQL diretamente em `flow_worker.py` ou `post_flow.py`;
- `commit` dentro de `core/repositories`;
- texto de WhatsApp escrito dentro do worker;
- `send_message` fora de `pywa_functions`;
- regra de retry dentro de um sender;
- acesso ao Redis dentro de uma função PyWa;
- `JsonResponse` dentro de repositório;
- mock dentro de código de produção;
- duplicação de regra de negócio no Admin;
- fachada ou wrapper sem responsabilidade própria;
- captura silenciosa de erro que transforme falha em sucesso;
- refatoração estrutural misturada com mudança de comportamento sem testes e
  documentação explícita.

## Como decidir onde criar uma função

Use esta sequência:

1. Executa SQL da aplicação? `core/repositories`.
2. Abre ou prepara infraestrutura de banco? `core/database`.
3. Gerencia cache ou fallback de cache? `core/cache`.
4. Chama serviço externo compartilhado? `core/integrations/<serviço>`.
5. Envia mensagens com PyWa? `core/integrations/whatsapp/pywa_functions`;
   bloqueio/desbloqueio reutiliza `core/integrations/whatsapp/tools/usuarios.py`.
6. Define texto ou callback do WhatsApp? `messages`.
7. Trata HTTP da Meta? `callback/webhook`. Trata acesso ou interface do painel?
   `callback/monitoramento`.
8. Decide processamento assíncrono ou etapa? `workers`.
9. É comando humano de diagnóstico, monitoramento, manutenção ou probe?
   `utilitarios`.
10. Existe apenas para validar comportamento? `tests`.

Se a função responder positivamente a mais de uma pergunta, provavelmente deve
ser dividida em orquestração e operação de baixo nível.

## Checklist para alterações futuras

Antes de implementar:

1. Ler `REGRAS_DE_NEGOCIO.md` e este documento.
2. Identificar a camada proprietária da responsabilidade.
3. Mapear contratos, chamadores e estados intermediários afetados.
4. Confirmar que a mudança não duplica uma função existente.

Durante a implementação:

1. Manter transações no orquestrador correto.
2. Preservar logs e exceções relevantes.
3. Não misturar refatoração com nova regra de negócio.
4. Criar ou atualizar testes somente em `tests/`.

Depois da implementação:

```powershell
python -m unittest discover -s tests -t . -p "test_*.py" -v
python -m compileall core workers callback utilitarios tests
python callback/manage.py check
git diff --check
```

Também confira:

- imports antigos removidos;
- envios PyWa em `pywa_functions` e operações de usuários na primitiva compartilhada;
- textos de WhatsApp apenas em `messages`;
- SQL e transações nas camadas corretas;
- nenhum segredo novo no diff;
- nenhuma alteração não relacionada à tarefa.

## Atualização deste documento

Este documento deve ser atualizado quando:

- uma nova camada for criada;
- a propriedade de uma transação mudar;
- uma integração externa ganhar estrutura própria;
- uma exceção arquitetural deixar de ser temporária;
- um padrão recorrente for aprovado para uso futuro.

Mudanças neste documento não substituem testes nem alteram automaticamente as
regras de negócio.
````

### Passo 29 — `core/README.md`

**Ação:** Alterar. Atualizar a referência à configuração compartilhada.

Conteúdo completo do arquivo:

```markdown
# Core

Recursos compartilhados pelo webhook, monitoramento, workers, Django Admin e ferramentas
operacionais. `core` não conhece o fluxo completo de nenhum ponto de entrada.

- [Portal do projeto](../README.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)

## Mapa

| Pasta ou arquivo | Responsabilidade | Documento |
|---|---|---|
| `cache/` | Redis, cache local, fallback e autocura | [cache/README.md](cache/README.md) |
| `database/` | Conexão, DDL, funções PostgreSQL e setup | [database/README.md](database/README.md) |
| `repositories/` | SQL de runtime usando cursor recebido | [repositories/README.md](repositories/README.md) |
| `integrations/` | Comunicação com serviços externos | [integrations/README.md](integrations/README.md) |
| `triagem/` | Catálogo único das seis perguntas, compartilhado pelo WhatsApp e Funil | [triagem/perguntas.py](triagem/perguntas.py) |
| `validacoes/` | Validação pura de e-mail, sem acesso ao banco ou envio | [validacoes/email.py](validacoes/email.py) |
| `config_env.py` | Leitura de `.env`, variáveis de ambiente e validação de tipos | [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md#configuração-e-segredos) |
| `logging_config.py` | Configuração comum de logs e redução de identificadores | [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md#logging-e-exceções) |

## Contrato

`core` pode:

- encapsular infraestrutura compartilhada;
- executar operações de baixo nível;
- fornecer contratos simples para pontos de entrada;
- compartilhar regras puras e catálogos usados por mais de um consumidor;
- definir exceções de domínio compartilhadas.

`core` não deve:

- iniciar o laço infinito do worker;
- retornar `JsonResponse`;
- decidir etapa da conversa;
- escolher limite de retry;
- conter mocks ou dados exclusivos de teste;
- importar `workers` ou `callback`.

As transações pertencem ao arquivo que conhece o fluxo completo. Repositórios e
integrações não devem assumir propriedade de conexão recebida de outro módulo.

## Políticas e dados do atendimento

As configurações `idade_minima_suporte` e `email_obrigatorio` pertencem à unidade. Os
contextos em `repositories/fluxo/contextos/` fornecem esses dados aos resolvers;
a decisão de encaminhar, tratar ou avançar permanece no worker.

A profissão é preservada na conversa e atualizada no cadastro do cliente. O
Funil utiliza o e-mail da resposta aceita naquele atendimento, inclusive a
ausência permitida, sem substituir esse histórico pelo cadastro de outra
conversa. Consulte os contratos de
[repositórios](repositories/README.md) e da
[integração Funil](integrations/funil/README.md) antes de alterar essa fronteira.

O follow-up usa `repositories/atendimento/followup.py` para elegibilidade,
fencing e registros de envio/retomada; conteúdo e transporte pertencem a
`integrations/whatsapp`. A criação das tabelas fica em `database/deploy_database`,
e a migração de uma base existente em `deploy/migrations`. O laço proativo e a
decisão de repetir a etapa no retorno continuam nos respectivos workers.
```

### Passo 30 — `core/database/README.md`

**Ação:** Alterar. Documentar DDL final e migração incremental preservando as referências históricas.

Conteúdo completo do arquivo:

````markdown
# Banco de dados

Conexão PostgreSQL, verificação, DDL, funções SQL e preparação do ambiente.

- [Portal do projeto](../../README.md)
- [Padrões de arquitetura](../../PADROES_DE_ARQUITETURA.md#conexões-e-transações)
- [Repositórios de runtime](../repositories/README.md)

## Estrutura

```text
core/database/
├── connection_aws.py
├── connection_check.py
└── deploy_database/
    ├── setup_database.py
    ├── bank_script.py
    ├── followup_script.py
    ├── transacao_deploy.py
    ├── cache_control_script.py
    ├── etapa_transicao_script.py
    ├── floodscript.py
    ├── turno_cliente_script.py
    └── povoar_etapas.py
```

## Runtime e deploy

- `connection_aws.py` fornece conexões para os orquestradores e aceita
  `connect_timeout` opcional; o follow-up e seu diagnóstico usam 10 segundos;
- `connection_check.py` valida acesso ao PostgreSQL;
- `deploy_database/` cria schema, tabelas, índices e funções;
- partições mensais são mantidas pelo comando manual
  `utilitarios.maintenance.message_partitions`;
- SQL de negócio executado durante atendimento fica em `core/repositories`.

## Setup

Em uma instalação vazia, prepare primeiro o schema `chatbot` e as tabelas
gerenciadas pelo Django. No banco de destino:

```sql
CREATE SCHEMA IF NOT EXISTS chatbot;
```

Depois, com as variáveis do ambiente configuradas, a partir da raiz:

```powershell
python callback/manage.py migrate --noinput
```

Somente então execute o setup do banco de negócio:

```powershell
python -m core.database.deploy_database.setup_database
```

Ordem atual:

```text
healthcheck
-> configuração única da role
-> schema principal final
   (inclui tabelas de follow-up por followup_script.py)
-> controle de cache
-> tabelas de flood
-> índices de turno
-> função de dequeue
-> funções de lock
-> seed de etapas
-> whitelist de transições de etapas
-> reset de cache de desenvolvimento
```

`povoar_etapas.py` mantém o catálogo de estados com IDs estáveis.
`etapa_transicao_script.py` mantém a whitelist executável de
`origem + evento -> destino`. Uma aresta só deve entrar no seed quando resolver,
sender, efeitos transacionais e testes estiverem prontos.

`transacao_deploy.py` centraliza conexão, commit, rollback e fechamento. Uma
falha é relançada e interrompe o setup antes do log de finalização. Funções
concluídas anteriormente mantêm seu próprio commit; a reexecução idempotente
completa os passos restantes.

Os comandos utilizam `IF NOT EXISTS`, `CREATE OR REPLACE` ou `ON CONFLICT` onde
aplicável. Por isso, um setup interrompido normalmente pode ser executado de
novo sem apagar o banco.

`bank_script.py` descreve diretamente o schema final da V1. Ele não contém
`ALTER TABLE`, correções de colunas antigas, dados de unidade ou migrações
históricas. As tabelas são criadas em ordem de dependência para que chaves
estrangeiras e constraints já nasçam prontas.

`chatbot.auth_user` é um pré-requisito explícito do DDL de negócio. Sua criação
continua pertencendo às migrations do Django; o DDL não recria tabelas internas
do framework. Se ela não existir, o setup falha com uma orientação antes de
criar as tabelas de negócio.

`unidade.id_usuario_monitoramento` é `INT NULL`, único quando preenchido e
referencia `chatbot.auth_user(id)` com `ON DELETE SET NULL`. O DDL final define
a coluna e suas constraints no `CREATE TABLE` da unidade. O banco garante a
relação 1:1 opcional; a autorização dos recursos pertence ao serviço HTTP e ao
repositório de monitoramento. Excluir um usuário não exclui a unidade.

O schema final inclui `integracao_funil_unidade`, configuração 1:1 da unidade,
`funil_envios`, fila operacional 1:1 da conversa, a profissão informada pelo
cliente naquela conversa, a profissão válida mais recente no cadastro do
cliente e `pesquisa_satisfacao`, registro 1:1 de nota e comentário opcional da
conversa. As etapas 18 a 22 são marcadas como
`elegivel_funil`; os dados da pesquisa não compõem o payload do Funil. A etapa
20 registra a decisão de comentar, a etapa 21 coleta o comentário quando aceito
e a recusa salta diretamente da etapa 20 para a 22. Encerramento e bloqueio de
30 dias são exclusivos da política da etapa 22.

Cada unidade possui `idade_minima_suporte INTEGER NULL DEFAULT NULL`, limitada
por CHECK a NULL/50/60/70/80/90, e `email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE`.
O limite encaminha apenas titulares a partir da idade escolhida até 99 anos;
NULL desativa. A coleta de e-mail conserva a exceção universal do titular 60+.

O SQL `deploy/migrations/20260911_idade_minima_suporte.sql` converte a coluna
booleana anterior: TRUE vira 60 e FALSE vira NULL. É transacional, verifica
as configurações por unidade e recusa reaplicação/schema parcial. Não altera
conversas, históricos ou stages do follow-up. Instalação limpa usa o DDL atual;
não deve executar novamente as migrações históricas sobre o schema final.
Ver [procedimento coordenado](../../deploy/idade_minima_suporte.md).

A migração incremental que insere a confirmação como etapa 3 e remapeia as
referências existentes está em
`deploy/migrations/20260809_adicionar_confirmacao_etapa3.sql`. Ela deve ser
executada inteira no DBeaver, em janela de manutenção e com snapshot recente;
`setup_database.py` não substitui essa migração.

A correção posterior que torna a profissão obrigatória depois da confirmação
está em
`deploy/migrations/20260811_tornar_profissao_obrigatoria_apos_confirmacao.sql`.
Ela troca somente o catálogo de transições, aceita reexecução no estado final e
não retrocede conversas que já passaram pela profissão.

A migração que adiciona `cliente.profissao` está em
`deploy/migrations/20260823_adicionar_profissao_cliente.sql`. Ela mantém
`conversa.profissao` como snapshot e preenche o cadastro com a profissão não
vazia da conversa mais recente de cada cliente.

A migração que adiciona as duas políticas da unidade e amplia o domínio de
`conversa.motivo_encerramento` está em
`deploy/migrations/20260829_adicionar_suporte_idoso_email_obrigatorio.sql`.
Ela altera somente o schema, aceita reexecução no estado final e não executa
`UPDATE` nem `INSERT` sobre os dados de negócio.

A migração que renomeia `unidade.nome` para `nome_unidade` e adiciona a
apresentação configurável do agente está em
`deploy/migrations/20260812_personalizar_agente_unidade.sql`. Ela preserva os
nomes das unidades existentes, aplica `Suh`/`feminino` somente no primeiro
backfill e recusa schemas parciais antes de publicar o novo contrato.

`IF NOT EXISTS` não migra uma estrutura criada por uma versão antiga. Evolução
de schema existente exige um script de migração separado ou decisão consciente
de recriação em desenvolvimento. Novas migrações não devem ser anexadas ao DDL
de criação final.

A migração atual de monitoramento está em
`deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql`.
Execute-a inteira no DBeaver antes de publicar o código atualizado, com
`chatbot.unidade` e `chatbot.auth_user` já existentes. Ela adiciona a coluna
opcional e suas constraints. Se a tabela da proposta anterior existir,
transfere seus vínculos, confere o resultado e só então remove essa tabela,
sem `CASCADE`. Vínculos inválidos ou ambíguos interrompem a transação.
O SQL anterior de criação da tabela foi substituído e não deve ser executado.
A migração atual é de aplicação única: coluna já existente causa erro em vez
de aceitar uma estrutura divergente. Em caso de erro, execute `ROLLBACK`.
`ALTER TABLE`, transferência e remoção de legado ficam somente na migração;
o DDL continua sendo exclusivamente a definição final para instalação nova.

## Registros de follow-up

O DDL de instalação limpa inclui três tabelas não particionadas, criadas por
`deploy_database/followup_script.py` dentro da transação de `bank_script.py`:

| Tabela | Responsabilidade |
|---|---|
| `followup_envio` | Recibo por conversa e ID/data da mensagem do bot que originou o ciclo; registra o histórico e o WAMID do lembrete confirmado. |
| `followup_retomada` | Checkpoint da reação do cliente por conversa, fila e hash; preserva etapa, stage anterior e conclusão para retries. |
| `followup_legado` | Auditoria das conversas ativas marcadas na migração, com stage anterior e data da marcação. |

As FKs dessas tabelas apontam para a conversa com `ON DELETE CASCADE`; o
histórico de mensagens continua particionado. Não há nova tabela Django nem
ação administrativa para editar esses registros. `followup_stage` e
`followup_last_sent_at` já pertencem à tabela `conversa`.

Para uma base anterior à V1.2.0, use uma única vez
[followup_registros.sql](../../deploy/migrations/followup_registros.sql), com
flow parado e follow-up desligado. O script inteiro é transacional: cria os
registros, audita todas as conversas ativas e marca `followup_stage = 1`, inclusive
nas etapas 18–21. Não altera etapa, histórico, finalização ou datas anteriores e
não envia mensagens. Legado ativo terminal/inconsistente cancela a migração.

Na produção atual, essa migração já foi aplicada. Não a repita em deploys
seguintes: a reaplicação falha em vez de remarcar conversas. O setup de banco
vazio cria a estrutura sem marcar o legado. A role da aplicação precisa ter
permissões de leitura e escrita nas novas tabelas, por propriedade ou grants.
O [diagnóstico sem envio](../../utilitarios/README.md#diagnóstico-de-follow-up)
confere as consultas; ele não comprova as permissões de escrita.

Histórico, recibo e stage 1 são confirmados juntos pelo worker proativo.
Histórico da repetição, conclusão da retomada e reset do stage são confirmados
juntos pelo flow. A chamada à Meta ocorre fora dessa atomicidade local;
aceite externo seguido de falha no commit ainda pode gerar duplicidade.

## Atomicidade

No PostgreSQL, o DDL utilizado pelo projeto participa de transações. Uma tabela
não é criada pela metade: o bloco da função confirma ou reverte sua transação.
O banco pode ficar parcialmente configurado entre funções independentes, e a
reexecução completa os passos restantes.

## Funções PostgreSQL críticas

`bank_script.py` define:

- dequeue e retomada de mensagens abandonadas;
- lock e unlock versionados da conversa;
- tabelas, restrições e índices principais;
- timezone e timeouts operacionais.

Mudanças nessas funções podem alterar ordenação, retry e exclusão mútua. Consulte
[Regras de negócio](../../REGRAS_DE_NEGOCIO.md) e atualize testes de contrato.

## Segurança

Credenciais de banco são carregadas por `core/config_env.py` a partir de
variáveis de ambiente:

```text
DB_HOST
DB_NAME
DB_USER
DB_PASSWORD
DB_PORT
DB_SSLMODE
DB_SSLROOTCERT
```

`DB_SSLMODE` e `DB_SSLROOTCERT` são opcionais para preservar o comportamento
local. Em produção, use `DB_SSLMODE=verify-full`, aponte
`DB_SSLROOTCERT` para uma CA confiável e mantenha em `DB_HOST` o hostname real
do servidor, necessário para a validação do certificado.

Novas credenciais não devem ser adicionadas ao código, README, logs ou prints.
Em desenvolvimento, use o `.env` local privado e ignorado pelo Git. Em produção,
use variáveis do serviço, arquivo de ambiente com permissão restrita ou
gerenciador de segredos.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_followup.py`;
- `tests/integration/test_followup_postgres.py` (PostgreSQL local descartável).

A organização e o comando da suíte completa estão em `tests/README.md`.
````

### Passo 31 — `core/repositories/README.md`

**Ação:** Alterar. Atualizar o contrato do contexto da etapa 6.

Conteúdo completo do arquivo:

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
|   |-- followup.py
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

- `fluxo/contextos/etapa6.py` lê `idade_minima_suporte`, `bpa_ativo` e número comercial
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
worker_followup -> followup_worker.py
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

`listar_elegiveis` e `reler_elegivel` usam o mesmo SQL: etapa 1–17, stage zero,
última mensagem do bot confirmada há pelo menos sete horas, última mensagem do
cliente dentro de 23h59, unidade adimplente e ausência de bloqueios ou fila aberta.
Os horários do bot e do cliente são condições separadas. A paginação usa
`(ancora_em, id_conversa)` para não ficar presa nas primeiras falhas.

`proteger_conversa` confere `processing`, `lock_version` e validade de 110
segundos antes da persistência, com renovação antes do envio. A retomada
concluída é reconhecida por sua entrada original; um replay não zera um novo ciclo.
`consultar_diagnostico` executa transação somente leitura e não adquire o lock de
processamento nem envia mensagens. Os contratos reais de SQL e migração são
verificados em `tests/integration/test_followup_postgres.py`.
````

### Passo 32 — `core/integrations/whatsapp/README.md`

**Ação:** Alterar. Explicar o limite recebido pelo sender e a mensagem parametrizada.

Conteúdo completo do arquivo:

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
│   ├── followup_messages.py
│   ├── tratamentos_universais.py
│   └── triagem_componentes.py
├── pywa_functions/
│   ├── cliente.py
│   ├── saudacao.py
│   ├── resposta_envio.py
│   ├── ferramentas.md
│   └── pywa_senders/
│       ├── etapa1.py ... etapa22.py
│       ├── followup.py
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
o cliente retorna com `followup_stage = 0` pelo menos três horas após o último envio confirmado do bot
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
`idade_minima_suporte`, comparar a idade do titular ao limite e encerrar o
atendimento é do worker. O sender recebe o limite validado e o catálogo monta
o texto; com 60, preserva exatamente a mensagem antiga. As cinco variantes
oficiais permitem reconhecer uma resposta existente sem reenviá-la. Da mesma forma, a política `email_obrigatorio` e a distinção entre
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

`messages/followup_messages.py` contém o único texto aprovado:
`Você viu a minha mensagem?`.
`pywa_senders/followup.py` envia texto sem botões, sem saudação de retorno e sem
id_mensagem_fila fictício. Usa sessão HTTP com timeout e sem retry automático;
recebe destinatário e phone_id da unidade. `conta_wa` aceita sessão opcional sem
alterar os clientes existentes. A sessão usa timeout de 20 segundos por operação,
com conexão limitada a 5 segundos. Stage e persistência pertencem ao worker/repositório.
O ID retornado confirma o aceite da API; os eventos `sent`, `delivered` e `read`
recebidos pelo webhook não atualizam o histórico nesta versão.
````

### Passo 33 — `workers/README.md`

**Ação:** Alterar. Documentar decisão, efeito e recuperação pela configuração atual.

Conteúdo completo do arquivo:

````markdown
# Workers

Camada assíncrona responsável pelo atendimento no WhatsApp, lembretes de
inatividade e publicação periódica de oportunidades no Funil de Vendas.

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
│   │   ├── repeticao_followup.py
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
│   │   ├── retorno_followup.py
│   │   ├── movimento_conversa.py
│   │   ├── finalizacao_fila.py
│   │   ├── lock_conversa.py
│   │   └── ordem_turno.py
│   └── suporte/
│       ├── cache_repair.py
│       └── estado_ciclo.py
├── worker_followup/
│   ├── iniciar_worker_followup.py
│   ├── config.py
│   └── followup_worker.py
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
-> reler conversa sob lock e reconhecer retomada de follow-up
-> persistir histórico do cliente
-> repetir etapa na retomada; nos demais casos, rotear e enviar resposta
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
4. aquisição do lock;
5. vínculo, releitura e histórico do cliente, incluindo o marcador de retomada quando aplicável;
6. renovação do lock antes do envio;
7. histórico e contexto do bot; na retomada, conclusão do marcador e reset do stage;
8. status `sent`, após conferir novamente a posse do lock;
9. unlock.

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
- `repeticao_followup.py`: reapresentação da etapa na reação ao follow-up ou
  legado marcado, preservando a resposta já existente;
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
- Etapa 6: `idade_minima_suporte` aceita NULL (desativado), 50, 60, 70, 80 ou 90.
  Encaminha somente titulares a partir do limite até 99 anos, persiste a idade e
  encerra na etapa 6 com `encaminhado_suporte_idoso`, sem bloqueio ou Funil.
  Dependentes seguem as regras atuais. Pessoas de 100+ conservam o encaminhamento
  próprio para titular ou dependente, mesmo com suporte desativado.
  Na recuperação, as cinco mensagens oficiais identificam a resposta já enviada;
  uma reavaliação usa o limite atual, sem recuperar a configuração anterior.
  A barreira de idempotência impede reenvio e não cria avanço de etapa.
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
- Etapa 11: `Começar triagem`, o callback do botão e confirmações textuais como
  `iniciar triagem`, `sim` e `vamos começar` autorizam o início. A classificação
  permanece no validador contextual da etapa, após os tratamentos universais.

No retry já respondido, o resultado aceito do e-mail e o encaminhamento de
suporte são reconstruídos pelo histórico original, sem nova chamada à Meta
nem reavaliação da decisão pela configuração atual da unidade.

### Saudação de retorno

No caminho normal com `followup_stage = 0`, após a etapa 1,
`valida_historico.py` compara o horário da mensagem atual do
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
- `tests/unit/test_sondas_funil.py`;
- `tests/unit/test_followup.py`;
- `tests/integration/test_followup_postgres.py`.

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

### Configuração e elegibilidade

| Variável | Padrão no Python | Valores aceitos |
|---|---|---|
| `FOLLOWUP_WORKER_ENABLED` | `False` | Booleano; a unit configura `true`. |
| `FOLLOWUP_POLL_SECONDS` | `60` | 5–3.600 segundos de espera após cada lote. |
| `FOLLOWUP_BATCH_SIZE` | `20` | 1–100 candidatas por lote; processamento sequencial. |

O texto é `Você viu a minha mensagem?`. Para despachar, todas as condições
precisam continuar válidas na releitura após adquirir o lock:

- conversa ativa, sem finalização, em etapa 1–17 não terminal;
- `followup_stage = 0` (`NULL` é tratado como zero);
- última mensagem da conversa é do bot, confirmada como `sent`, com pelo menos
  sete horas, e `last_interaction_at` corresponde a essa mensagem;
- última mensagem do cliente tem menos de 23h59, reservando um minuto da janela
  de 24 horas; não existe mensagem do cliente com horário igual ou posterior ao bot;
- unidade adimplente, destinatário e números da unidade presentes;
- menos de 12 turnos sem avanço, sem bloqueio persistido ou flood no banco;
- nenhuma fila `pending`/`processing` do par cliente/unidade, inclusive sem vínculo;
- nenhum recibo que já cubra a âncora ou o próprio lembrete, nem retomada aberta com fila pendente.

Exemplo: bot há 8 horas e cliente há 25 horas não permitem envio; bot há 8 horas
e cliente há 9 horas permitem, se os demais critérios forem atendidos.
O relógio de elegibilidade vem do PostgreSQL. Os limites de etapa e de tempo
são regras do código/SQL, não novas variáveis de ambiente.

O sucesso persiste histórico, recibo e stage 1 no mesmo commit. Não há segunda
mensagem enquanto o cliente não reagir. Uma confirmação da Meta seguida de
falha no commit local ainda pode resultar em duplicidade no retry; o worker
registra `followup_commit_falhou` como crítico.

### Retomada pelo flow

No flow, o contexto é relido depois do lock. `transacoes/retorno_followup.py` registra
a reação e recupera a prova de repetição. `response_flow/repeticao_followup.py`
chama os senders normais da etapa, sem resolvers de negócio. A renovação do lock
antes do envio acrescenta um checkpoint; persistência final e finalização da fila
validam a posse antes de alterar dados. Repositórios não controlam commits.
Stage positivo, por lembrete ou migração inicial, prefixa a repetição com
`Que bom te ver novamente, <nome>!` ou `Que bom te ver novamente!` sem nome salvo.
O histórico guarda exatamente o texto enviado. Stage zero mantém `Olá novamente`
na regra existente de três horas.

A primeira reação é guardada, mas não valida nem avança a etapa. A repetição
mantém botões e dados persistidos; não altera `turnos_sem_avanco`, Funil ou
encerramento. Stage zero, histórico da repetição e conclusão do marcador só são
confirmados juntos após o envio. `followup_last_sent_at` permanece como auditoria.
Falha preserva a retomada; replay concluído não reenvia nem zera um ciclo posterior.
O legado marcado também pode repetir etapas 18–21, embora elas não recebam
proativos. A etapa terminal 22 não é repetível por esse caminho.

### Operação e logs

`SIGTERM`/`SIGINT` sinalizam parada e interrompem a espera entre lotes; uma
candidata já em andamento passa pela limpeza da conexão e do lock. Falhas de
consulta usam espera exponencial de 5 até 300 segundos. A unit usa
`Restart=on-failure`, `RestartSec=5s` e `TimeoutStopSec=100s`.

`followup_iniciado` informa a configuração. `followup_despacho` antecede a chamada
externa, e `followup_confirmado` confirma a persistência local. Não há log INFO a
cada varredura vazia; ausência de despachos não comprova falha. Para consultar
candidatas sem envio, use o [diagnóstico](../utilitarios/README.md#diagnóstico-de-follow-up).

Deploy: preparar banco e código, reiniciar flow compatível, então iniciar follow-up.
Rollback: parar o proativo primeiro e manter flow compatível enquanto houver stage
positivo ou retomadas pendentes. Desligar o serviço não limpa esses registros.
Os comandos completos ficam na [rotina de deploy](../regras_deploy/rotina_deploy.md)
e no [guia de ativação](../deploy/README.md#ativação-do-follow-up).
````

### Passo 34 — `callback/README.md`

**Ação:** Alterar. Documentar Admin, configuração exibida e contagem em Relatórios.

Conteúdo completo do arquivo:

````markdown
# Aplicativos Django: webhook e monitoramento

Projeto Django que reúne o webhook e o aplicativo de monitoramento por unidade.
O webhook recebe eventos da Meta, valida a entrada e persiste mensagens aceitas
na fila. O processamento da conversa pertence ao worker. O monitoramento oferece
login com autenticação Django, autorização por unidade, consulta responsiva de
conversas e indicadores, além da exportação de contatos.

Documentos centrais:

- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)
- [Portal do projeto](../README.md)

## Estrutura

```text
callback/
├── callback/              configuração Django
├── webhook/
│   ├── admin.py           operações administrativas
│   ├── models.py          mapeamento das tabelas
│   ├── urls.py            rota /webhook
│   ├── views.py           borda GET/POST
│   └── services/          fluxo HTTP e anti-flood
├── monitoramento/        aplicativo do painel por unidade
│   ├── __init__.py
│   ├── apps.py           registro MonitoramentoConfig
│   ├── forms.py          credenciais nativas e autorização antes do login
│   ├── views.py          login, saída, painel, APIs de leitura e CSV
│   ├── urls.py           rotas públicas e privadas do monitoramento
│   ├── monitoramento_guard.py  autorização da sessão e dos recursos
│   ├── periodos.py       janelas de consulta aceitas pelo servidor
│   ├── apresentacao.py   consolidação, perfis, botões e CSV Google/essencial
│   ├── services.py       orquestra leituras da unidade autorizada
│   ├── templates/monitoramento/  login, painel e acesso negado
│   └── static/monitoramento/     estilos, interação e logo ESL Tech
│       ├── css/
│       ├── js/
│       └── img/
└── manage.py
```

Arquivos principais de `services`:

- `post_flow.py`: validações e transação da fila;
- `meta_signature.py`: assinatura `X-Hub-Signature-256`;
- `bloqueio_meta_guard.py`: consulta da lista local de bloqueio, promoção de
  suspeita e nova tentativa de bloqueio na Meta;
- `flood_guard.py`: Redis, banco, memória e bloqueio Meta;
- `populating_fila_mensagens.py`: parse e inserção usando cursor recebido;
- `alerta_flood_memoria.py`: alerta local quando banco e Redis falham.

## Endpoint

```text
GET  /webhook
POST /webhook
```

A rota não possui barra final. O `GET` atende à verificação inicial da Meta. O
`POST` recebe eventos reais.

O `GET` devolve `hub.challenge` quando `hub.mode=subscribe` e
`hub.verify_token` coincide com `META_WEBHOOK_VERIFY_TOKEN`; nos demais casos,
devolve `Webhook ativo` com HTTP 200.

O limite do body é configurado por `WEBHOOK_MAX_BODY_BYTES` (padrão: 256 KiB).
Quando `META_WEBHOOK_SIGNATURE_REQUIRED=true`, o POST exige HMAC-SHA256 do body
original, calculado com `META_APP_SECRET` e comparado com
`X-Hub-Signature-256` por `hmac.compare_digest`. Secret vazio, header ausente ou
assinatura inválida resultam em 403. O padrão dessa flag no código é `False`;
a exigência efetiva depende da configuração do ambiente.

## Ordem do POST

```text
Content-Type
-> tamanho do body
-> assinatura Meta
-> parse JSON
-> classificação do evento Meta
-> lista local de bloqueio / suspeita de bot
-> anti-flood
-> unidade ativa
-> conversa bloqueada
-> preparação da mensagem
-> transação da fila
-> resposta HTTP
```

O webhook não envia etapas, não avança conversa e não executa dequeue.
O follow-up é disparado pelo worker próprio após consulta de inatividade; não
exige um evento recebido nem cria uma entrada fictícia na fila. A reação real
do cliente passa pelas mesmas barreiras de assinatura, bloqueio, flood e turno.

Eventos contendo apenas `statuses` retornam 200 sem processamento na V1.
Eventos sem `messages`/`statuses`, ou com ambos, também retornam 200 sem
enfileirar. Esses descartes ocorrem antes dos controles de bloqueio e flood.

## Contrato HTTP

| Cenário | HTTP | Resultado |
|---|---:|---|
| Mensagem inserida | 200 | `status=ok` |
| Descarte por regra de negócio | 200 | `status=ignored` ou `status=ok`, conforme o ponto do fluxo |
| JSON inválido | 200 | `status=ignored`, `reason=invalid_json` |
| Falha de conexão, inserção ou commit da fila | 503 | `status=unavailable`, `reason=insert_exception` |
| Falha ao confirmar a unidade no banco após cache sem resposta conclusiva | 503 | `status=unavailable`, `reason=unit_validation_unavailable` |
| Falha de Redis e banco ao validar bloqueio de conversa | 503 | `status=unavailable`, `reason=conversation_block_validation_unavailable` |
| Falha na consulta ou promoção da lista local de bloqueio | 503 | `status=unavailable`, `reason=blocklist_validation_unavailable` |
| Flood detectado sem conseguir consultar ou persistir o bloqueio local | 503 | `status=unavailable`, `reason=flood_<origem>_banco_indisponivel` ou `flood_<origem>_persistencia_local_falhou` |
| Erro inesperado identificável, nas três primeiras ocorrências por WAMID | 503 | `status=unavailable`, `reason=unexpected_error_retry`, com `attempt` |
| Erro inesperado com limite esgotado ou contador indisponível | 200 | `status=ignored`, `reason=unexpected_error_retry_exhausted` ou `unexpected_error_retry_unavailable` |
| Assinatura inválida | 403 | `status=forbidden` |
| Payload grande | 413 | `status=payload_too_large` |
| `Content-Type` inválido | 415 | `status=unsupported_media_type` |
| `Content-Length` inválido | 400 | `status=bad_request` |
| Método não permitido | 405 | `status=method_not_allowed` |

Turno ocupado, duplicidade, unidade inativa, conversa bloqueada e flood com
bloqueio local persistido são descartes com HTTP 200. Falhas operacionais de
validação ou persistência usam os motivos 503 acima. Em motivos de flood,
`<origem>` é `redis`, `banco` ou `memoria`.

O limite de três respostas 503 aplica-se somente ao tratamento genérico de
erro inesperado, com contador Redis por WAMID e TTL de sete dias renovado a cada
ocorrência. Sem WAMID ou sem Redis, esse tratamento retorna 200 com
`unexpected_error_retry_unavailable`; os demais cenários 503 não passam por
esse contador.

## Turno e duplicidade

O par lógico é:

```text
cliente_telefone + id_phone_unidade
```

`core/repositories/seguranca/turno_cliente.py` usa advisory lock transacional para impedir
corridas. Enquanto existir fila aberta sem resposta própria do bot, mensagens
posteriores do mesmo par são descartadas.

Mensagens com timestamp anterior a uma interação já registrada também são
descartadas como reentregas fora de ordem. Se todas as filas abertas já têm sua
própria resposta do bot com `status_envio=sent`, o turno pode ser liberado.

`id_hash_msg` é único. Reentregas da Meta não criam duas linhas; o insert utiliza
`ON CONFLICT DO NOTHING`.

## Anti-flood

A regra atual mede cada cliente dentro de cada unidade:

```text
15 WAMIDs distintos em 5 segundos
chave = wa_id_cliente + phone_id_unidade
```

Clientes diferentes da mesma unidade não compartilham contador. A ordem dos
fallbacks é Redis, banco e memória local. No Redis, deduplicação por WAMID e
incremento são atômicos, com janela fixa e deduplicação por duas horas.

O bloqueio utiliza `core/integrations/whatsapp/tools/usuarios.py`. O fluxo
persiste a intenção em `chatbot.cliente_bloqueado_meta` antes de chamar a Meta.
Se a Meta falhar, mantém o bloqueio local e descarta a mensagem com HTTP 200;
uma nova mensagem desse par tenta bloquear na Meta novamente. Se o banco
impedir a persistência, retorna 503 sem chamar a Meta. Unidade não cadastrada
é descartada sem bloqueio externo.

Antes do anti-flood, `bloqueio_meta_guard.py` verifica essa lista local e
também promove conversas que atingiram o limite de turnos sem avanço. A
promoção é confirmada no banco antes da chamada externa.

Relatórios e reconciliação manual ficam em
`utilitarios/monitoring/blocked_users.py`.

O relatório é somente leitura e possui duas conferências distintas:

- bloqueios: compara
  `(waba_id, phone_id_unidade, wa_id_cliente)` entre a lista da Meta e
  `chatbot.cliente_bloqueado_meta`;
- registros Cloud API: percorre o `waba_id` de cada unidade e compara os
  `phone_number_id` retornados pela Meta com `chatbot.unidade`.

Ele também separa falhas de coleta e vínculos divergentes; não bloqueia,
desbloqueia, registra ou remove dados automaticamente.

## Transações

`post_flow.py` é dono da conexão usada para enfileirar:

```text
abrir conexão -> povoando_fila -> commit/rollback -> close
```

`populating_fila_mensagens.py` recebe cursor e não controla conexão.

As transações independentes do anti-flood pertencem a `flood_guard.py`; a
consulta e promoção da lista local pertencem a `bloqueio_meta_guard.py`. Essa
separação está detalhada em
[Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md).

## Django Admin

O Admin é majoritariamente somente leitura. As exceções operacionais são:

- criação, edição e exclusão individual de unidade;
- criação, edição e exclusão de configuração de integração do Funil por unidade;
- desbloqueio individual de cliente bloqueado na Meta.

Cada unidade exige `nome_unidade`, `nome_agente` e `genero`. O campo `genero`
oferece no formulário somente `Masculino` e `Feminino`; ele controla o artigo
usado para apresentar o agente nos inícios padrão, de mídia, financeiro e de
tratamento de reforço escolar da etapa 1.

`waba_id` e `phone_number_id` ficam somente leitura após a criação. O Admin
também expõe `idade_minima_suporte` e `email_obrigatorio`. O seletor de suporte
aceita Desativado, 50+, 60+, 70+, 80+ e 90+; ativar exige um `numero_comercial`
brasileiro válido, inclusive ao editar ou remover o número de uma unidade ativa.
Somente o titular é alcançado; o limite não altera a dispensa de e-mail dos 60+.

No Admin, criação/exclusão de unidade e desbloqueio individual seguem
Meta-first. Se a Meta falhar, a alteração local correspondente não é
confirmada. Se a Meta concluir e uma etapa local posterior falhar, a operação
externa não é compensada automaticamente: a unidade exige conferência manual.
O desbloqueio também zera `turnos_sem_avanco` das conversas ativas do par.
Essa ordem administrativa é diferente do bloqueio preventivo do webhook,
que persiste primeiro a lista local.

## Cadastro e autorização do monitoramento

O modelo `Unidade`, com `managed = False`, inclui `id_usuario_monitoramento`,
um `OneToOneField` opcional para o usuário do Django. No Admin da unidade,
**Usuário de monitoramento** seleciona uma conta comum criada em **Usuários**.
Uma conta não pode ser vinculada a duas unidades; várias unidades podem ficar
sem conta. Excluir o usuário limpa o campo com `SET_NULL` e preserva a unidade.
O formulário permite contas inativas para preparar o cadastro, mas elas não
passam pela autorização. A edição mantém o fluxo administrativo existente da
unidade; o vínculo de acesso é consultado diretamente no banco, sem cache.
As regras completas estão em [Regras de negócio, 19.6](../REGRAS_DE_NEGOCIO.md#196-contas-de-monitoramento-por-unidade).

O aplicativo `monitoramento` está registrado por
`monitoramento.apps.MonitoramentoConfig` em `callback/settings.py`. As rotas são
incluídas no URLconf do projeto; `STATIC_URL=/static/` permite carregar os assets
também nas URLs aninhadas. O login não cria tabelas nem migrações adicionais.

`monitoramento/monitoramento_guard.py` oferece
`exigir_acesso_monitoramento(request, id_conversa=..., id_mensagem=...)`.
Somente `request.user.pk` identifica a conta. Os identificadores dos recursos
são opcionais, mas, quando fornecidos, são conferidos na mesma consulta que
valida o vínculo e a conta no banco. O retorno informa a unidade autorizada;
falhas de autorização geram `PermissionDenied`, sem distinguir recurso ausente
de recurso de outra unidade. Erros de banco propagam e não liberam acesso.

`forms.py` estende `AuthenticationForm`: o Django verifica o hash da senha do
username informado, depois `exigir_acesso_usuario_monitoramento` valida a conta
e seu vínculo antes de criar a sessão. Não há consulta própria de senhas.
Usuário inexistente e senha incorreta recebem o mesmo aviso, sem confirmar a
existência de contas. Contas inativas, administrativas ou sem unidade não entram.

- `GET /login/`: formulário responsivo com logo vetorial extraída do material
  da ESL Tech, sem dependências visuais externas.
- `POST /login/`: autenticação com CSRF, sessão Django e destino fixo. O
  parâmetro `next` não controla o redirecionamento. Falhas de banco retornam 503
  com aviso genérico; a senha não é reapresentada nem registrada pela view.
- `POST /sair/`: encerra a sessão com CSRF; GET não executa logout.
- `GET /`: entrega o painel privado e responsivo.
- `GET /dados/conversas/`: resumo e lista consolidada dos contatos.
- `GET /dados/conversas/<id_cliente>/`: histórico do contato dentro da unidade.
- `GET /dados/relatorio/`: indicadores, perfis, satisfação, atividade e etapas.
- `GET /contatos.csv`: exporta todos os contatos ou somente os elegíveis.
  Por padrão, o arquivo segue as 36 colunas, a grafia e a ordem do modelo oficial do Google
  Contacts para que e-mail, telefone, observações e marcador sejam reconhecidos.
  Com `formato=essencial`, entrega somente `Nome`, `E-mail` e `Telefone`, com
  telefone brasileiro sem o prefixo internacional `+55` (preservando o DDD),
  nome completo na primeira coluna, separador `;` e UTF-8 com BOM para planilhas
  em pt-BR. Os quatro downloads usam o mesmo período e escopo autorizado.

O login bem-sucedido retorna a `/`. A página e cada endpoint de dados chamam
`exigir_acesso_monitoramento`; nenhum deles aceita unidade escolhida em URL,
query string ou JavaScript. Depois do guard, cada SQL de
`core/repositories/monitoramento/painel.py` recebe e aplica o `id_unidade`
autorizado. O guard não modifica consultas posteriores nem concede acesso ao
Admin.

O navegador atualiza a seção de conversas a cada 10 segundos e a de relatórios
a cada 30 segundos, somente enquanto a página está visível. Voltar à aba força
uma nova leitura. Não há WebSocket nem tarefa periódica no servidor para o
painel: as requisições são atendidas pelo mesmo Gunicorn/Django do webhook.
Mensagens são carregadas somente quando um contato é aberto.

O follow-up confirmado aparece como mensagem de texto do bot na conversa e
participa da contagem de mensagens no período. Não há cartão exclusivo,
controle de disparo nem edição de stage no monitoramento. A lista mostra os
perfis junto da data: `DP -18`, `DP 18–59`, `DP 60+`, `18–59` e `60+`, conforme
os dados disponíveis; o cabeçalho da conversa mantém a descrição completa.

Conversas prioriza a lista e o histórico, sem repetir os quatro indicadores do
relatório. O layout compacto preserva as fontes e ajusta o espaço do chat pela
altura real do cabeçalho e do aviso, inclusive ao girar o celular. Em telas
estreitas, lista e conversa alternam com o botão de voltar. Os downloads
essenciais ficam logo abaixo dos downloads para Google Contatos em Relatórios.

O padrão é todo o histórico até o instante da requisição. Também existem os
períodos 24 horas, 7 e 30 dias, 2, 3 e 6 meses e 1 ano. Os períodos finitos são
comparados à janela imediatamente anterior de igual duração. A distribuição por
etapa representa o estado atual da conversa mais recente de cada contato com
atividade no período; não reconstrói a etapa histórica. Como o histórico
persiste texto e tipo, mas não o
payload original dos botões, o painel apresenta como referência os botões do
catálogo atual da etapa, sempre desabilitados.

O painel é somente leitura. Os filtros, a pesquisa, os seletores de período e os
downloads não alteram registros. As regras `idade_minima_suporte`, `email_obrigatorio`
e `bpa_ativo` vêm da unidade. O CSV completo preserva campos ausentes vazios; o
CSV elegível exige nome, e-mail estruturalmente válido e telefone em formato
internacional. Essa regra vale tanto para Google CSV quanto para CSV essencial;
nenhum dos formatos acrescenta etiquetas comerciais ou datas ao nome.

O card **Encaminhados ao comercial** fica somente em Relatórios, abaixo dos
quatro indicadores. Conta clientes distintos por unidade com encerramento
`encaminhado_suporte_idoso` no período (`finalizou_em`, intervalo semiaberto).
Inclui históricos, sem filtrar pela política atual, sem duplicar conversas e sem
misturar os casos 100+. Não comprova clique, atendimento humano ou matrícula.
Tags 18–59, 60+ e de dependentes continuam fixas. Quantidades e taxas do Funil
mantêm todos os envios registrados mesmo quando a configuração atual mudou.

Não há cadastro, recuperação/troca de senha nem bloqueio por número de tentativas
no portal. Contas e senhas continuam administradas pelo proprietário no Django
Admin. Senhas ficam sempre mascaradas no campo; os formulários usam o mecanismo
nativo de sessão e proteção CSRF. `falha_csrf` personaliza o aviso em português
somente nas rotas de monitoramento, preservando o tratamento padrão nas demais.
O HTTPS e os cookies seguros dependem das configurações de produção descritas
na [rotina de deploy](../regras_deploy/rotina_deploy.md).

`ALLOWED_HOSTS` aceita os domínios, mas não separa rotas por hostname; essa
separação não foi implementada. Os relatórios em `utilitarios` seguem manuais.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_monitoramento_unidade.py`;
- `tests/unit/test_monitoramento_login.py`;
- `tests/unit/test_monitoramento_painel.py`.

Esses arquivos cobrem o núcleo transacional; consulte também
[`tests/README.md`](../tests/README.md).
````

### Passo 35 — `utilitarios/README.md`

**Ação:** Alterar. Documentar as faixas fixas, os envios históricos e a nota de política nos relatórios manuais.

Conteúdo completo do arquivo:

````markdown
# Utilitários operacionais

Comandos manuais de monitoramento, diagnóstico e manutenção. Esta pasta não é
importada pelo webhook, pelo monitoramento, pelos workers nem pelo Django
Admin.

## Fronteira

```text
serviços de produção -> core/callback/workers
operador humano      -> utilitarios -> primitivas de core
```

Os módulos daqui podem consultar ou manter recursos de produção quando
executados conscientemente. Nenhum deles roda por import e nenhum serviço deve
depender de `utilitarios`.

## Estrutura

```text
utilitarios/
├── bootstrap.py
├── local_settings.py       configuração privada local, ignorada pelo Git
├── reports_functions/
│   ├── weekly.py            dashboards e PDFs dos últimos 7 dias
│   └── total.py             dashboards e PDFs desde o primeiro atendimento
├── requirements-monitoramento.txt
├── montar_lead_teste.py
├── verificar_followup.py    diagnóstico somente leitura, sem envio
├── cache_consulta.py
├── utlitys.py
├── pintregister.py
├── operacoes_rotineiras.sql
├── monitoring/
│   ├── blocked_users.py
│   ├── infrastructure.py
│   └── suspicious_conversations.py
├── maintenance/
│   ├── cache_reset.py
│   └── message_partitions.py
└── integrations/
    ├── funil_saj_teste.py
    ├── funil_rio_teste.py
    └── funil_andre_teste.py
```

A maioria das ferramentas usa o bootstrap para execução local no PyCharm;
o [diagnóstico de follow-up](#diagnóstico-de-follow-up) é uma exceção.
Nas ferramentas que usam esse bootstrap, o
`.env` da raiz é lido explicitamente e os ajustes privados de
`utilitarios/local_settings.py`, arquivo ignorado pelo Git, são aplicados por
cima dele. Assim, o SSL do PostgreSQL continua compatível com o Windows sem
misturar variáveis antigas herdadas do processo. Os comandos que aceitam
`--env-file` devem receber `/etc/chatbot/chatbot.env` quando forem executados na
VM; eles nunca dependem do arquivo privado local.

## Regra de pertencimento

Um arquivo pertence a `utilitarios/` quando é um comando iniciado
conscientemente por uma pessoa para diagnóstico, monitoramento, manutenção ou
probe. Nenhum ponto de entrada da aplicação — webhook, monitoramento,
`worker_flow`, `worker_funil`, `worker_followup` ou Django Admin — pode importar esta pasta.

Não pertencem a `utilitarios/`:

- primitivas reutilizadas pelos pontos de entrada, que ficam em `core`;
- instalação e DDL inicial, que ficam em `core/database/deploy_database`;
- migrações incrementais, que ficam em `deploy/migrations`;
- entrypoints do framework ou dos serviços, como `manage.py`, WSGI e workers;
- testes, mocks e fixtures de validação automatizada, que ficam em `tests`.

Todo módulo desta pasta deve ser seguro por import: importar define funções,
mas não conecta ao banco/Redis, não chama APIs, não imprime relatórios e não
altera dados. Operações mutantes exigem confirmação explícita.

Os relatórios principais podem ser executados diretamente pelo botão verde do
PyCharm. Os comandos `python -m` continuam disponíveis para filtros avançados.

No Windows, os módulos também podem ser executados diretamente pelo botão
**Run** do PyCharm. O caminho Linux configurado em `DB_SSLROOTCERT` é
automaticamente resolvido para o bundle público do RDS incluído em
`deploy/certificates`, mantendo `verify-full`.

## Monitoramento semanal e total por unidade

Os geradores de monitoramento criam, para cada unidade consultada, um dashboard
HTML de conversas e um relatório PDF de desempenho. O semanal cobre por padrão
os últimos 7 dias. O total cobre, de forma independente para cada unidade, o
intervalo entre a primeira mensagem recebida de cliente e o instante congelado
no começo da execução. Ambos usam exatamente a mesma estrutura visual, regras
de consolidação e métricas. Instale a dependência adicional uma vez:

```bash
python -m pip install -r utilitarios/requirements-monitoramento.txt
```

Depois execute:

```bash
python -m utilitarios.reports_functions.weekly
python -m utilitarios.reports_functions.total
```

Na VM, informe explicitamente o ambiente de produção:

```bash
python -m utilitarios.reports_functions.weekly \
  --env-file /etc/chatbot/chatbot.env
python -m utilitarios.reports_functions.total \
  --env-file /etc/chatbot/chatbot.env
```

As duas visões ficam isoladas dentro da pasta da unidade:

```text
monitoramento/
└── <unidade>/
    ├── semanal/
    │   ├── dashbord/
    │   │   └── conversas_<intervalo>.html
    │   └── relatorios/
    │       └── desempenho_<intervalo>.pdf
    └── total/
        ├── dashbord/
        │   └── conversas_<intervalo>.html
        └── relatorios/
            └── desempenho_<intervalo>.pdf
```

O nome comercial `Santo Antônio de Jesus` é publicado na pasta curta `SAJ`;
os demais nomes de unidade são preservados após a remoção do prefixo `Supera`.

A pasta `/monitoramento/` inteira é ignorada pelo Git. Os arquivos gerados
contêm dados pessoais e devem ser entregues somente aos responsáveis pela
respectiva unidade, sem publicação ou compartilhamento indiscriminado.

O dashboard apresenta como uma sequência as conversas técnicas pertencentes
exatamente ao mesmo par `(id_unidade, id_cliente)`. Conversas de unidades ou
clientes diferentes nunca são unificadas. O utilitário opera em modo somente
leitura: consulta o PostgreSQL e grava apenas os artefatos locais de saída, sem
alterar o banco, o Redis ou enviar mensagens e integrações externas.

O instante final do relatório total é resolvido uma única vez e compartilhado
por todas as unidades da execução. Cada unidade, porém, conserva seu próprio
início. Se uma unidade ainda não tiver mensagem recebida de cliente, ela também
recebe um relatório vazio, sem buscar ou misturar dados de outra unidade.

Flags principais:

- `--dias N`: altera a janela semanal, cujo padrão é 7 dias (somente `weekly`);
- `--ate ISO-8601`: fixa o fim da janela;
- `--id-unidade ID`: limita a uma unidade e pode ser repetida;
- `--saida CAMINHO`: troca a raiz `monitoramento`;
- `--max-mensagens N`: limita o volume consultado;
- `--statement-timeout-ms N`: ajusta o timeout das consultas;
- `--env-file CAMINHO`: escolhe explicitamente o arquivo de ambiente.

O PDF depende do ReportLab; o HTML é autocontido e pode ser aberto offline no
navegador.

### Perfis de atendimento nos PDFs

Os PDFs semanal e total compartilham os mesmos indicadores por perfil:

- dependentes de 4 a 17 anos com BPA ativo, ou de 5 a 17 sem BPA;
- dependentes de 18 a 59 anos e dependentes com 60 anos ou mais;
- titulares de 18 a 59 anos e titulares com 60 anos ou mais.

Cada faixa mostra clientes únicos, conversas, leads enviados ao funil e taxa de
envio. A idade usada é a da pessoa atendida: `cliente.idade` no atendimento
próprio; `dependente.idade` ligado à mesma conversa e cliente no atendimento
para dependente. Dados ausentes, inválidos ou fora dessas faixas ficam em
contadores explícitos de não classificados. Não há dupla contagem aos 18/60
anos. Um cliente pode representar pessoas de perfis diferentes; por isso, não
se somam as linhas para obter o total geral de leads.

O funil usa somente `funil_envios.status = 'sent'`, com `enviado_em` no período,
para clientes que entraram em contato na janela, atribuindo cada envio à sua
própria conversa. Um retry confirmado de conversa sem mensagens na janela
também entra nos perfis, mas não acrescenta mensagens antigas ao HTML. O envio
não equivale a agendamento, venda ou posição atual no CRM.

O snapshot carrega `idade_minima_suporte` como inteiro ou NULL e mostra a política
atual em uma nota. As cinco faixas etárias continuam fixas; suas quantidades e
taxas incluem os envios ao Funil registrados, sem esconder uma faixa inteira
pelo limite da unidade. As idades e configurações são as disponíveis na extração,
sem inventar histórico de alterações. O total reutiliza a implementação semanal.
O novo card de encaminhamentos pertence ao painel web; não é acrescentado ao PDF.
Os quatro CSVs mantêm formatos, telefones e elegibilidade anteriores.

O PDF inclui cobertura de classificação, participação na satisfação,
distribuição das notas, comentários com profissão e relação nominal dos leads.
Os HTMLs de conversas continuam separados e com a mesma finalidade anterior.

## Consultas Meta e alerta sobre alteração do PIN

As consultas abaixo usam `utilitarios/local_settings.py` no Windows. Na VM,
acrescente `--env-file /etc/chatbot/chatbot.env`:

```bash
python -m utilitarios.cache_consulta --limite 200
python -m utilitarios.utlitys --phone-number-id PHONE_ID
```

Os identificadores são mascarados nas consultas por padrão.

> **Não execute `utilitarios.pintregister` pela linha de comando, nem com
> `--help`.** O bloco `__main__` atual substitui os argumentos recebidos por um
> alvo e uma confirmação fixos e realiza imediatamente o POST mutante na Meta.
> Enquanto esse entrypoint não for corrigido em uma tarefa de código própria,
> ele não é uma ferramenta CLI segura. Importar o módulo não realiza o POST.

## Bloqueios Meta × banco

Lista cada unidade com seu WABA e `phone_id`, consulta os bloqueados da Meta e
compara com `chatbot.cliente_bloqueado_meta`:

```bash
python -m utilitarios.monitoring.blocked_users blocked-users --show-wa-id
```

Também é possível apenas abrir `blocked_users.py` e clicar em **Run**. Sem
parâmetros, ele executa esse mesmo relatório e mostra os WA IDs completos.

Ao executar `blocked_users.py` diretamente no PyCharm sem parâmetros, esse é o
relatório escolhido por padrão.

O resultado separa:

- sincronizados no banco e na Meta;
- somente na Meta;
- somente no banco, ainda pendentes de confirmação na Meta;
- registros não comparados porque a Meta falhou naquela unidade;
- vínculo local divergente entre unidade e `phone_id`.

Uma falha em uma unidade não transforma sua lista Meta em lista vazia e não
interrompe as outras. A chave da comparação é
`(waba_id, phone_id_unidade, wa_id_cliente)`.

Para conferir os registros Cloud API dos números:

```bash
python -m utilitarios.monitoring.blocked_users phone-registrations
```

Esse segundo relatório percorre todas as WABAs conhecidas pelo banco e detecta
inclusive um mesmo `phone_id` associado a WABAs diferentes. Ele não descobre
uma WABA inteira que ainda não esteja cadastrada localmente.

Os comandos são somente leitura. Código de saída `0` significa sincronizado,
`1` indica divergência e `2` indica falha de coleta.

## Diagnóstico de follow-up

`verificar_followup.py` usa o ambiente carregado por `core.config_env`;
não usa `bootstrap.py`, `local_settings.py` nem aceita `--env-file`.
Com as variáveis do banco de teste já configuradas, execute da raiz:

```bash
python -m utilitarios.verificar_followup
```

Na VM, carregue o ambiente dos serviços:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python -m utilitarios.verificar_followup'
```

O comando usa uma transação somente leitura. Confere a existência das três
tabelas, conta stages positivos/negativos/maiores que um, marcações do legado e
datas futuras em `last_interaction_at`, e lista até dez candidatas por ID de
conversa, unidade e etapa. Não envia mensagens nem adquire lock de processamento.

`FOLLOWUP_CONSULTA_OK_SEM_ENVIO` confirma a consulta. Stage negativo ou data futura
encerra com `REVISAR_ANOMALIAS_ANTES_DE_ATIVAR`; ausência das tabelas falha com
`SCHEMA_FOLLOWUP_AUSENTE`. Stage maior que um aparece para revisão, mas é aceito
pela retomada. Amostra vazia é válida e não significa falha do serviço.
`ciclos_aguardando_reacao` inclui o legado marcado e não mede lembretes enviados.

## Conversas suspeitas

```bash
python -m utilitarios.monitoring.suspicious_conversations \
  --id-unidade 1 --ultimas-horas 24 --formato texto
```

Use `--todas-unidades` para ampliar o escopo. WA IDs e textos sensíveis
permanecem mascarados por padrão.

## Infraestrutura remota

```bash
python -m utilitarios.monitoring.infrastructure
```

Confirma acesso ao PostgreSQL e ao Redis e recusa um destino local.

## Cache

```bash
python -m utilitarios.maintenance.cache_reset --operacional --confirmar
python -m utilitarios.maintenance.cache_reset --bloqueios --confirmar
python -m utilitarios.maintenance.cache_reset --unidades --confirmar
```

Todas as operações validam que o Redis é remoto e exigem `--confirmar`. A
remoção por `SCAN` e `DELETE` é uma manutenção *best effort*, não uma transação
atômica; no deploy, execute-a com webhook e workers parados, como determina o
runbook, para não concorrer com a criação de novas chaves.

Na VM, acrescente `--env-file /etc/chatbot/chatbot.env`. Sem `--env-file`, o
comando usa `utilitarios/local_settings.py`, preservando a execução local pelo
PyCharm.

## Partições do histórico

```bash
python -m utilitarios.maintenance.message_partitions \
  --months-ahead 3 --confirm
```

O comando executa DDL idempotente e retorna erro após rollback se alguma
partição não puder ser criada.

## Sondas do Funil

SAJ:

```bash
python -m utilitarios.integrations.funil_saj_teste catalog
python -m utilitarios.integrations.funil_saj_teste payload
python -m utilitarios.integrations.funil_saj_teste send-test --confirm-real-send
```

Rio Vermelho:

```bash
python -m utilitarios.integrations.funil_rio_teste payload
python -m utilitarios.integrations.funil_rio_teste \
  send-test --confirm-real-send
```

Santo André - Jardim Bela Vista:

```bash
python -m utilitarios.integrations.funil_andre_teste
python -m utilitarios.integrations.funil_andre_teste payload
python -m utilitarios.integrations.funil_andre_teste \
  send-test --confirm-real-send
```

Em cada bloco, somente `send-test` envia uma oportunidade real, e isso exige a
flag de confirmação. Em Santo André, executar o arquivo ou módulo sem argumentos
é o atalho intencional para esse mesmo envio confirmado, permitindo usar
diretamente o botão **Run** do PyCharm. Cada sonda usa um lead fictício
identificado para sua própria unidade. Como Santo André ainda não existe no
banco, seu snapshot usa `id_unidade=-1` apenas para satisfazer o contrato
interno; esse campo não é incluído no payload da ApiCarrossel. Importar os
módulos nunca realiza uma requisição externa.

## Ideia futura: rotação automática do PIN

O desenho preliminar para atualizar periodicamente o PIN na Meta e no banco
está registrado em [`PIN_AUTOMATICO_FUTURO.md`](PIN_AUTOMATICO_FUTURO.md). Ele
é apenas uma proposta para uma versão futura; nenhuma automação foi ativada.
````

### Passo 36 — `tests/README.md`

**Ação:** Alterar. Documentar os novos cenários e a exigência explícita de PostgreSQL descartável.

Conteúdo completo do arquivo:

````markdown
# Testes do projeto

Esta pasta reúne testes unitários, de contrato e de integração SQL. Além do núcleo
transacional, ela cobre regras e utilitários já implementados:

- cenário completo de turno A/B/C;
- retry, requeue, ordem da fila e fencing por `lock_version`;
- persistência idempotente, avanço e não avanço de etapa;
- checkpoints, commits, rollback e conclusão da fila no worker;
- suporte ao idoso e obrigatoriedade do e-mail;
- validação da oferta, início da triagem, profissão e saudação após inatividade;
- montagem dos relatórios semanais e totais;
- payloads e sondas manuais do Funil;
- vínculo 1:1 opcional de monitoramento e autorização de conversas/mensagens por unidade;
- login nativo, par username/senha, sessão, CSRF e revogação do acesso ao portal;
- painel somente leitura, períodos, consultas por unidade, botões históricos,
  indicadores, Google CSV e CSV essencial sem o prefixo brasileiro `+55`;
- follow-up proativo, retomada reativa, elegibilidade, migração e locks entre workers.

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
tests/unit/test_followup.py
tests/integration/test_followup_postgres.py
```

Por padrão, os testes usam fakes e mocks para fronteiras externas, sem chamar
Meta, Funil, Redis ou RDS. A integração com PostgreSQL local só executa quando
`FOLLOWUP_TEST_DSN` é fornecida explicitamente. Um utilitário manual não deve
ser executado como forma de testar sua importação.

Testes unitários pertencem a `tests/unit/`; contratos com PostgreSQL real ficam
em `tests/integration/` e exigem ambiente descartável explícito. Dados e classes
auxiliares exclusivos de teste ficam em `tests/`, nunca nos módulos de produção.
Sem `FOLLOWUP_TEST_DSN`, a descoberta pula a integração PostgreSQL.

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
O teste distingue a remoção de `+55` no essencial da preservação do telefone
internacional no Google CSV; não remove o DDD nem altera os dados de origem.

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
O retorno completo também usa fila e histórico reais nesse banco descartável:
rollback preserva stage positivo, a confirmação mantém a etapa e os contadores,
e recuperar a mesma reação não reseta um ciclo posterior. Cobre tanto o lembrete
confirmado quanto o legado sem data de envio.
Meta permanece simulada; a confirmação de entrega real exige homologação manual.

## Suporte por idade

`unit/test_suporte_por_idade.py` cobre as seis configurações, fronteiras,
Admin, contato comercial, mensagem, recuperação com limite atual e contagem
real em SQLite dos encaminhamentos por unidade, data e motivo. As suítes de
e-mail, turno, follow-up, CSV e relatórios continuam como regressão.

`integration/test_suporte_por_idade_postgres.py` executa migração, domínio,
recusa de reaplicação, falha com rollback e DDL de instalação limpa. Exige
`SUPORTE_IDADE_TEST_DSN`, host loopback e banco vazio `test_chatbot_suporte_idade`.
Recusa schema chatbot preexistente; não usa DB_HOST/DB_NAME. Sem a variável, é
pulado. Ver o [procedimento](../deploy/idade_minima_suporte.md) para homologação.
````

### Passo 37 — `deploy/README.md`

**Ação:** Alterar. Vincular a entrega ao procedimento coordenado e aos SQLs de avanço e reversão.

Conteúdo completo do arquivo:

````markdown
# Implantacao no Lightsail

Os arquivos assumem a aplicacao em `/opt/chatbot/app`, o ambiente virtual em
`/opt/chatbot/venv` e as variaveis em `/etc/chatbot/chatbot.env`. Os quatro
processos da aplicacao sao independentes e escrevem seus logs no journald. O
portal de monitoramento faz parte do processo web `chatbot-webhook`; ele não
cria outro serviço. O quarto serviço é `chatbot-worker-followup`, implantado na
V1.2.0. Este guia também cobre a preparação de uma instalação nova.

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

O follow-up é instalado junto das demais units, mas deve ser iniciado somente
após o banco e o flow compatível estarem validados. Conclua a seção
[Ativação do follow-up](#ativação-do-follow-up) para habilitá-lo.

```bash
systemctl status chatbot-webhook chatbot-worker-flow chatbot-worker-funil chatbot-worker-followup
journalctl -u chatbot-webhook -u chatbot-worker-flow -u chatbot-worker-funil -u chatbot-worker-followup -f
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

Na atualização dos workers ou de seus módulos compartilhados, pare o follow-up
antes do flow; retome o flow compatível e validado antes de reativar os lembretes.
Pare também o Funil quando ele for afetado. Alterações exclusivas do painel
podem manter os workers ativos. O webhook continua recebendo e enfileirando
quando o schema permite; para carregar Python/templates novos, recebe `HUP`,
pois Gunicorn não possui auto-reload. Alteração de `.env` ou da unit exige `restart` e segue
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
As colunas `followup_stage`/`followup_last_sent_at` já existentes não são recriadas. Com o flow
parado e o follow-up desligado, a migração registra em followup_legado todas as
conversas ativas e marca followup_stage = 1, inclusive nas etapas 18–21. O horário
`followup_last_sent_at`, o histórico, a etapa e a finalização permanecem como estavam.
O script é único e transacional; não reaplicar nos próximos deploys. O setup limpo
cria as três tabelas e não marca conversas. A marcação não comprova envio de mensagem.
Conversa ativa terminal/inconsistente recusa toda a migração: concluir a recuperação
pendente do flow e revisar a anomalia antes de tentar de novo, sem encerrar em massa.

Na produção, essa migração já foi aplicada em 10/09/2026 na V1.2.0, com 106
conversas marcadas naquela execução. Não repetir nem manter esse número como
expectativa fixa: os clientes podem retomar normalmente após o deploy.

Instalar `systemd/chatbot-worker-followup.service` e executar daemon-reload não
inicia envios. A unit habilita FOLLOWUP_WORKER_ENABLED; se essa chave já existir no
EnvironmentFile, conferir a precedência antes da ativação. Nenhum segredo novo é necessário.
Antes da primeira ativação, executar o diagnóstico abaixo e conferir permissões
da role da aplicação nas novas tabelas. Reiniciar primeiro
`chatbot-worker-flow.service` e conferir estado/logs. Somente então:

```bash
sudo systemctl enable --now chatbot-worker-followup.service
sudo journalctl -u chatbot-worker-followup.service --since "5 minutes ago" -n 80 --no-pager
```

`python -m utilitarios.verificar_followup` faz leitura e mostra IDs de uma amostra.
Não é uma execução do worker e não envia mensagens. Um resultado vazio é válido.
O [README dos utilitários](../utilitarios/README.md#diagnóstico-de-follow-up)
traz o comando com o ambiente da VM e explica cada indicador. A sequência completa
de atualização fica em [rotina_deploy.md](../regras_deploy/rotina_deploy.md).

Para interromper os lembretes, parar e desabilitar a unit de follow-up. Isso mantém
o flow apto a tratar retornos de lembretes ou do legado marcado. Não apagar recibos, resetar
stages em massa nem reverter o flow incompatível enquanto existirem ciclos positivos.

## Suporte por idade mínima

O [procedimento de suporte por idade](idade_minima_suporte.md) coordena schema,
código, estáticos e serviços. A migração incremental está em
`migrations/20260911_idade_minima_suporte.sql`; a reversão restrita a NULL/60 está
em `rollback/20260911_idade_minima_suporte.sql`. Não executar em instalações
novas, não reaplicar a migração de follow-up e não editar a migração histórica
que criou a coluna booleana. Os comandos só pertencem à implantação aprovada.
````

## Parte 6 — procedimento de homologação e publicação

### Passo 38 — `deploy/idade_minima_suporte.md`

**Ação:** Criar. Registrar os comandos e o momento exato de executar o SQL, as conferências e os limites do retorno de versão.

Conteúdo completo do arquivo:

````markdown
# Publicação do suporte por idade mínima

Este procedimento pertence à entrega que substitui `unidade.suporte_idoso` por
`idade_minima_suporte`. Código, SQL, Admin e painel devem ser publicados juntos.
O modelo Django é `managed=False`; `manage.py migrate` não converte essa coluna.
Não há nova configuração de `.env`, serviço ou alteração dos ciclos do follow-up.

## Homologação antes de produção

1. Materializar todos os arquivos da entrega e revisar o diff. Preservar a etapa
   10, as tags fixas, os quatro CSVs e as proteções transacionais do flow.
2. Executar a suíte unitária na raiz, com as dependências do projeto:

```powershell
python -B -m unittest discover -s tests -t . -p "test_*.py"
```

3. Criar um banco PostgreSQL local vazio chamado `test_chatbot_suporte_idade`,
   exclusivo de testes. `SUPORTE_IDADE_TEST_DSN` deve indicar esse banco com host
   loopback e credenciais locais. Nunca usar a conexão de produção do DBeaver
   nessa variável. Com ela configurada, executar:

```powershell
python -B -m unittest tests.integration.test_suporte_por_idade_postgres
```

O teste cria e remove somente seu próprio schema `chatbot`, recusa um schema
preexistente, aplica o SQL integral, verifica conversão, defaults, domínio,
reaplicação, schema parcial e rollback. Sem a variável, o teste é pulado;
um resultado pulado não comprova que a migração foi homologada.

4. Confirmar os senders com Meta simulada e homologar manualmente o CTA em uma
   unidade de teste, sem usar leads reais. O botão continua abrindo o WhatsApp
   comercial e a mensagem usa a faixa configurada.
5. Conferir Admin e relatórios em computador e celular, em retrato e paisagem.
   Trocar períodos, conferir zero real, erro de consulta e histórico de suporte.
6. Registrar o commit aprovado e um backup recuperável do banco de produção.
   O SQL não é um mecanismo de backup. Garantir que o backup pode ser restaurado
   antes da janela de manutenção.

## Janela de manutenção

Antes de iniciar, interromper execuções manuais de relatórios e edições no Admin.
Guardar o commit anterior retornado abaixo para eventual retorno:

```bash
cd /opt/chatbot/app
git status --short
git rev-parse HEAD
```

A árvore precisa estar limpa. Conferir que a branch e o commit remoto correspondem
à entrega revisada. Os comandos abaixo usam a branch de produção atual do projeto:

```bash
git fetch origin
git checkout prod
```

Parar primeiro o follow-up e depois os demais consumidores. A indisponibilidade
do webhook é parte desta manutenção; não manter processos antigos lendo a coluna
removida e não iniciar o código novo antes da migração.

```bash
sudo systemctl stop chatbot-worker-followup.service
sudo systemctl stop chatbot-worker-flow.service chatbot-worker-funil.service chatbot-webhook.service
systemctl is-active chatbot-worker-followup.service chatbot-worker-flow.service chatbot-worker-funil.service chatbot-webhook.service
```

Só continuar quando todos estiverem `inactive`:

```bash
git pull --ff-only origin prod
git rev-parse HEAD
```

Conferir o hash aprovado. Não executar `setup_database.py` e não reaplicar a
migração do follow-up ou os scripts antigos de criação das flags.

## Momento de executar o SQL no DBeaver

**Executar agora o conteúdo integral de
`deploy/migrations/20260911_idade_minima_suporte.sql`, de BEGIN a COMMIT, na
conexão de produção correta.** Usar a execução do script completo, não apenas
a instrução sob o cursor. O arquivo contém as pré-condições e pós-condições.

O resultado deve preservar a quantidade de unidades: habilitadas antes viram
60 e desativadas antes viram NULL. Nenhuma conversa ou stage é alterado.
Após sucesso e COMMIT, conferir em nova consulta:

```sql
SELECT idade_minima_suporte, COUNT(*) AS unidades
FROM chatbot.unidade
GROUP BY idade_minima_suporte
ORDER BY idade_minima_suporte NULLS FIRST;

SELECT column_name, data_type, is_nullable, column_default
FROM information_schema.columns
WHERE table_schema = 'chatbot' AND table_name = 'unidade'
  AND column_name IN ('suporte_idoso', 'idade_minima_suporte');
```

Se houver erro, executar `ROLLBACK` na mesma sessão e manter os serviços parados
até identificar o estado do banco. Não ignorar uma exceção nem executar trechos
soltos para contornar as pré-condições.

## Validação e retomada

Na VM, carregar o ambiente sem imprimir segredos e verificar o Django:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'
```

Revisar o resultado; warnings já conhecidos não devem esconder erros novos.
Publicar o CSS/JS com a referência de cache atualizada pelo template:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
sudo systemctl start chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service
systemctl is-active chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service
sudo journalctl -u chatbot-worker-flow.service -u chatbot-webhook.service --since "5 minutes ago" -n 80 --no-pager
```

Confirmar que o flow compatível está funcionando e sem erros de coluna/contexto.
Somente então retomar o follow-up já instalado:

```bash
sudo systemctl start chatbot-worker-followup.service
sudo systemctl show chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service chatbot-worker-followup.service -p Id -p ActiveState -p SubState -p NRestarts --no-pager
curl --fail --silent --show-error --output /dev/null --write-out '%{http_code}\n' https://monitoramento.3esltech.com/login/
```

No navegador, validar o seletor do Admin, os quatro downloads, tags fixas e o
card de encaminhamentos em todos os períodos. Conferir logs e relatórios manuais.
Manter as unidades em NULL/60 até concluir essa conferência; a escolha de outras
faixas é uma edição posterior e deliberada do proprietário.

## Retorno de versão

Parar os quatro consumidores e suspender relatórios/edições como na manutenção.
Um `git checkout` isolado não restaura compatibilidade com a coluna antiga.

- Se a migração falhou e houve rollback, confirmar a presença de `suporte_idoso`
  booleano antes de retornar ao commit anterior.
- Se a migração foi confirmada e todas as unidades ainda estão em NULL/60,
  executar integralmente `deploy/rollback/20260911_idade_minima_suporte.sql` no
  DBeaver. Ele converte NULL para FALSE e 60 para TRUE e preserva os demais dados.
- Havendo 50/70/80/90, a reversão é recusada. Decidir entre corrigir a nova versão
  ou restaurar uma configuração anterior validada com o responsável. Não
  transformar todos os limites em TRUE e não apagar históricos de atendimento.

Após o schema voltar ao booleano, selecionar o **hash anterior que foi registrado**,
republicar os estáticos dessa versão, executar o check e retomar os serviços.
Não usar `reset --hard` para descartar mudanças locais ou reescrever histórico Git.
Uma restauração integral de backup exige avaliar também as mensagens recebidas
desde o backup; não é substituída automaticamente pelo SQL de reversão.
````

## Critério para encerrar a implementação

A entrega está pronta quando os 38 arquivos estiverem aplicados e revisados,
a suíte e a homologação PostgreSQL passarem, o Admin aceitar somente as seis
opções, o painel conservar as tags/CSV e a publicação coordenada estiver preparada.
O conteúdo dos passos é uma proposta completa e verificável, não uma confirmação
de que a migração ou o deploy já ocorreram.
