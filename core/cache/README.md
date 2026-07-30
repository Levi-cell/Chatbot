# Cache

Camada de Redis, cache local, fallback e reparo detectável.

- [Portal do projeto](../../README.md)
- [Regras de negócio](../../REGRAS_DE_NEGOCIO.md#18-cache-fallback-e-autocura)
- [Padrões de arquitetura](../../PADROES_DE_ARQUITETURA.md#cache)

## Arquivos

```text
core/cache/
├── redis_client.py
├── cache_unidade.py
├── cache_flood_memoria.py
├── cache_reset.py
└── runtime/
    ├── cache_cliente.py
    ├── cache_conversas_bloqueadas.py
    └── cache_flood_redis.py
```

`redis_client.py` lê a configuração por `core/config_env.py`:

```text
REDIS_HOST
REDIS_PORT
REDIS_USERNAME
REDIS_PASSWORD
REDIS_SSL
```

Esses valores devem vir de `.env` local, variáveis do ambiente de produção ou
gerenciador de segredos. Não coloque credenciais Redis diretamente no código.

## Princípios

- PostgreSQL continua sendo a fonte persistida da verdade;
- Redis acelera consultas, não controla regras sozinho;
- indisponibilidade ou valor inválido deve ser registrado;
- o fallback usado depende do domínio;
- autocura cobre divergências detectáveis, não edição manual arbitrária;
- cache não executa commit ou rollback de transações pertencentes a outro fluxo.

## Cliente

`runtime/cache_cliente.py` relaciona `wa_id` ao `id_cliente`. Miss ou falha do
Redis permite consulta/criação pelo worker. Valor inválido é descartado.

Se um ID stale provocar violação de FK, o `flow_worker` remove a entrada para que
o próximo retry consulte o banco novamente.

## Unidade

`cache_unidade.py` mantém o mapa `phone_number_id -> id_unidade` e metadados de
versão.

```text
cache válido -> usa Redis
cache ausente/inválido -> consulta banco
divergência de versão -> tenta recarregar
FK stale detectada -> remove/recarrega no retry
```

O Django Admin incrementa a versão persistida quando uma unidade muda. Falha no
preflight do Redis bloqueia a alteração administrativa prevista.

## Conversa bloqueada

`runtime/cache_conversas_bloqueadas.py` acelera a janela de 30 dias após a etapa
final. Se Redis falhar, consulta o banco e tenta reparar o cache.

O par da chave é cliente e unidade. Esse bloqueio de conversa não é o mesmo que
bloqueio de usuário na Meta.

## Flood

`runtime/cache_flood_redis.py` é a primeira camada do rate limit. A chave combina:

```text
wa_id_cliente + phone_id_unidade
```

Clientes diferentes da mesma unidade não compartilham contagem.

`cache_flood_memoria.py` é a última barreira quando Redis e banco falham. É local
ao processo, limitada e não substitui Redis em ambiente com múltiplas instâncias.

## Reset de desenvolvimento

`cache_reset.py` conserva apenas o reset completo usado pelo setup de
desenvolvimento. Comandos manuais ficam em
[`operations/maintenance/cache_reset.py`](../../operations/maintenance/cache_reset.py).

## Reset operacional de produção

Quando clientes e conversas forem removidos do banco, execute o modo
`--operacional` uma única vez com as variáveis do ambiente de produção
carregadas. O Redis de produção é remoto; não existe servidor Redis local na
VM:

```bash
cd /opt/chatbot/app
sudo -u chatbot bash -c 'set -a; source /etc/chatbot/chatbot.env; set +a; cd /opt/chatbot/app; export PYTHONPATH=/opt/chatbot/app; /opt/chatbot/venv/bin/python -m operations.maintenance.cache_reset --operacional'
```

Esse modo remove somente os prefixos `cliente_cache:`,
`conversa_bloqueada:`, `webhook_flood_rate:` e
`webhook_erro_inesperado:`. O mapa de unidades, suas chaves
de versão e outras configurações do Redis permanecem intactos. O comando falha
com código diferente de zero se o Redis estiver indisponível e pode ser
repetido com segurança.

Para apagar exclusivamente bloqueios de 30 dias, siga o comando protegido em
[`regras_deploy/servicos_e_redis_remoto.md`](../../regras_deploy/servicos_e_redis_remoto.md).

## Testes relacionados

- `tests/unit/test_cache_essencial.py`;
- `tests/unit/test_cache_reset_operacional.py`;
- `tests/unit/test_flood_guard.py`;
- `tests/unit/test_retry_essencial.py`.
