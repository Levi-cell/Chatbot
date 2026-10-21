# Ambiente de desenvolvimento do Chatbot

## 1. Finalidade deste documento

Este documento registra a arquitetura e o passo a passo para construir um
ambiente de desenvolvimento isolado, testar alterações com números reais do
WhatsApp Cloud API e promover o mesmo código para produção sem trocar URLs,
credenciais ou configurações dentro da branch.

Ele foi escrito para continuar útil mesmo sem o histórico das conversas que
levaram às decisões abaixo. Nenhum segredo real deve ser acrescentado a este
arquivo.

> **Estado deste guia:** plano de construção. A criação deste Markdown não
> implementa os guardas de ambiente, não cria banco, não cria Redis, não altera
> a Meta e não cria branches.

## 2. Estado conhecido em 1º de setembro de 2026

- produção está na linha V1.0.8;
- a branch de produção se chama `prod`;
- o callback padrão do App da Meta é
  `https://webhook.3esltech.com/webhook` e pertence à produção;
- as WABAs de Santo Antônio de Jesus e Rio Vermelho são de produção;
- a WABA `Supera teste` foi criada para desenvolvimento, mas ainda não foi
  configurada;
- `Test WhatsApp Business Account` é a conta de teste criada pela própria Meta
  e não será o ambiente DEV definitivo;
- ainda falta adquirir um número/chip para desenvolvimento;
- o projeto ainda não possui todos os guardas descritos neste plano;
- o banco DEV, o Redis DEV, o usuário de sistema Meta DEV e a branch `develop`
  ainda precisam ser preparados.

## 3. Decisões de arquitetura

### 3.1 Código igual; configuração diferente

DEV e produção devem executar o mesmo código. A branch define **qual versão do
código** está sendo testada; variáveis externas definem **qual infraestrutura**
essa versão utiliza.

É proibido implementar lógica como:

```python
if branch_git == "develop":
    usar_banco_dev()
else:
    usar_banco_prod()
```

O processo não deve consultar `.git`, nome de branch ou caminho da pasta para
escolher banco, Redis, token ou integração. Em vez disso, deve exigir
`CHATBOT_ENV=development`, `CHATBOT_ENV=test` ou
`CHATBOT_ENV=production` e falhar se a combinação de recursos não corresponder
ao ambiente declarado.

Isso permite promover `develop` para `prod` sem editar o código. Na VM, o
systemd continuará injetando o arquivo privado de produção. Na máquina local,
o processo carregará somente a configuração privada de desenvolvimento.

### 3.2 Mesmo App da Meta, WABAs diferentes

O mesmo App da Meta pode atender DEV e produção. O callback padrão do App
permanece apontando para produção. A WABA DEV receberá um callback alternativo
por meio de `override_callback_uri`:

```text
App Meta atual
├── WABA SAJ (produção) ----------> webhook.3esltech.com/webhook
├── WABA Rio Vermelho (produção) -> webhook.3esltech.com/webhook
└── WABA Supera teste (DEV) ------> <domínio-ngrok>/webhook
```

Nunca substituir a URL exibida no painel geral **Assinar os webhooks** pelo
ngrok. Esse campo é o callback padrão do App e hoje protege o tráfego de
produção.

### 3.3 Uma WABA por unidade no desenho atual

O contrato atual do projeto contém `unidade.waba_id UNIQUE`, e o Admin remove a
assinatura da WABA inteira quando uma unidade é excluída. Portanto:

- para testar uma unidade, usar `Supera teste` com um número DEV;
- para simular SAJ e Rio Vermelho simultaneamente, criar **duas WABAs DEV**,
  cada uma com seu próprio número;
- as duas WABAs DEV podem apontar para o mesmo webhook ngrok;
- não cadastrar duas unidades do chatbot na mesma WABA sem antes redesenhar o
  modelo, o Admin e seus testes.

Começar com uma única WABA e um único número reduz custo e complexidade. A
segunda WABA só será necessária quando um teste realmente depender de duas
unidades ao mesmo tempo.

### 3.4 Banco separado na mesma instância RDS

Usar outro banco PostgreSQL na mesma instância RDS:

```text
mesmo endpoint e mesma instância RDS
├── <banco-produção>  -> schema chatbot -> produção
└── db_chatbot_dev    -> schema chatbot -> desenvolvimento
```

Não usar apenas `chatbot_dev` como outro schema do banco de produção. O código
possui muitas referências explícitas a `chatbot.<tabela>`; mudar somente o
`search_path` não redirecionaria essas consultas. Um banco separado permite
manter o schema interno chamado `chatbot` e selecionar o ambiente apenas com
`DB_NAME`.

A AWS permite vários bancos criados pelo usuário dentro da mesma instância
RDS. Isso não cria outra instância com nova cobrança fixa. O banco DEV ainda
consome armazenamento, I/O, backup, conexões, CPU e memória da instância
compartilhada; testes pesados podem afetar produção e devem ser controlados.

