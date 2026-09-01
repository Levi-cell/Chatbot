# Rotina de deploy da branch `prod`

Este é o procedimento canônico para publicar uma atualização comum do projeto
na instância Lightsail.

Ambiente atual:

- repositório na VM: `/opt/chatbot/app`;
- ambiente virtual: `/opt/chatbot/venv`;
- configuração de produção: `/etc/chatbot/chatbot.env`;
- webhook público: `https://webhook.3esltech.com/webhook`;
- branch de produção: `prod`.

## Regra dos três serviços

| Serviço | Papel | Ação no deploy comum |
|---|---|---|
| `chatbot-webhook.service` | Recebe a Meta e grava na fila | Permanece atendendo; recebe `HUP` depois da atualização |
| `chatbot-worker-flow.service` | Processa o fluxo do atendimento | Para antes do `git pull` e inicia depois das validações |
| `chatbot-worker-funil.service` | Envia oportunidades ao Funil | Para antes do `git pull` e inicia depois das validações |

O webhook continuar ativo permite que novas mensagens sejam persistidas na
fila enquanto os workers estão parados. Elas serão processadas quando o worker
de fluxo voltar.

### Correção importante sobre o webhook

O auto-reload é comportamento do servidor de desenvolvimento do Django. Em
produção, o projeto usa Gunicorn sem `--reload`; portanto, um `git pull` sozinho
**não** carrega o novo código no webhook.

No deploy comum, não é necessário interromper o endpoint. Envie `HUP` ao
processo principal do Gunicorn: ele cria workers com o código novo e encerra os
antigos graciosamente.

Mudança em `.env` ou na unit systemd do webhook é exceção: exige `restart`, pois
o processo principal precisa reler seu ambiente ou sua definição de serviço.

## Comandos rápidos para parar e iniciar somente os workers

Parar:

```bash
sudo systemctl stop chatbot-worker-flow.service chatbot-worker-funil.service
```

Iniciar:

```bash
sudo systemctl start chatbot-worker-flow.service chatbot-worker-funil.service
```

Verificar:

```bash
systemctl is-active chatbot-webhook.service
systemctl is-active chatbot-worker-flow.service chatbot-worker-funil.service
```

Durante a atualização, o resultado esperado é `active` para o webhook e
`inactive` para os dois workers. `inactive` faz `systemctl is-active` retornar
um código diferente de zero; nesse ponto isso é esperado, não uma falha.

## 1. Sincronizar a `prod` antes de começar uma alteração

Execute no PowerShell, na raiz do projeto local, antes de iniciar o trabalho:

```powershell
git switch prod
git status --short
git pull --ff-only origin prod
```

O `git status --short` deve estar vazio antes do `pull`. Se houver arquivos
alterados, primeiro revise e preserve o trabalho; não use `reset --hard` para
forçar a sincronização.

## 2. Testar e publicar a atualização no GitHub

Depois de concluir as alterações, ainda no computador local:

```powershell
git branch --show-current
git status --short
python -m unittest discover -s tests -t . -p "test_*.py"
git diff --check

git add -A
git diff --cached --name-status
git diff --cached --check
git diff --cached --stat

git commit -m "Descreva objetivamente a atualizacao"
git push origin prod
git status -sb
```

Antes do commit, confira a lista de arquivos preparada por
`git diff --cached --name-status`. Nunca publique `.env`, tokens,
senhas, certificados ou dumps do banco.

O `-u` não é necessário no `git push`: a `prod` já acompanha `origin/prod`.
Usá-lo novamente não costuma causar problema, mas não acrescenta nada à rotina.

Anote o commit publicado para conferi-lo na VM:

```powershell
git rev-parse --short HEAD
```

## 3. Parar os workers na Lightsail

Execute no terminal Ubuntu da Lightsail:

```bash
sudo systemctl stop chatbot-worker-flow.service chatbot-worker-funil.service

systemctl is-active chatbot-webhook.service
systemctl is-active chatbot-worker-flow.service chatbot-worker-funil.service
```

Não continue se o webhook não estiver `active`.

## 4. Atualizar o checkout da VM

```bash
cd /opt/chatbot/app

git status --short
git fetch origin
git checkout prod
git pull --ff-only origin prod
git rev-parse --short HEAD
```

Regras:

- `git status --short` deve estar vazio antes do `pull`;
- o hash final deve ser o mesmo publicado no computador local;
- se a VM estiver com alteração local, pare e investigue. Não apague a mudança
  com `reset`, `checkout --` ou remoção de arquivo sem saber sua origem.

## 5. Atualizar dependências e validar o Django

```bash
/opt/chatbot/venv/bin/pip install -r /opt/chatbot/app/requirements.txt

sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py check --deploy'

sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py migrate --noinput'

sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app PYTHONDONTWRITEBYTECODE=1; /opt/chatbot/venv/bin/python callback/manage.py collectstatic --noinput'
```

O `EnvironmentFile` das units não é herdado pela sessão SSH. Esses comandos
carregam explicitamente `/etc/chatbot/chatbot.env`; não use `cat`, `env` ou outro
comando que imprima seus valores.

`manage.py migrate` cuida das tabelas internas gerenciadas pelo Django. As
tabelas de negócio `chatbot.*` usam modelos `managed = False` e seguem o fluxo
de DDL e `ALTER` descrito em
[modificando_env_e_banco_em_prod.md](modificando_env_e_banco_em_prod.md).

