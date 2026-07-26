# Servicos da VM e Redis remoto

Este e o procedimento canonico para operar os tres processos do chatbot e o
Redis de producao.

## Regra de arquitetura

Na producao, o sistema usa **somente o Redis remoto**. O arquivo
`core/cache/redis_client.py` cria a conexao com as variaveis abaixo, carregadas
de `/etc/chatbot/chatbot.env` pelas units do `systemd`:

- `REDIS_HOST`;
- `REDIS_PORT`;
- `REDIS_USERNAME`;
- `REDIS_PASSWORD`;
- `REDIS_SSL`.

`REDIS_HOST` nao pode ser `localhost`, `127.0.0.1` ou `::1` na VM. Um comando
manual Python tambem precisa carregar `/etc/chatbot/chatbot.env`; abrir uma
sessao SSH nao carrega esse arquivo automaticamente.

Nao use `redis-cli ping` sem informar um host. Esse comando consulta o Redis
local padrao em `127.0.0.1:6379` e nao prova que a aplicacao alcanca o Redis
remoto.

## Parar os tres servicos

Execute na VM, um por vez:

```bash
sudo systemctl stop chatbot-webhook.service
sudo systemctl stop chatbot-worker-flow.service
sudo systemctl stop chatbot-worker-funil.service
```

## Iniciar os tres servicos

Execute na VM, um por vez:

```bash
sudo systemctl start chatbot-webhook.service
sudo systemctl start chatbot-worker-flow.service
sudo systemctl start chatbot-worker-funil.service
```

Confirme os tres estados:

```bash
systemctl is-active chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service
```

O resultado esperado sao tres linhas `active`.

## Confirmar que a aplicacao usa o Redis remoto

Este comando carrega o mesmo ambiente dos servicos, nao exibe a senha e
recusa explicitamente um endpoint local:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python -c "from core.cache.redis_client import get_redis; r=get_redis(); h=str(r.connection_pool.connection_kwargs.get(\"host\", \"\")).strip().lower(); assert h not in {\"localhost\", \"127.0.0.1\", \"::1\"}, f\"RECUSADO_REDIS_LOCAL={h}\"; print(\"REDIS_REMOTO_OK=\", r.ping()); print(\"DESTINO=\", h, r.connection_pool.connection_kwargs.get(\"port\"))"'
```

O resultado esperado contem `REDIS_REMOTO_OK= True` e o endpoint remoto.

## Limpar somente os clientes bloqueados no Redis remoto

Essa operacao apaga apenas chaves `conversa_bloqueada:*`. Ela nao apaga cache
de unidades, clientes, flood ou qualquer outra chave. Nao usa `FLUSHDB` nem
`FLUSHALL`.

Para impedir que uma chave seja recriada durante a manutencao, pare os tres
servicos primeiro. Em seguida, execute:

```bash
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python -c "from core.cache.redis_client import get_redis; r=get_redis(); h=str(r.connection_pool.connection_kwargs.get(\"host\", \"\")).strip().lower(); assert h not in {\"localhost\", \"127.0.0.1\", \"::1\"}, f\"RECUSADO_REDIS_LOCAL={h}\"; p=\"conversa_bloqueada:*\"; ks=list(r.scan_iter(match=p, count=500)); print(\"DESTINO=\", h, r.connection_pool.connection_kwargs.get(\"port\")); print(\"ANTES=\", len(ks)); print(\"REMOVIDAS=\", r.delete(*ks) if ks else 0); depois=sum(1 for _ in r.scan_iter(match=p, count=500)); print(\"DEPOIS=\", depois); raise SystemExit(0 if depois == 0 else 1)"'
```

O resultado obrigatorio e `DEPOIS= 0`. Depois, inicie novamente os tres
servicos com os comandos deste documento.

Importante: se o banco ainda possuir uma conversa encerrada dentro do periodo
de bloqueio, a regra de recuperacao do sistema pode recriar a chave. Para um
reset operacional completo, o banco e o Redis precisam representar o mesmo
estado.

## Remover o Redis local da VM

As units antigas do webhook e do worker-flow exigiam incorretamente
`redis-server.service`. Portanto, **nao remova o Redis local antes de instalar
as units corrigidas**.

Depois de atualizar `/opt/chatbot/app` pela branch `prod`, instale as tres
units atuais e recarregue o `systemd`:

```bash
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/chatbot-webhook.service /etc/systemd/system/chatbot-webhook.service
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/chatbot-worker-flow.service /etc/systemd/system/chatbot-worker-flow.service
sudo install -m 0644 /opt/chatbot/app/deploy/systemd/chatbot-worker-funil.service /etc/systemd/system/chatbot-worker-funil.service
sudo systemctl daemon-reload
sudo systemd-analyze verify /etc/systemd/system/chatbot-webhook.service /etc/systemd/system/chatbot-worker-flow.service /etc/systemd/system/chatbot-worker-funil.service
```

Confirme que nenhuma unit ainda depende do servidor local:

```bash
if systemctl show chatbot-webhook.service chatbot-worker-flow.service chatbot-worker-funil.service -p Requires -p After --no-pager | grep -q redis-server; then echo 'ABORTAR: ainda existe dependencia de redis-server'; exit 1; else echo 'OK: units sem Redis local'; fi
```

Execute tambem o teste `REDIS_REMOTO_OK` deste documento. Somente se os dois
testes passarem, remova o Redis local:

```bash
sudo systemctl disable --now redis-server.service
sudo apt-get purge -y redis-server redis-tools
sudo apt-get autoremove -y
```

O pacote Python `redis`, instalado em `/opt/chatbot/venv`, e independente dos
pacotes `redis-server` e `redis-tools` do Ubuntu e continuara disponivel.

Valide que nao existe servidor escutando localmente na porta 6379:

```bash
sudo ss -lntp | grep ':6379'
```

O resultado esperado e nenhuma linha. `systemctl status redis-server.service`
tambem deve informar que a unit nao foi encontrada.

Por fim, inicie os tres servicos e repita a verificacao
`REDIS_REMOTO_OK=True`.