### 3.5 Redis completamente isolado

DEV nunca pode usar o Redis de produção. As chaves atuais não possuem namespace
global por ambiente e `setup_database.py` chama uma limpeza que remove chaves
operacionais por nomes e prefixos conhecidos. Apontar DEV para o Redis de
produção poderia apagar cache de unidades, bloqueios, flood e controles do
webhook real.

Ordem de preferência:

1. Redis local em contêiner, liberado somente para
   `CHATBOT_ENV=development` por um guarda explícito;
2. endpoint/banco Redis remoto exclusivo de DEV;
3. somente após uma mudança arquitetural completa, database lógico e namespace
   separados no mesmo servidor.

O código atual recusa Redis local e ainda não aceita `REDIS_DB`; essa adaptação
precisa acontecer antes da opção 1 ou 3. Não enfraquecer a recusa de loopback em
produção.

### 3.6 Integrações externas

- `FUNIL_WORKER_ENABLED=False` em DEV;
- não copiar para DEV uma integração ativa do Funil;
- links de agendamento e Instagram devem ser de teste ou claramente inofensivos;
- o acesso Meta de DEV deve alcançar somente as WABAs/números DEV;
- dados pessoais de produção não devem ser clonados para a máquina local.

## 4. Matriz final dos ambientes

| Item | Desenvolvimento | Produção |
|---|---|---|
| Código | `develop` ou `feature/*` | `prod` |
| Identidade | `CHATBOT_ENV=development` | `CHATBOT_ENV=production` |
| Configuração | `.env.dev`, privado | `/etc/chatbot/chatbot.env` |
| App Meta | mesmo App atual | mesmo App atual |
| WABA | `Supera teste` | WABAs reais |
| Número | chip/número exclusivamente DEV | números reais |
| Callback | `https://<ngrok-estável>/webhook` | `https://webhook.3esltech.com/webhook` |
| Verify token | exclusivo de DEV | atual de produção |
| Access token | usuário de sistema DEV | usuário de sistema de produção |
| App Secret | mesmo App Secret, guardado separadamente | atual de produção |
| Banco | `db_chatbot_dev` | banco atual |
| Schema interno | `chatbot` | `chatbot` |
| Usuário PostgreSQL | exclusivo de DEV | atual de produção |
| Redis | local permitido somente em DEV ou remoto exclusivo | remoto atual |
| Funil | desativado | conforme configuração de produção |
| Web | Django local, porta 8000 | Gunicorn + Nginx + HTTPS |

## 5. Limitações atuais que precisam ser resolvidas antes do primeiro teste

Uma auditoria do código atual encontrou estes pontos:

1. `core/config_env.py` sempre tenta carregar `.env` da raiz. Ainda não existe
   seleção explícita de `.env.dev` por `CHATBOT_ENV`.
2. `core/database/connection_aws.py` usa `DB_NAME`, mas não confirma
   `current_database()` nem uma identidade persistente do ambiente.
3. `callback/callback/settings.py` fixa o `search_path=chatbot`, o que confirma
   a decisão de manter o mesmo schema dentro de bancos diferentes.
4. `core/cache/redis_client.py` recusa loopback e endereço da própria máquina
   em qualquer ambiente.
5. as chaves Redis não possuem um namespace completo DEV/produção.
6. `core/cache/cache_reset.py` remove chaves e prefixos; por isso jamais pode
   operar sobre o Redis real durante o bootstrap DEV.
7. `core/database/deploy_database/setup_database.py` executa essa limpeza de
   cache ao final do setup.
8. `core/database/deploy_database/bank_script.py` contém
   `ALTER ROLE fushi`, nome específico de produção e com efeito além do banco
   DEV se a role for compartilhada.
9. o webhook real é exatamente `/webhook`, sem barra final.
10. o webhook identifica a unidade por
    `entry[].changes[].value.metadata.phone_number_id` e consulta
    `chatbot.unidade.phone_number_id`.
11. ao cadastrar unidade, o Django Admin valida WABA/número, assina a WABA,
    registra o número na Meta e atualiza o cache. Não é um simples cadastro
    local.
12. `FUNIL_WORKER_ENABLED` já oferece um kill switch e deve permanecer falso
    em DEV.
13. o ngrok, se encaminhar a aplicação inteira, também torna `/admin/`
    acessível publicamente. É necessário publicar somente `/webhook` ou
    bloquear o restante para o host público.

Nenhum servidor DEV deve ser iniciado antes de fechar os itens 1, 2, 4, 6, 8 e
13.

## 6. Fase A — preparar guardas no código

Esta fase deve ser feita numa feature branch e coberta por testes antes de
qualquer recurso DEV receber tráfego real.

### 6.1 Identidade explícita

Adicionar `CHATBOT_ENV` com domínio fechado:

```text
development
test
production
```

Valor ausente ou desconhecido deve abortar o processo. Testes unitários devem
usar `test` e não carregar arquivos de ambiente locais.

Comportamento pretendido:

```text
CHATBOT_ENV=development -> pode carregar .env.dev; rejeita banco/Redis de produção
CHATBOT_ENV=test        -> usa valores injetados pela suíte; não carrega .env
CHATBOT_ENV=production  -> usa somente variáveis externas; não carrega .env.dev
```

O arquivo `.env.dev` já está coberto pelo padrão `.env.*` do `.gitignore`. Um
eventual `.env.example` pode ser versionado apenas com nomes e placeholders.

### 6.2 Preflight obrigatório e fail-closed

Criar uma verificação reutilizada por webhook, worker de fluxo, worker do Funil
e scripts de banco. Antes do primeiro trabalho externo, ela deve confirmar:

- valor de `CHATBOT_ENV`;
- `SELECT current_database()`;
- identidade persistente do banco;
- usuário PostgreSQL esperado para o ambiente;
- identidade e destino do Redis;
- `FUNIL_WORKER_ENABLED=False` quando o ambiente for DEV;
- ausência de combinações explicitamente proibidas.

Uma forma forte de identificar o banco é configurar um marcador persistente e
consultá-lo em cada inicialização:

```sql
ALTER DATABASE db_chatbot_dev
    SET chatbot.environment = 'development';
```

O guarda pode ler:

```sql
SELECT
    current_database(),
    current_user,
    current_setting('chatbot.environment', TRUE);
```

Ao introduzir esse guarda em produção, primeiro cadastrar o marcador
`production` no banco real, renovar as conexões e só então publicar o código
que passa a exigi-lo.

Exemplos que devem abortar:

- `CHATBOT_ENV=development` conectado a um banco marcado `production`;
- `CHATBOT_ENV=production` conectado a `db_chatbot_dev`;
- DEV conectado ao endpoint Redis conhecido de produção;
- DEV com `FUNIL_WORKER_ENABLED=True`;
- produção com opção de Redis local ativada.

Não registrar senhas ou tokens no resultado do preflight. Hostnames, nomes de
banco e ambiente podem ser exibidos; tokens devem aparecer apenas como
presente/ausente.

### 6.3 Role PostgreSQL

Remover o nome `fushi` do setup genérico. O código não deve executar um
`ALTER ROLE` global de produção durante a criação do banco DEV.

Escolher uma das soluções:

- preferida: provisionar as roles fora da aplicação e retirar essa etapa do
  setup automático;
- alternativa: configurar somente a role atual e somente o banco atual, usando
  identificadores PostgreSQL seguros e um preflight aprovado.

DEV deve usar uma role que não consiga conectar ou alterar o banco de
produção.

### 6.4 Redis local somente em DEV

Se for escolhida a opção local, criar uma variável como
`REDIS_ALLOW_LOCAL=True`, aceita apenas quando `CHATBOT_ENV=development`.
Qualquer outra combinação deve continuar recusando loopback.

Mesmo com Redis exclusivo, manter nomes de chave previsíveis e considerar
`REDIS_NAMESPACE=chatbot:dev` como defesa adicional. Namespace não substitui a
separação física/lógica enquanto existirem rotinas de limpeza sem escopo.

### 6.5 Superfície pública do ngrok

O host do ngrok deve aceitar publicamente somente:

```text
GET  /webhook   # desafio de verificação da Meta
POST /webhook   # notificações assinadas da Meta
```

Bloquear `/admin/`, `/static/` e demais rotas quando o `Host` for o domínio
ngrok, ou aplicar uma Traffic Policy equivalente no ngrok. O Admin continuará
acessível localmente por `http://127.0.0.1:8000/admin/`.

Durante exposição pública:

- usar `DJANGO_DEBUG=False`;
- manter `META_WEBHOOK_SIGNATURE_REQUIRED=True`;
- limitar o corpo como em produção;
- nunca publicar o token de verificação ou App Secret;
- não usar autenticação HTTP comum sobre `/webhook`, pois a Meta precisa
  alcançá-lo diretamente.

### 6.6 Testes obrigatórios dos guardas

Adicionar testes para, no mínimo:

- ambiente ausente;
- ambiente inválido;
- DEV + banco production;
- production + banco DEV;
- DEV + Redis de produção;
- production + Redis local;
- DEV + Funil habilitado;
- `test` sem leitura de `.env.dev`;
- host ngrok tentando abrir `/admin/`;
- host local abrindo `/admin/`;
- `/webhook` funcionando no host ngrok.

## 7. Fase B — criar o fluxo Git

### 7.1 Branches permanentes

```text
prod       código aprovado e implantável
develop    integração das mudanças já testadas em features
feature/*  trabalho isolado e temporário
hotfix/*   correção urgente originada de prod
```