Se o deploy incluir uma alteração de schema, o `ALTER` compatível já deve ter
sido aplicado e validado no RDS antes de carregar código que dependa dele.

## 6. Atualizar units systemd, quando necessário

Se `deploy/systemd/chatbot-worker-flow.service` ou
`deploy/systemd/chatbot-worker-funil.service` mudou:

```bash
sudo install -m 0644 \
  /opt/chatbot/app/deploy/systemd/chatbot-worker-flow.service \
  /etc/systemd/system/chatbot-worker-flow.service

sudo install -m 0644 \
  /opt/chatbot/app/deploy/systemd/chatbot-worker-funil.service \
  /etc/systemd/system/chatbot-worker-funil.service

sudo systemctl daemon-reload
sudo systemd-analyze verify \
  /etc/systemd/system/chatbot-worker-flow.service \
  /etc/systemd/system/chatbot-worker-funil.service
```

Se a unit `chatbot-webhook.service` mudou, instale-a, execute
`systemctl daemon-reload` e faça `restart` do webhook. Um `HUP` não aplica uma
nova unit systemd.

## 7. Recarregar o código do webhook sem derrubar o endpoint

```bash
sudo systemctl kill \
  --signal=HUP \
  --kill-who=main \
  chatbot-webhook.service

sleep 3

systemctl is-active chatbot-webhook.service
sudo systemctl show chatbot-webhook.service \
  -p ActiveState -p SubState -p MainPID -p NRestarts --no-pager

curl --fail --silent --show-error \
  https://webhook.3esltech.com/webhook

sudo journalctl -u chatbot-webhook.service \
  --since "5 minutes ago" --no-pager
```

O `curl` deve retornar `Webhook ativo`, e o serviço deve permanecer `active` e
`running`. O journal do Gunicorn deve registrar o recebimento do sinal e a
substituição graciosa dos workers.

Se o `HUP` falhar ou o novo código não carregar, use o fallback abaixo. Haverá
uma interrupção curta, e por isso o health check deve ser repetido em seguida:

```bash
sudo systemctl restart chatbot-webhook.service
systemctl is-active chatbot-webhook.service
curl --fail --silent --show-error https://webhook.3esltech.com/webhook
```

## 8. Iniciar e verificar os workers

Somente depois de o webhook e o banco estarem validados:

```bash
sudo systemctl start chatbot-worker-flow.service chatbot-worker-funil.service

systemctl is-active \
  chatbot-webhook.service \
  chatbot-worker-flow.service \
  chatbot-worker-funil.service

sudo systemctl show \
  chatbot-webhook.service \
  chatbot-worker-flow.service \
  chatbot-worker-funil.service \
  -p Id -p ActiveState -p SubState -p NRestarts --no-pager

sudo journalctl \
  -u chatbot-worker-flow.service \
  -u chatbot-worker-funil.service \
  --since "5 minutes ago" --no-pager
```

Resultados esperados:

- os três serviços em `active` / `running`;
- worker de fluxo iniciando ciclos sem erro de banco, Redis ou Meta;
- worker do Funil concluindo o ciclo e informando o próximo ciclo conforme
  `FUNIL_INTERVALO_SEGUNDOS` (padrão atual: 30 minutos);
- ausência de crescimento contínuo de `NRestarts`.

## 9. Casos que não são um deploy comum

| Mudança | Procedimento adicional |
|---|---|
| Somente código Python | `HUP` gracioso no Gunicorn |
| `.env` de produção | `restart` dos serviços afetados; o Gunicorn não relê o EnvironmentFile por `HUP` |
| Unit systemd | instalar a unit, `daemon-reload` e reiniciar o serviço afetado |
| Nginx | `nginx -t` antes de `systemctl reload nginx` |
| Schema compatível/aditivo | aplicar primeiro o `ALTER` validado no DBeaver |
| Rename, drop, mudança de tipo ou `NOT NULL` incompatível | usar migração expand/contract ou janela de manutenção |

Manter o webhook ativo pressupõe que a mudança seja compatível com a versão que
está atendendo durante os poucos minutos do deploy. Alterações destrutivas de
banco não devem ser improvisadas nesse fluxo.

## 10. Se algo falhar

1. Mantenha os dois workers parados. O webhook saudável continuará enfileirando.
2. Consulte os journals e corrija a causa antes de reiniciá-los.
3. Para voltar código, faça `git revert` do commit no computador local, teste,
   publique o novo commit na `prod` e repita o deploy. Não reescreva o histórico
   da `prod` e não force um estado antigo diretamente na VM.
4. Se o webhook também estiver indisponível, priorize restaurá-lo e valide o
   endpoint público antes de qualquer worker.

Comandos de diagnóstico:

```bash
sudo journalctl -u chatbot-webhook.service -n 200 --no-pager
sudo journalctl -u chatbot-worker-flow.service -n 200 --no-pager
sudo journalctl -u chatbot-worker-funil.service -n 200 --no-pager
sudo nginx -t
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python -c "from core.cache.redis_client import get_redis; r=get_redis(); print(\"REDIS_PING=\", r.ping()); print(\"REDIS_DESTINO=\", r.connection_pool.connection_kwargs.get(\"host\"), r.connection_pool.connection_kwargs.get(\"port\"))"'
```

O ultimo comando usa o Redis definido no ambiente da aplicacao. Nao use
`redis-cli ping` sem host: ele consulta `127.0.0.1:6379` e nao valida o Redis
remoto de producao. Consulte tambem
[`servicos_e_redis_remoto.md`](servicos_e_redis_remoto.md).
