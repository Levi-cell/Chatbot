# Modificando `.env` e banco em produção

Este runbook cobre mudanças excepcionais de configuração e schema. Ele não
substitui a [rotina comum de deploy](rotina_deploy.md).

## Regras obrigatórias

- PostgreSQL é a fonte persistida da verdade para os dados de negócio.
- Redis é cache, fallback operacional ou proteção temporária conforme o domínio;
  ele não substitui o PostgreSQL como registro definitivo.
- O `.env` de produção nunca entra no Git e nunca deve ser exibido inteiro em
  log, print, screenshot, documentação ou conversa.
- Toda mudança de schema deve aparecer no DDL Python como **estado final de
  criação**, sem histórico de correções.
- O banco RDS já existente recebe um `ALTER` incremental separado, revisado e
  executado no DBeaver.
- O `ALTER` aplicado no DBeaver não deve ser copiado para
  `core/database/deploy/bank_script.py` como migração histórica.
- `INSERT`, `UPDATE`, `DELETE` ou `TRUNCATE` manual de dados de negócio em
  produção continua proibido, exceto no reset operacional explicitamente
  autorizado e documentado na Parte C. O uso comum do DBeaver descrito aqui é
  para DDL de schema controlado.

## Como interpretar a fonte de verdade e a autocura do cache

O projeto afirma isso explicitamente em `REGRAS_DE_NEGOCIO.md`,
`PADROES_DE_ARQUITETURA.md` e `core/cache/README.md`: PostgreSQL é a fonte
persistida da verdade; Redis acelera decisões e consultas.

O contrato não exige consultar banco e Redis em toda leitura, e o tratamento de
miss é específico de cada domínio:

- cache miss, valor inválido ou indisponibilidade do Redis usa o fallback de
  banco previsto para aquele domínio;
- um ID de cliente stale que causar violação de FK é removido, e o retry seguinte
  volta ao banco;
- o cache de unidades usa versão persistida em `chatbot.cache_controle` e recarrega
  quando detecta divergência;
- no webhook, a ausência da chave de bloqueio não consulta imediatamente o banco;
  se necessário, o worker classifica a conversa pelo PostgreSQL e registra a
  chave com o TTL restante. Uma falha do Redis no webhook usa o fallback de banco;
- a autocura cobre divergências **detectáveis**. O sistema não compara os dois
  lados em toda leitura para tentar suportar edição manual arbitrária.

Existem estados operacionais temporários cuja primeira avaliação é o Redis. O
principal exemplo é a janela curta de flood; PostgreSQL e memória são fallbacks.
Isso não transforma o Redis em fonte persistente dos dados de cliente, conversa,
etapa ou histórico. É um contador efêmero de proteção da entrada.

Portanto, a interpretação correta é: um cache hit válido pode permitir continuar
sem consultar o banco naquela linha do fluxo, mas o registro definitivo continua
no PostgreSQL. Se uma inconsistência só puder ser descoberta mais tarde, a
autocura ocorre no tratamento conhecido e a mensagem volta pelo retry.

## Parte A — atualizar o `.env` sem usar Nano

### 1. Preparar o conteúdo fora da VM

Use um arquivo local privado, por exemplo `.env.prod`, que já é ignorado pelo
Git. Tome `.env.example` como catálogo de chaves, mas mantenha os valores reais
específicos de produção. Não copie cegamente o `.env` de desenvolvimento.

Antes de copiar, confira especialmente:

```text
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,18.229.43.133,webhook.3esltech.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://webhook.3esltech.com
DJANGO_TRUST_X_FORWARDED_PROTO=True
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DB_SSLMODE=verify-full
DB_SSLROOTCERT=/etc/ssl/certs/aws-rds-global-bundle.pem
PGSSLCERTMODE=disable
REDIS_HOST=127.0.0.1
FUNIL_WORKER_ENABLED=True
```

Os demais tokens, IDs, senhas e endpoints devem conter os valores reais do
ambiente, sem serem enviados ao GitHub.

### 2. Criar backup e arquivo temporário na Lightsail

Os serviços podem continuar executando enquanto o novo arquivo é preparado:

```bash
sudo cp -a \
  /etc/chatbot/chatbot.env \
  /etc/chatbot/chatbot.env.rollback

sudo install -o root -g chatbot -m 0640 \
  /dev/null \
  /etc/chatbot/chatbot.env.new
```

O backup `.rollback` representa a última configuração conhecida como boa.

### 3. Colar o arquivo completo sem Nano