Antes de criar `develop`, o diretório deve estar limpo e toda alteração atual
deve ter destino conhecido. Nunca usar reset destrutivo para “limpar” trabalho.

Criação inicial, uma única vez:

```bash
git status -sb
git fetch --prune origin
git switch prod
git pull --ff-only origin prod
git switch -c develop
git push -u origin develop
```

Proteger `prod` no GitHub contra force push e exclusão. Quando viável, exigir
pull request e suíte de testes. Proteger também `develop` contra force push.

### 7.2 Rotina de uma funcionalidade

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feature/nome-curto

# implementar, revisar e testar

git push -u origin feature/nome-curto
```

Abrir PR `feature/nome-curto -> develop`. O ambiente DEV acompanha `develop`
depois do merge. Segredos e arquivos de ambiente nunca participam do PR.

### 7.3 Hotfix

Um hotfix nasce de `prod`, volta para `prod` após validação e depois também é
incorporado em `develop`, evitando que a correção desapareça na próxima versão.

## 8. Fase C — criar o banco DEV na mesma instância RDS

### 8.1 Preparação

- executar com uma conta administrativa do RDS, nunca com a credencial da
  aplicação;
- confirmar por escrito o endpoint e o banco atual antes de qualquer comando;
- usar senha gerada e armazenada fora do repositório;
- não reutilizar a role de produção;
- não usar `DROP DATABASE`, `DROP SCHEMA` ou nomes calculados sem conferência.

Exemplo a adaptar — sem colocar a senha real neste arquivo:

```sql
CREATE ROLE chatbot_dev_app
    LOGIN
    PASSWORD '<SENHA_DEV_GERADA>'
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    CONNECTION LIMIT 8;

CREATE DATABASE db_chatbot_dev
    OWNER chatbot_dev_app
    ENCODING 'UTF8'
    TEMPLATE template0;

ALTER DATABASE db_chatbot_dev CONNECTION LIMIT 10;
```

`CREATE DATABASE` deve ser executado fora de `BEGIN/COMMIT`. Depois:

```sql
REVOKE ALL ON DATABASE db_chatbot_dev FROM PUBLIC;
GRANT CONNECT, TEMPORARY ON DATABASE db_chatbot_dev TO chatbot_dev_app;

ALTER DATABASE db_chatbot_dev
    SET chatbot.environment = 'development';

ALTER ROLE chatbot_dev_app IN DATABASE db_chatbot_dev
    SET timezone TO 'America/Sao_Paulo';

ALTER ROLE chatbot_dev_app IN DATABASE db_chatbot_dev
    SET idle_in_transaction_session_timeout = '30min';

ALTER ROLE chatbot_dev_app IN DATABASE db_chatbot_dev
    SET statement_timeout = '10min';

ALTER ROLE chatbot_dev_app IN DATABASE db_chatbot_dev
    SET lock_timeout = '15s';
```

Também impedir a role DEV de conectar ao banco de produção. Como PostgreSQL
normalmente concede `CONNECT` a `PUBLIC`, um simples `REVOKE ... FROM
chatbot_dev_app` pode não ser suficiente. Primeiro inventariar todas as roles e
serviços que legitimamente usam produção; em janela controlada, retirar
`CONNECT` de `PUBLIC` e concedê-lo explicitamente às roles reais de produção e
administração. Só executar essa mudança depois de revisar o impacto para não
bloquear monitoramento, manutenção ou o próprio chatbot.

O acesso de rede ao RDS deve reutilizar uma rota segura já existente, VPN ou
túnel. Se a instância for pública, limitar a regra do Security Group ao IP
necessário; nunca abrir PostgreSQL para `0.0.0.0/0` apenas para facilitar DEV.

### 8.2 Estrutura inicial

Depois de corrigir o setup e apontar comprovadamente para DEV:

```powershell
$env:CHATBOT_ENV = "development"
python -m core.database.deploy_database.setup_database
python callback/manage.py migrate --noinput
python callback/manage.py createsuperuser
python callback/manage.py check
```

Ordem necessária:

1. `setup_database` cria o schema `chatbot`, tabelas de negócio, funções,
   etapas e transições;
2. `manage.py migrate` cria as estruturas gerenciadas pelo Django;
3. `createsuperuser` cria somente o administrador DEV.

Os modelos de negócio estão com `managed=False`; `manage.py migrate` não
substitui o DDL de `core/database/deploy_database/`.

Um banco criado do baseline atual não precisa reaplicar todas as migrações
históricas. Migrações incrementais passam a ser aplicadas a partir do estado
em que o banco DEV foi criado.

### 8.3 Dados iniciais

Preferir dados sintéticos:

- uma unidade DEV;
- cliente e dependentes fictícios;
- link de agendamento de teste;
- integração do Funil ausente ou inativa;
- nenhum telefone, e-mail, comentário ou histórico real de clientes.

Se um defeito exigir dados semelhantes aos reais, exportar apenas o menor
recorte necessário e anonimizar antes de disponibilizá-lo no ambiente DEV.
Nunca restaurar uma cópia bruta de produção no computador pessoal.

## 9. Fase D — preparar Redis DEV

### 9.1 Opção recomendada para desenvolvimento local

Depois de implementar o guarda `REDIS_ALLOW_LOCAL`, um contêiner local evita
novo serviço pago:

```powershell
docker run --name chatbot-redis-dev `
  --publish 127.0.0.1:6380:6379 `
  --detach redis:7-alpine
