# Implantação do Supera no Lightsail

Referência para instalações da última versão numerada, V1.20.0. O webhook serve a API, o Admin e o painel. O [inventário](../workers/README.md) descreve os seis workers, suas configurações e seus efeitos. O encerramento do desenvolvimento é um registro do repositório. O estado de uma VM deve ser verificado na própria instalação.

## Instalação inicial

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

## Serviços da aplicação

Os sete arquivos em [deploy/systemd](systemd) definem os executáveis, o usuário, o diretório e o arquivo de ambiente. A VM usa PostgreSQL e Redis remotos. Ao instalar ou alterar uma unidade, copiar o arquivo correspondente para `/etc/systemd/system/` e executar `systemctl daemon-reload`. Habilitar somente integrações configuradas para aquela instalação. A [rotina de deploy](../regras_deploy/rotina_deploy.md) registra a ordem de pausa e retomada.

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

## Banco existente

Usar a migração incremental correspondente à versão de origem e verificar seu resultado antes de iniciar o código dependente. Os [scripts históricos](migrations) incluem alternativas e consolidados para alguns releases. Executar o diretório inteiro em ordem de nome pode repetir mudanças. O setup declarativo é para instalações novas. Históricos específicos: [idade mínima](idade_minima_suporte.md), [regras comerciais e idade](filtro_comercial_regras_idade.md), [consumo Meta](consumo_mensal_meta.md) e [reserva com ou sem link](reserva_com_sem_link.md).

## Ativação do follow-up

Na atualização para V1.20.0, a [migração dos três follow-ups](migrations/20261029_tres_followups.sql) encerra conversas ainda abertas iniciadas até 29/10/2026 às 19h de Brasília, preserva histórico e contadores e registra o motivo sem bloqueio de 30 dias. Na instalação limpa, o DDL já cria a estrutura final. A unit do follow-up corresponde ao modelo de 15 minutos, 7 e 14 horas. Validar schema e executar `python -m utilitarios.verificar_followup` no ambiente configurado antes de reativar o serviço. Essa checagem é de leitura.

## FireAds e relatórios

A [integração](../docs/fireads.md) diferencia consulta de abertura, identificação periódica e entrega ao dashboard. Para o worker de origem, configurar o corte inicial com fuso em `FIREADS_ORIGEM_DESDE` e a habilitação em `FIREADS_ORIGEM_ATIVO`. Preservar o corte configurado entre reinícios. Os estáticos do painel são preparados por `collectstatic`. Conferir a leitura autenticada de Conversas, Relatórios e Consumo para uma unidade de teste. Um HTTP 200 na página de login verifica a rota pública.

Os procedimentos de ambiente e acesso ao banco estão no [guia de configuração](../regras_deploy/modificando_env_e_banco_em_prod.md).