Inicie a captura no terminal Ubuntu:

```bash
sudo tee /etc/chatbot/chatbot.env.new > /dev/null
```

Depois:

1. cole **somente** o conteúdo completo do novo `.env`;
2. garanta que a última linha terminou com Enter;
3. pressione `Ctrl+D` para encerrar e salvar.

No terminal, `Ctrl+C` cancela o comando; ele não salva. Se cancelar ou colar
conteúdo incompleto, descarte apenas o temporário e repita:

```bash
sudo rm -f /etc/chatbot/chatbot.env.new
sudo install -o root -g chatbot -m 0640 /dev/null /etc/chatbot/chatbot.env.new
sudo tee /etc/chatbot/chatbot.env.new > /dev/null
```

No terminal do navegador, use o botão **Paste into terminal** ou o atalho de
colar aceito pelo navegador. Não execute o conteúdo do `.env` como comandos do
shell; ele deve ser colado somente enquanto `tee` estiver aguardando entrada.

### 4. Normalizar e conferir sem revelar valores

```bash
sudo sed -i 's/\r$//' /etc/chatbot/chatbot.env.new
sudo chown root:chatbot /etc/chatbot/chatbot.env.new
sudo chmod 0640 /etc/chatbot/chatbot.env.new
sudo stat -c '%a %U %G %n' /etc/chatbot/chatbot.env.new
```

O resultado esperado é:

```text
640 root chatbot /etc/chatbot/chatbot.env.new
```

Liste somente os nomes das chaves e procure duplicatas, sem imprimir segredos:

```bash
sudo awk -F= \
  '/^[A-Za-z_][A-Za-z0-9_]*=/{print NR ":" $1}' \
  /etc/chatbot/chatbot.env.new

sudo awk -F= \
  '/^[A-Za-z_][A-Za-z0-9_]*=/{print $1}' \
  /etc/chatbot/chatbot.env.new | sort | uniq -d
```

O segundo comando não deve produzir saída.

Valide a presença das configurações essenciais:

```bash
sudo -u chatbot /opt/chatbot/venv/bin/python -c "from dotenv import dotenv_values; c=dotenv_values('/etc/chatbot/chatbot.env.new'); required=('DJANGO_SECRET_KEY','DJANGO_ALLOWED_HOSTS','DJANGO_CSRF_TRUSTED_ORIGINS','DB_HOST','DB_NAME','DB_USER','DB_PASSWORD','DB_SSLMODE','DB_SSLROOTCERT','PGSSLCERTMODE','REDIS_HOST','META_ACCESS_TOKEN','META_WEBHOOK_VERIFY_TOKEN','META_APP_SECRET','META_WABA_ID','META_PHONE_NUMBER_ID_DEV','FUNIL_WORKER_ENABLED'); missing=[k for k in required if not c.get(k)]; print('AMBIENTE_OK' if not missing else 'FALTANDO: '+','.join(missing)); raise SystemExit(bool(missing))"
```

O comando deve imprimir `AMBIENTE_OK`.

### 5. Testar o arquivo temporário contra Django, RDS e Redis

Este teste injeta o arquivo `.new` apenas no processo de validação. Ele ainda
não altera os serviços ativos:

```bash
sudo -u chatbot env \
  PYTHONPATH=/opt/chatbot/app \
  /opt/chatbot/venv/bin/python -c "import os,sys; sys.path.insert(0,'/opt/chatbot/app/callback'); from dotenv import dotenv_values; os.environ.update({k:v for k,v in dotenv_values('/etc/chatbot/chatbot.env.new').items() if v is not None}); from core.database.connection_aws import get_conn; from core.cache.redis_client import confirmar_conexao_redis; conn=get_conn('env_preflight'); assert conn.execute('SELECT 1').fetchone()[0] == 1; conn.close(); assert confirmar_conexao_redis(); os.environ.setdefault('DJANGO_SETTINGS_MODULE','callback.settings'); import django; django.setup(); from django.core.management import call_command; call_command('check', deploy=True); print('PREFLIGHT_ENV_RDS_REDIS_OK')"
```

Não instale o arquivo se esse preflight terminar com erro.

### 6. Aplicar o novo ambiente

Uma alteração de `EnvironmentFile` não é carregada por `HUP`: o processo
principal do Gunicorn mantém o ambiente antigo. Por isso, nessa operação há um
`restart` curto do webhook.

