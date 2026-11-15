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
  `core/database/deploy_database/bank_script.py` como migração histórica.
- Uma intervenção em dados de negócio tem escopo próprio. O arquivamento do projeto e um deploy de código não autorizam limpeza de banco ou cache.

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

Use somente o arquivo local privado `.env`, que já é ignorado pelo Git, como
fonte local de configuração. Mantenha suas chaves alinhadas com
`/etc/chatbot/chatbot.env`, que é a fonte carregada pelos serviços da VM. Não
crie arquivos paralelos como `.env.prod`.

Antes de copiar, confira especialmente:

```text
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,18.229.43.133,webhook.3esltech.com,monitoramento.3esltech.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://webhook.3esltech.com,https://monitoramento.3esltech.com
DJANGO_TRUST_X_FORWARDED_PROTO=True
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DB_SSLMODE=verify-full
DB_SSLROOTCERT=/etc/ssl/certs/aws-rds-global-bundle.pem
PGSSLCERTMODE=disable
REDIS_HOST=ENDPOINT_DO_REDIS_REMOTO
META_GRAPH_API_VERSION=26.0
FUNIL_WORKER_ENABLED=True
```

O follow-up é habilitado pela própria unit, sem segredo adicional. Seus padrões
são `FOLLOWUP_WORKER_ENABLED=true`, `FOLLOWUP_POLL_SECONDS=60` e
`FOLLOWUP_BATCH_SIZE=20`. Se alguma dessas chaves estiver neste arquivo, seu
valor prevalece sobre `Environment=` da unit. Preserve uma desativação
intencional ao trocar o ambiente; ativação do proativo exige flow compatível.

Os demais tokens, IDs, senhas e endpoints devem conter os valores reais do
ambiente, sem serem enviados ao GitHub.

O subdomínio `monitoramento.3esltech.com` usa o mesmo IP estático do webhook.
Sua inclusão no ambiente prepara a aceitação do domínio pelo Django, mas não
publica o painel sozinha. Nginx e certificado HTTPS para esse endereço devem ser
configurados na VM durante a implantação. O aplicativo já possui login, painel,
APIs de consulta e CSV. Ele depende das tabelas nativas de autenticação/sessões
do Django e da migração do vínculo de usuário na unidade. Executar
`collectstatic` para publicar CSS, JavaScript e logo.

Na VM de producao, `REDIS_HOST` nunca deve ser `localhost`, `127.0.0.1` ou
`::1`. A rotina operacional e a remocao do Redis local estao documentadas em
[`servicos_e_redis_remoto.md`](servicos_e_redis_remoto.md).

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
sudo -u chatbot /opt/chatbot/venv/bin/python -c "from dotenv import dotenv_values; c=dotenv_values('/etc/chatbot/chatbot.env.new',interpolate=False); required=('DJANGO_SECRET_KEY','DJANGO_ALLOWED_HOSTS','DJANGO_CSRF_TRUSTED_ORIGINS','DB_HOST','DB_NAME','DB_USER','DB_PASSWORD','DB_SSLMODE','DB_SSLROOTCERT','PGSSLCERTMODE','REDIS_HOST','META_ACCESS_TOKEN','META_GRAPH_API_VERSION','META_WEBHOOK_VERIFY_TOKEN','META_APP_SECRET','FUNIL_WORKER_ENABLED'); missing=[k for k in required if not c.get(k)]; print('AMBIENTE_OK' if not missing else 'FALTANDO: '+','.join(missing)); raise SystemExit(bool(missing))"
```

O comando deve imprimir `AMBIENTE_OK`.

### 5. Testar o arquivo temporário contra Django, RDS e Redis

Este teste injeta o arquivo `.new` apenas no processo de validação. Ele ainda
não altera os serviços ativos:

```bash
sudo -u chatbot env -i \
  PYTHONPATH=/opt/chatbot/app \
  /opt/chatbot/venv/bin/python -c "import os,sys; from dotenv import dotenv_values; c=dotenv_values('/etc/chatbot/chatbot.env.new',interpolate=False); invalid=[k for k,v in c.items() if v is None]; assert not invalid, 'VALORES_INVALIDOS: '+','.join(invalid); os.environ.update({k:str(v) for k,v in c.items()}); os.environ['PYTHON_DOTENV_DISABLED']='1'; sys.path.insert(0,'/opt/chatbot/app/callback'); from core.database.connection_aws import get_conn; conn=get_conn('env_preflight'); cursor=conn.cursor(); cursor.execute('SELECT 1'); assert cursor.fetchone()[0] == 1; conn.close(); from core.cache.redis_client import get_redis_safe,validar_redis_remoto; redis=get_redis_safe(retries=1,delay=0,validate=True); validar_redis_remoto(redis); assert redis.ping() is True; redis.close(); os.environ.setdefault('DJANGO_SETTINGS_MODULE','callback.settings'); import django; django.setup(); from django.core.management import call_command; call_command('check',deploy=True); print('PREFLIGHT_ENV_RDS_REDIS_OK')"
```

Não instale o arquivo se esse preflight terminar com erro.

### 6. Aplicar e recuperar o ambiente

Registrar os serviços ativos. Após validar o arquivo temporário, pausar os processos afetados na ordem da [rotina de manutenção](rotina_deploy.md). Instalar o arquivo com proprietário `root:chatbot` e modo `0640`. Um processo lê o `EnvironmentFile` ao iniciar. Para carregar novas variáveis, reiniciar cada serviço afetado, incluindo os workers de consulta, origem e consumo quando usam a configuração alterada. Restaurar apenas os serviços anteriormente ativos e conferir logs e conectividade. Guardar o backup restrito. Em caso de erro, reinstalar o backup validado com o mesmo proprietário e permissões e repetir a retomada.

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

- `core/database/deploy_database/bank_script.py`: schema principal final;
- `core/database/deploy_database/followup_script.py`: tabelas de recibos, retomadas e legado, chamadas pelo schema principal;
- `core/database/deploy_database/cache_control_script.py`: controle de versão do cache;
- `core/database/deploy_database/floodscript.py`: estruturas de flood e bloqueio;
- `core/database/deploy_database/turno_cliente_script.py`: índices de turno;
- `core/database/deploy_database/etapa_transicao_script.py`: tabela e mapa de transições;
- `core/database/deploy_database/povoar_etapas.py`: catálogo final das etapas;
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

### Ordem da mudança

Conferir versão de origem, preparar backup e ensaiar a migração em uma cópia com dados representativos. A [rotina de deploy](rotina_deploy.md) cobre a coordenação dos sete processos e a validação posterior. Os [scripts de migração](../deploy/migrations) documentam pré-condições e verificações de cada versão. A migração da V1.20.0 preserva os encerramentos e recibos anteriores e introduz o terceiro follow-up.

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

## Manutenção de dados

O antigo reset global usava um inventário anterior à inclusão de chats, filas FireAds, snapshots de entrega e consumo Meta. Uma restauração integral precisa considerar as dependências do schema efetivamente instalado, as mensagens já aceitas por sistemas externos e os bloqueios permanentes. Para manutenção de um contato específico, os procedimentos com escopo por telefone estão no [guia de utilitários](../utilitarios/README.md#consulta-e-remoção-por-telefone). O PostgreSQL e o cache têm ciclos de retenção distintos.