```

Configuração correspondente:

```dotenv
REDIS_HOST=127.0.0.1
REDIS_PORT=6380
REDIS_USERNAME=
REDIS_PASSWORD=
REDIS_SSL=False
REDIS_ALLOW_LOCAL=True
```

A publicação em `127.0.0.1` impede acesso direto pela rede. Não abrir a porta
6379/6380 no roteador ou firewall.

### 9.2 Alternativa remota

Criar endpoint e credenciais exclusivos de DEV. Não basta trocar somente um
prefixo no Redis de produção com o código atual. Registrar um marcador DEV e
fazer o preflight confirmar esse marcador antes de qualquer limpeza.

## 10. Fase E — arquivo `.env.dev`

O arquivo deve ficar na raiz, ignorado pelo Git, com valores reais apenas na
máquina autorizada. Modelo sem segredos:

```dotenv
CHATBOT_ENV=development

DB_HOST=<MESMO_ENDPOINT_RDS>
DB_NAME=db_chatbot_dev
DB_USER=chatbot_dev_app
DB_PASSWORD=<SEGREDO_DEV>
DB_PORT=5432
DB_SSLMODE=verify-full
DB_SSLROOTCERT=<CAMINHO_CA_RDS>

REDIS_HOST=127.0.0.1
REDIS_PORT=6380
REDIS_USERNAME=
REDIS_PASSWORD=
REDIS_SSL=False
REDIS_ALLOW_LOCAL=True

DJANGO_SECRET_KEY=<CHAVE_EXCLUSIVA_DEV>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,<HOST_NGROK>
DJANGO_CSRF_TRUSTED_ORIGINS=https://<HOST_NGROK>
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DJANGO_TRUST_X_FORWARDED_PROTO=False
DJANGO_SECURE_HSTS_SECONDS=0
WEBHOOK_MAX_BODY_BYTES=262144

META_APP_ID=<MESMO_APP_ID>
META_APP_SECRET=<MESMO_APP_SECRET_GUARDADO_SEPARADAMENTE>
META_ACCESS_TOKEN=<TOKEN_DO_USUARIO_DE_SISTEMA_DEV>
META_GRAPH_API_VERSION=<VERSAO_CONFIGURADA_NO_PROJETO>
META_PHONE_REGISTRATION_PIN=<PIN_DO_NUMERO_DEV>
META_WEBHOOK_VERIFY_TOKEN=<TOKEN_DE_VERIFICACAO_EXCLUSIVO_DEV>
META_WEBHOOK_SIGNATURE_REQUIRED=True
META_HTTP_CONNECT_TIMEOUT_SECONDS=30
META_HTTP_READ_TIMEOUT_SECONDS=35

FUNIL_WORKER_ENABLED=False
FUNIL_INTERVALO_SEGUNDOS=1800
FUNIL_LIMITE_POR_CICLO=100
FUNIL_LEASE_SEGUNDOS=900
FUNIL_RETRY_LEAD_SEGUNDOS=3600
FUNIL_HTTP_CONNECT_TIMEOUT_SECONDS=10
FUNIL_HTTP_READ_TIMEOUT_SECONDS=30
```

Regras:

- não copiar o token Meta de produção;
- App Secret e App ID são do mesmo App, mas continuam sendo segredos/valores
  externos;
- usar verify token e Django secret diferentes dos de produção;
- nunca enviar `.env.dev` por chat, e-mail ou commit;
- cada terminal DEV precisa receber `CHATBOT_ENV=development` antes de iniciar
  Python, salvo quando houver um lançador seguro que faça isso;
- a VM continua usando `/etc/chatbot/chatbot.env`; não criar `.env.dev` nela.

## 11. Fase F — preparar a Meta

### 11.1 Comprar e conservar o número

- comprar chip/eSIM sob controle da equipe;
- confirmar que recebe SMS ou ligação;
- preferir número sem WhatsApp pessoal/Business ativo;
- manter a linha ativa mesmo depois da verificação;
- não instalar WhatsApp no número usado pela Cloud API;
- guardar os dados de recuperação fora do Git.

### 11.2 Usuário de sistema e token DEV

No Portfólio Empresarial:

1. criar usuário do sistema `chatbot-dev`;
2. atribuir o App atual;
3. atribuir somente a WABA `Supera teste`;
4. não atribuir as WABAs SAJ/Rio de produção;
5. gerar token para o mesmo App com
   `whatsapp_business_messaging` e
   `whatsapp_business_management`;
6. guardar o token somente em `.env.dev` ou em gerenciador de segredos.

Um usuário e token próprios limitam o impacto de vazamento, revogação ou erro
no ambiente DEV. Não anular os tokens do usuário de produção durante essa
configuração.

### 11.3 Cadastrar o número

Na WABA `Supera teste`:

1. adicionar o número DEV;
2. confirmar posse por SMS ou ligação;
3. registrar o PIN de verificação em duas etapas;
4. anotar de modo privado o WABA ID e o Phone Number ID;
5. confirmar que o número aparece dentro de `Supera teste`;
6. não enviar mensagens de teste ainda.

Para uma segunda unidade DEV, repetir em uma segunda WABA DEV. Não reutilizar a
mesma WABA devido ao contrato atual `unidade.waba_id UNIQUE`.

### 11.4 Cadastrar a unidade DEV no sistema

Somente depois de o processo Django estar usando token, banco e Redis DEV:

1. acessar `http://127.0.0.1:8000/admin/`, nunca o Admin pelo ngrok;
2. criar a unidade com WABA ID e Phone Number ID DEV;
3. manter integração do Funil inativa;
4. usar links de teste;
5. observar os logs da validação WABA/número, assinatura e registro;
6. confirmar a atualização do cache de unidades.