```bash
sudo systemctl stop chatbot-worker-flow.service chatbot-worker-funil.service

sudo install -o root -g chatbot -m 0640 \
  /etc/chatbot/chatbot.env.new \
  /etc/chatbot/chatbot.env

sudo systemctl restart chatbot-webhook.service

systemctl is-active chatbot-webhook.service
curl --fail --silent --show-error https://webhook.3esltech.com/webhook

sudo systemctl start chatbot-worker-flow.service chatbot-worker-funil.service

systemctl is-active \
  chatbot-webhook.service \
  chatbot-worker-flow.service \
  chatbot-worker-funil.service
```

Depois, confirme os journals:

```bash
sudo journalctl -u chatbot-webhook.service \
  -u chatbot-worker-flow.service \
  -u chatbot-worker-funil.service \
  --since "5 minutes ago" --no-pager
```

Se tudo estiver correto, remova apenas o temporário; mantenha o rollback até o
próximo deploy estável:

```bash
sudo rm -f /etc/chatbot/chatbot.env.new
```

### 7. Rollback do `.env`

Se algum serviço falhar após a troca:

```bash
sudo systemctl stop chatbot-worker-flow.service chatbot-worker-funil.service

sudo install -o root -g chatbot -m 0640 \
  /etc/chatbot/chatbot.env.rollback \
  /etc/chatbot/chatbot.env

sudo systemctl restart chatbot-webhook.service
sudo systemctl start chatbot-worker-flow.service chatbot-worker-funil.service

systemctl is-active \
  chatbot-webhook.service \
  chatbot-worker-flow.service \
  chatbot-worker-funil.service
```

### Erros conhecidos de ambiente

**Certificado de cliente em `/home/chatbot/.postgresql/postgresql.crt`:**

```bash
sudo grep '^PGSSLCERTMODE=disable$' /etc/chatbot/chatbot.env
```

Se não houver saída, corrija a configuração e reinicie os serviços afetados.
`PGSSLCERTMODE=disable` desativa a procura de certificado TLS de cliente; a
validação do servidor continua protegida por `DB_SSLMODE=verify-full` e
`DB_SSLROOTCERT`.

**Falha ao ler o `.env`:**

```bash
sudo stat -c '%a %U %G %n' /etc/chatbot/chatbot.env
sudo awk -F= '/^[A-Za-z_][A-Za-z0-9_]*=/{print NR ":" $1}' \
  /etc/chatbot/chatbot.env
```

O arquivo deve ser `640 root chatbot`. Não use `cat` no arquivo de produção,
pois isso expõe todos os segredos no terminal e em screenshots.

## Parte B — alterar o schema do banco em produção

### Contrato entre DDL final e banco existente

Cada mudança de schema deve entregar dois artefatos diferentes:

1. **DDL final no código:** uma instalação limpa já cria a tabela, constraint ou
   índice em sua forma definitiva.
2. **SQL incremental para o RDS atual:** um `ALTER`, `CREATE INDEX`, backfill ou
   sequência equivalente, pronto para revisão e execução no DBeaver.

Exemplo conceitual: se uma coluna nova passa a fazer parte de `conversa`, o
`CREATE TABLE chatbot.conversa` em `bank_script.py` recebe a coluna diretamente.
O arquivo não deve ganhar uma cauda histórica com `ALTER TABLE ADD COLUMN`.
Separadamente, o responsável pelo deploy recebe o SQL que adiciona essa coluna
ao RDS já existente.

Essa separação garante simultaneamente que:

- um banco criado do zero nasce no estado final;
- o RDS evolui sem ser apagado e recriado;
- o histórico de implantação não contamina o DDL canônico.

`CREATE TABLE IF NOT EXISTS` não compara nem corrige uma tabela existente.
Executar novamente `setup_database.py` não substitui a migração incremental.

### Arquivos canônicos que podem precisar mudar

- `core/database/deploy/bank_script.py`: schema principal final;
- `core/database/deploy/cache_control_script.py`: controle de versão do cache;
- `core/database/deploy/floodscript.py`: estruturas de flood e bloqueio;
- `core/database/deploy/turno_cliente_script.py`: índices de turno;
- `core/database/deploy/etapa_transicao_script.py`: tabela e mapa de transições;
- `core/database/deploy/povoar_etapas.py`: catálogo final das etapas;
- `callback/webhook/models.py`: representação no Admin, sempre com
  `managed = False` para essas tabelas.

O arquivo correto depende do domínio da alteração. Não mova tudo para
`bank_script.py` apenas por ser SQL.

