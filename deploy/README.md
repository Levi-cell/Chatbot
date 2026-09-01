# Implantacao no Lightsail

Os arquivos assumem a aplicacao em `/opt/chatbot/app`, o ambiente virtual em
`/opt/chatbot/venv` e as variaveis em `/etc/chatbot/chatbot.env`. Os tres
processos da aplicacao sao independentes e escrevem seus logs no journald.

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
validando o certificado do servidor. Depois, prepare o Django:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py migrate --noinput'
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
```

`EnvironmentFile` é carregado automaticamente somente pelo systemd. Uma sessão
SSH comum não recebe essas variáveis; os comandos manuais acima carregam o mesmo
arquivo privado dos serviços sem exibir seu conteúdo.

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

## Operacao dos servicos e do Redis remoto

Os comandos individuais para iniciar e parar cada processo, limpar somente os
bloqueios no Redis remoto e remover o servidor Redis local da VM estao em
[`regras_deploy/servicos_e_redis_remoto.md`](../regras_deploy/servicos_e_redis_remoto.md).

Nao exponha a porta `6379` e nao use `FLUSHDB` ou `FLUSHALL` em producao.