O formulário atual executa chamadas reais à Meta antes de salvar. Se o token
DEV não estiver correto, interromper e corrigir a configuração; não tentar com
o token de produção.

## 12. Fase G — iniciar localmente e publicar pelo ngrok

### 12.1 Preparar Python

Na raiz do projeto:

```powershell
py -3.12 -m venv venv
./venv/Scripts/Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
$env:CHATBOT_ENV = "development"
```

Não acrescentar ao `requirements.txt` dependências exclusivas de empacotamento
ou ferramentas que não fazem parte do runtime do servidor.

### 12.2 Validar antes de abrir o túnel

```powershell
python -m unittest discover -s tests -t . -p "test_*.py"
python callback/manage.py check
```

Executar também o futuro preflight. Ele deve mostrar explicitamente
`development`, `db_chatbot_dev`, role DEV, Redis DEV e Funil desativado. Se
qualquer item apontar para produção, não iniciar o webhook.

### 12.3 Processos DEV

Terminal 1 — webhook:

```powershell
$env:CHATBOT_ENV = "development"
python callback/manage.py runserver 127.0.0.1:8000
```

Terminal 2 — worker de fluxo:

```powershell
$env:CHATBOT_ENV = "development"
python -m workers.worker_flow.iniciar_flow_worker
```

Não iniciar `workers.worker_funil.iniciar_worker_funil` em DEV.

Terminal 3 — ngrok, usando o domínio estável atribuído à conta:

```powershell
ngrok http 8000 --url https://<DOMINIO_NGROK>
```

O authtoken do ngrok deve ser configurado localmente conforme a documentação do
ngrok e nunca incluído neste repositório.

### 12.4 Configurar o callback alternativo da WABA DEV

Pré-condições:

- Django respondendo localmente;
- ngrok encaminhando para a porta 8000;
- somente `/webhook` público;
- `.env.dev` contém o mesmo verify token que será informado à Meta;
- WABA ID confirmado como `Supera teste`;
- nenhum ID de WABA de produção selecionado.

No Explorador da Graph API, selecionar o App atual e usar o token DEV. Enviar:

```text
POST /<WABA_DEV_ID>/subscribed_apps
```

Corpo JSON:

```json
{
  "override_callback_uri": "https://<DOMINIO_NGROK>/webhook",
  "verify_token": "<META_WEBHOOK_VERIFY_TOKEN_DEV>"
}
```

Usar a versão Graph configurada no projeto. A Meta fará um GET de verificação
no endpoint DEV. Depois consultar:

```text
GET /<WABA_DEV_ID>/subscribed_apps
```

O retorno deve mostrar o `override_callback_uri` do ngrok para a WABA DEV.
Conferir novamente essa resposta após qualquer alteração da unidade pelo Admin,
pois o Admin também assina a WABA.

Não executar essa operação em WABA SAJ/Rio de produção. A substituição é por
WABA e todos os números daquela WABA seguem o callback alternativo.

### 12.5 Pausar o ambiente com segurança

Para uma pausa longa, desassinar somente a WABA DEV antes de desligar o túnel:

```text
DELETE /<WABA_DEV_ID>/subscribed_apps
```

Depois parar worker, Django, ngrok e Redis DEV. Não “remover apenas o override”
deixando a WABA assinada, porque ela poderia voltar ao callback padrão do App,
que é o webhook de produção.