### Entrega mínima de qualquer mudança de schema

- alteração do DDL final no arquivo canônico;
- atualização do modelo Django não gerenciado, quando aplicável;
- SQL incremental para o estado atual do RDS;
- consultas SQL de validação após a mudança;
- plano de rollback ou explicação de irreversibilidade;
- testes do comportamento afetado;
- indicação de compatibilidade com o webhook que ficará ativo.

### Ordem segura da mudança

1. Inspecionar o schema atual no DBeaver.
2. Definir o estado final e atualizar o DDL Python.
3. Preparar o SQL incremental e seu rollback.
4. Executar a suíte local.
5. Criar snapshot do RDS antes de operação com risco estrutural.
6. Parar `chatbot-worker-flow` e `chatbot-worker-funil` na Lightsail.
7. Aplicar o SQL no DBeaver.
8. Executar as consultas de validação e confirmar a transação.
9. Publicar e instalar o código conforme `rotina_deploy.md`.
10. Recarregar o Gunicorn com `HUP` e só então iniciar os workers.

Para mudança aditiva e retrocompatível, o webhook pode permanecer ativo. Para
rename, drop, mudança de tipo, constraint incompatível ou remoção de coluna,
use o padrão **expand/contract**:

1. expandir o schema sem remover a estrutura antiga;
2. publicar código compatível com os dois formatos;
3. migrar e validar os dados;
4. passar a usar apenas o formato novo;
5. remover a estrutura antiga em deploy posterior.

Se isso não for possível, será necessária uma janela de manutenção e o webhook
poderá precisar ser interrompido. “Webhook sempre ativo” é objetivo do deploy
comum, não autorização para executar DDL incompatível enquanto recebe tráfego.

### Modelo de SQL incremental para o DBeaver

O SQL real deve conter nomes, tipos, defaults e constraints específicos da
tarefa. Este bloco é apenas a estrutura de segurança:

```sql
BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '60s';

-- ALTER TABLE chatbot.tabela ...;
-- UPDATE controlado de backfill, somente quando fizer parte da migração;
-- ALTER TABLE chatbot.tabela ... VALIDATE CONSTRAINT ...;

-- Consultas de validação antes do COMMIT.
-- SELECT ... FROM information_schema.columns ...;
-- SELECT COUNT(*) ...;

COMMIT;
```

No DBeaver, execute o bloco como script e confirme se o auto-commit está de
acordo com a estratégia definida. Não use `CASCADE`, `DROP`, `TRUNCATE` ou
mudança de tipo em produção sem revisão explícita, snapshot e rollback.

Índices grandes podem exigir `CREATE INDEX CONCURRENTLY`, que não pode rodar
dentro desse `BEGIN`. Esse caso precisa de um script e uma validação próprios.

### Validação de compatibilidade

Depois do `ALTER`, compare o RDS com o estado final descrito no código:

- colunas, tipos, nulabilidade e defaults;
- PKs, FKs, `UNIQUE` e `CHECK` constraints;
- índices e predicados de índices parciais;
- seeds de `etapa` e mapa de `etapa_transicao`;
- representação dos modelos `managed = False` no Admin;
- consultas dos repositórios que consomem a estrutura.

`python callback/manage.py migrate` não cria nem altera essas tabelas de negócio.
Ele continua útil para apps internos do Django, mas não substitui o SQL do
DBeaver nem o DDL final do projeto.

### Banco e cache durante uma alteração

Alterar schema não exige `FLUSHDB` ou `FLUSHALL`. Se a tarefa também modificar
dados que alimentam cache, a invalidação deve ocorrer pelo fluxo oficial da
aplicação, Django Admin ou ferramenta operacional específica.

A autocura cobre divergências detectáveis; ela não transforma edição manual de
dados em produção em operação suportada. O DBeaver deste runbook serve para a
migração controlada do schema, não para manter banco e Redis manualmente em
sincronia.

## Parte C — restaurar as tabelas operacionais ao estado vazio

Este procedimento apaga os **dados operacionais** e reinicia suas identidades,
mas preserva as tabelas, constraints, índices e partições. Ele não é uma
recriação do schema e não faz parte de um deploy comum.

Use somente com autorização explícita, snapshot recente do RDS e uma janela em
que ninguém esteja testando ou enviando mensagens para o número da Meta.

### Escopo do reset

Devem voltar ao estado vazio:

- `chatbot.cliente`;
- `chatbot.dependente`;
- `chatbot.conversa`;
- `chatbot.fila_mensagens`;
- `chatbot.historico_mensagens`, incluindo suas partições;
- `chatbot.respostas_desafios`;
- `chatbot.pesquisa_satisfacao`;
- `chatbot.funil_envios`;
- `chatbot.webhook_flood_evento`, por ser um registro operacional temporário
  da janela de flood.

Não devem ser alteradas pelo reset:

- `chatbot.cliente_bloqueado_meta`;
- `chatbot.unidade`;
- `chatbot.etapa`;
- `chatbot.etapa_transicao`;
- `chatbot.integracao_funil_unidade`;
- `chatbot.cache_controle`;
- tabelas internas do Django, roles, schema, constraints, índices e demais
  estruturas que não estejam na lista de reset.

`cliente_bloqueado_meta` é a exceção operacional permanente. Ela registra o
bloqueio aplicado pela Meta e não pode ser apagada para facilitar testes. Sua FK
para `cliente` usa `ON DELETE SET NULL`: ao remover os clientes, o
`id_cliente` do bloqueio pode ficar nulo, mas `wa_id_cliente`, unidade, phone ID
e o próprio registro de bloqueio permanecem.

Por essa dependência, **não use** `TRUNCATE chatbot.cliente CASCADE`. Isso pode
incluir `cliente_bloqueado_meta` no cascade e destruir os bloqueios preservados.

### 1. Preparar a janela de manutenção

Crie um snapshot do RDS e pare os três processos que acessam as tabelas. Neste
reset excepcional, o webhook também deve parar para não inserir uma mensagem no
meio da transação:

```bash
sudo systemctl stop \
  chatbot-webhook.service \
  chatbot-worker-flow.service \
  chatbot-worker-funil.service

systemctl is-active \
  chatbot-webhook.service \
  chatbot-worker-flow.service \
  chatbot-worker-funil.service
```

O resultado esperado durante a manutenção é `inactive` para os três. Não envie
mensagens ao número nesse intervalo: a Meta pode tentar entregar novamente um
evento recebido enquanto o webhook estiver indisponível.

### 2. Conferir banco e volumes antes de apagar

Execute no DBeaver e confirme que está no RDS e no database corretos:

```sql
SELECT
    current_database() AS database_atual,
    current_user AS usuario_atual,
    inet_server_addr() AS servidor_atual,
    NOW() AS conferido_em;

SELECT 'cliente_bloqueado_meta' AS tabela, COUNT(*) AS registros
FROM chatbot.cliente_bloqueado_meta
UNION ALL
SELECT 'cliente', COUNT(*) FROM chatbot.cliente
UNION ALL
SELECT 'dependente', COUNT(*) FROM chatbot.dependente
UNION ALL
SELECT 'conversa', COUNT(*) FROM chatbot.conversa
UNION ALL
SELECT 'fila_mensagens', COUNT(*) FROM chatbot.fila_mensagens
UNION ALL
SELECT 'historico_mensagens', COUNT(*) FROM chatbot.historico_mensagens
UNION ALL
SELECT 'respostas_desafios', COUNT(*) FROM chatbot.respostas_desafios
UNION ALL
SELECT 'pesquisa_satisfacao', COUNT(*) FROM chatbot.pesquisa_satisfacao
UNION ALL
SELECT 'funil_envios', COUNT(*) FROM chatbot.funil_envios
UNION ALL
SELECT 'webhook_flood_evento', COUNT(*) FROM chatbot.webhook_flood_evento;
```

Guarde o total de `cliente_bloqueado_meta`; o script também compara seus campos
permanentes antes do `COMMIT`.

### 3. Executar o reset transacional no DBeaver

Execute o bloco inteiro como script. Não acrescente `CASCADE`:

```sql
BEGIN;

SET LOCAL lock_timeout = '5s';
SET LOCAL statement_timeout = '5min';

LOCK TABLE
    chatbot.cliente_bloqueado_meta,
    chatbot.cliente,
    chatbot.conversa,
    chatbot.dependente,
    chatbot.fila_mensagens,
    chatbot.historico_mensagens,
    chatbot.respostas_desafios,
    chatbot.pesquisa_satisfacao,
    chatbot.funil_envios,
    chatbot.webhook_flood_evento
IN ACCESS EXCLUSIVE MODE;

CREATE TEMP TABLE reset_operacional_bloqueios_antes
ON COMMIT DROP
AS
SELECT
    id_bloqueio,
    wa_id_cliente,
    id_unidade,
    phone_id_unidade
FROM chatbot.cliente_bloqueado_meta;

TRUNCATE TABLE
    chatbot.historico_mensagens,
    chatbot.respostas_desafios,
    chatbot.pesquisa_satisfacao,
    chatbot.funil_envios,
    chatbot.dependente,
    chatbot.fila_mensagens,
    chatbot.conversa,
    chatbot.webhook_flood_evento
RESTART IDENTITY;

-- DELETE, e não TRUNCATE, preserva cliente_bloqueado_meta via ON DELETE SET NULL.
DELETE FROM chatbot.cliente;

-- Faz o próximo cliente começar novamente em 1.
SELECT setval(
    pg_get_serial_sequence('chatbot.cliente', 'id_cliente'),
    1,
    FALSE
);

DO $$
DECLARE
    registros_operacionais BIGINT;
BEGIN
    IF EXISTS (
        SELECT 1
        FROM (
            (
                SELECT *
                FROM reset_operacional_bloqueios_antes
                EXCEPT
                SELECT
                    id_bloqueio,
                    wa_id_cliente,
                    id_unidade,
                    phone_id_unidade
                FROM chatbot.cliente_bloqueado_meta
            )
            UNION ALL
            (
                SELECT
                    id_bloqueio,
                    wa_id_cliente,
                    id_unidade,
                    phone_id_unidade
                FROM chatbot.cliente_bloqueado_meta
                EXCEPT
                SELECT *
                FROM reset_operacional_bloqueios_antes
            )
        ) AS diferencas
    ) THEN
        RAISE EXCEPTION
            'cliente_bloqueado_meta foi alterada; reset cancelado';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM chatbot.cliente_bloqueado_meta
        WHERE id_cliente IS NOT NULL
    ) THEN
        RAISE EXCEPTION
            'restaram vínculos para clientes removidos';
    END IF;

    SELECT
        (SELECT COUNT(*) FROM chatbot.cliente)
      + (SELECT COUNT(*) FROM chatbot.dependente)
      + (SELECT COUNT(*) FROM chatbot.conversa)
      + (SELECT COUNT(*) FROM chatbot.fila_mensagens)
      + (SELECT COUNT(*) FROM chatbot.historico_mensagens)
      + (SELECT COUNT(*) FROM chatbot.respostas_desafios)
      + (SELECT COUNT(*) FROM chatbot.pesquisa_satisfacao)
      + (SELECT COUNT(*) FROM chatbot.funil_envios)
      + (SELECT COUNT(*) FROM chatbot.webhook_flood_evento)
      INTO registros_operacionais;

    IF registros_operacionais <> 0 THEN
        RAISE EXCEPTION
            'reset incompleto: % registros operacionais restantes',
            registros_operacionais;
    END IF;
END
$$;

COMMIT;
```

Se qualquer comando falhar antes do `COMMIT`, execute:

```sql
ROLLBACK;
```

Não tente contornar uma FK adicionando `CASCADE`. Investigue a dependência e
atualize este runbook antes de repetir a operação.

### 4. Limpar somente o cache operacional

Depois do `COMMIT`, execute uma vez na Lightsail:

```bash
cd /opt/chatbot/app
sudo -u chatbot env PYTHONPATH=/opt/chatbot/app \
  /opt/chatbot/venv/bin/python -m core.cache.cache_reset --operacional
```

Esse comando remove somente cache de cliente, bloqueios temporários de conversa
e contadores de flood. Ele preserva o mapa e a versão do cache de unidades. Não
use `FLUSHDB` nem `FLUSHALL`.

### 5. Reativar e validar os serviços

```bash
sudo systemctl start chatbot-webhook.service

curl -i https://webhook.3esltech.com/webhook

sudo systemctl start \
  chatbot-worker-flow.service \
  chatbot-worker-funil.service

systemctl is-active \
  chatbot-webhook.service \
  chatbot-worker-flow.service \
  chatbot-worker-funil.service
```

O resultado final esperado é HTTP `200` no webhook e três estados `active`.
Confira também se não surgiram erros de banco ou Redis:

```bash
sudo journalctl \
  -u chatbot-webhook.service \
  -u chatbot-worker-flow.service \
  -u chatbot-worker-funil.service \
  --since "10 minutes ago" \
  --no-pager
```

Depois da validação, a primeira mensagem nova pode recriar `cliente`, `conversa`
e os caches operacionais normalmente. Um cliente presente em
`cliente_bloqueado_meta` continua bloqueado mesmo sem um `id_cliente` associado.