Ao retomar, iniciar toda a infraestrutura e repetir o POST com
`override_callback_uri`. Nunca usar o botão **Remover assinatura** do callback
padrão do App.

## 13. Primeiro teste ponta a ponta

Executar nesta ordem:

1. confirmar preflight DEV;
2. confirmar `FUNIL_WORKER_ENABLED=False`;
3. confirmar `GET /<WABA_DEV_ID>/subscribed_apps` com URL ngrok;
4. enviar uma mensagem de um telefone pessoal para o número DEV;
5. verificar HTTP 200 no ngrok e nos logs Django;
6. confirmar inserção apenas em `db_chatbot_dev.chatbot.fila_mensagens`;
7. confirmar consumo pelo worker DEV;
8. confirmar resposta enviada pelo número DEV;
9. conferir histórico e conversa somente no banco DEV;
10. aceitar que o fluxo crie uma linha `pending` em `funil_envios`, mas
    confirmar que nenhuma ficou `sent` e que nenhuma chamada HTTP ao Funil foi
    realizada;
11. fazer uma consulta somente leitura na produção e confirmar que seus
    contadores não mudaram por causa do teste;
12. testar uma conversa completa antes de liberar o ambiente para trabalho
    diário.

Cenários mínimos de regressão:

- titular menor de 60 anos;
- titular 60+ com `suporte_idoso` ativo e inativo;
- dependente nas faixas previstas;
- unidade com `email_obrigatorio` ativo e inativo;
- e-mail válido, “não tenho” nos casos permitidos e resposta inválida;
- triagem, pesquisa de satisfação e encerramento;
- bloqueio, reentrega e mensagem duplicada;
- mídia e tipos de mensagem não suportados;
- duas unidades, somente quando houver duas WABAs DEV independentes.

## 14. Rotina diária de desenvolvimento

### Início

1. atualizar `develop` com `git pull --ff-only`;
2. abrir/criar a `feature/*`;
3. iniciar Redis DEV;
4. ativar venv e `CHATBOT_ENV=development`;
5. executar preflight e testes rápidos;
6. iniciar Django, worker e ngrok;
7. aplicar/confirmar o override da WABA DEV;
8. conferir assinatura antes de enviar mensagens.

### Durante o trabalho

- nunca colocar condicionais de branch no runtime;
- toda mudança de schema recebe baseline atualizado e migração incremental;
- toda regra de negócio recebe testes;
- não ativar Funil para “ver se funciona” sem um destino CRM de teste;
- não usar WABA, número, Redis ou credencial de produção;
- não abrir o Admin pelo domínio ngrok;
- revisar o inspetor do ngrok sem copiar payloads pessoais para documentação.

### Encerramento

1. terminar os testes em andamento;
2. pausar/desassinar a WABA DEV se o ambiente ficará offline;
3. parar worker, Django e ngrok;
4. parar Redis DEV se desejado;
5. verificar `git status -sb`;
6. confirmar que `.env.dev`, logs e dumps não entraram no Git.

## 15. Evolução do banco e migrações

Para cada alteração de banco:

1. atualizar o DDL final em `core/database/deploy_database/` para instalações
   novas;
2. criar SQL incremental em `deploy/migrations/` para bancos existentes;
3. tornar o SQL verificável, transacional e reexecutável quando possível;
4. aplicar primeiro no banco DEV;
5. executar suíte e teste ponta a ponta;
6. documentar pré-condições, pós-condições e rollback;
7. só então incluir a migração no plano de release para produção.

Não executar `setup_database.py` como substituto de migração em um banco já
existente. Não transportar dados DEV para produção.

## 16. Promoção de DEV para produção

### 16.1 Preparar a release

1. congelar merges em `develop` durante a validação final;
2. garantir worktree limpo;
3. revisar `git diff prod...develop` e `git log prod..develop`;
4. executar a suíte completa;
5. executar `manage.py check` e testes ponta a ponta em DEV;
6. conferir todas as migrações incrementais;
7. confirmar que nenhum segredo, `.env.dev`, dump ou URL temporária está no
   diff;
8. atualizar versão e documentação conforme a política do projeto;
9. abrir PR `develop -> prod`.

### 16.2 Por que o merge não troca configurações

- `.env.dev` não é versionado;
- `/etc/chatbot/chatbot.env` está fora do repositório;
- produção não consulta a branch para decidir recursos;
- a VM recebe `CHATBOT_ENV=production` e continua usando seus próprios valores;
- o callback padrão continua sendo o domínio de produção;
- ngrok e credenciais DEV não fazem parte do commit.

Assim, promover a release significa promover **código e migrações**, não
copiar a configuração DEV.

### 16.3 Deploy

Seguir o procedimento canônico em
[`regras_deploy/rotina_deploy.md`](regras_deploy/rotina_deploy.md) e as
instruções de [`deploy/README.md`](deploy/README.md).

Resumo dos gates:

1. snapshot/backup quando houver alteração de banco;
2. confirmar `prod...origin/prod` e revisar arquivos;
3. parar os processos exigidos pela compatibilidade da release;
4. aplicar migração no banco real somente após conferência do alvo;
5. executar `manage.py check --deploy`;
6. executar suíte completa;
7. iniciar webhook e verificar HTTP 200;
8. iniciar workers;
9. conferir `ActiveState`, `SubState`, `NRestarts` e journal;
10. realizar smoke test controlado.

O arquivo de produção deve declarar `CHATBOT_ENV=production` antes do primeiro
deploy que torne a variável obrigatória. O marcador do banco production também
deve existir antes de ativar o novo preflight.

### 16.4 Hotfix e sincronização

Depois de um hotfix em `prod`, incorporar o mesmo commit a `develop` por PR ou
merge revisado. Nunca resolver divergência copiando arquivos inteiros de uma
branch antiga sobre a nova, pois isso pode reintroduzir código obsoleto.

## 17. Rollback e contenção

### Incidente DEV envolvendo a Meta

1. desassinar somente a WABA DEV;
2. parar worker e webhook DEV;
3. preservar logs sem expor tokens;
4. consultar produção sem alterá-la;
5. corrigir e repetir preflight antes de reativar.

### DEV apontou para banco ou Redis errado

1. parar imediatamente todos os processos DEV;
2. não executar limpeza, reparo ou retry;
3. identificar operações pelos logs e horários;
4. tratar como incidente de produção se o recurso real foi alcançado;
5. rotacionar credenciais se houve exposição.

### Recriar DEV

Banco e Redis DEV podem ser descartáveis, mas a exclusão deve ser manual,
confirmando nomes absolutos e identidade `development`. Nunca oferecer um
comando genérico que calcule e apague banco/schema a partir de variável não
validada.

## 18. Checklist de aceite do ambiente

- [ ] `CHATBOT_ENV` é obrigatório e fail-closed.
- [ ] produção possui marcador `production` e DEV possui `development`.
- [ ] preflight testa banco, usuário, Redis e Funil.
- [ ] role DEV não acessa o banco de produção.
- [ ] Redis DEV é independente e não compartilha chaves com produção.
- [ ] `setup_database.py` não altera a role `fushi` nem limpa Redis real.
- [ ] `.env.dev` está ignorado e não contém valor de produção além dos itens
      inerentes ao mesmo App Meta.
- [ ] usuário/token Meta DEV acessa somente WABA DEV.
- [ ] WABA `Supera teste` possui apenas o número da unidade DEV correspondente.
- [ ] callback padrão do App continua em produção.
- [ ] WABA DEV mostra o override do ngrok.
- [ ] ngrok publica somente `/webhook`.
- [ ] assinatura Meta é obrigatória.
- [ ] Admin é usado somente por localhost.
- [ ] Funil permanece desativado.
- [ ] suíte completa passa.
- [ ] mensagem ponta a ponta escreve somente no banco DEV.
- [ ] fluxo de PR `feature -> develop -> prod` está definido.
- [ ] hotfixes de `prod` retornam para `develop`.
- [ ] deploy segue o runbook existente.

## 19. Próximos passos na ordem correta

1. implementar e testar os guardas da Fase A;
2. criar/proteger a branch `develop`;
3. criar role e banco DEV na mesma instância RDS;
4. preparar Redis DEV;
5. criar `.env.dev` e executar o bootstrap;
6. comprar e verificar o chip/número;
7. criar usuário de sistema e token Meta DEV;
8. cadastrar a unidade DEV;
9. iniciar Django e ngrok;
10. aplicar o override somente à WABA `Supera teste`;
11. executar o teste ponta a ponta;
12. só depois usar o ambiente no desenvolvimento cotidiano.

Os passos 6 a 10 ficam aguardando a compra do chip. As fases de código, Git,
banco e Redis podem ser planejadas antes, mas nenhuma integração Meta deve ser
ativada pela metade.

## 20. Referências externas

- [AWS — uma instância RDS pode conter múltiplos bancos criados pelo usuário](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/Overview.DBInstance.html)
- [AWS — conexão com RDS PostgreSQL](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/USER_ConnectToPostgreSQLInstance.psql.html)
- [Meta — callback alternativo por WABA](https://www.postman.com/meta/whatsapp-business-platform/request/un84tul/override-callback-url)
- [Meta — assinaturas de webhook por WABA](https://www.postman.com/meta/whatsapp-business-platform/folder/ozgs3jn/webhook-subscriptions)
- [Meta — registro e verificação do número](https://www.postman.com/meta/whatsapp-business-platform/folder/zuoeksl/registration)
- [ngrok — CLI e endpoint HTTP](https://ngrok.com/docs/agent/cli)
- [GitHub — branches e proteção](https://docs.github.com/en/enterprise-cloud%40latest/pull-requests/reference/branches)
