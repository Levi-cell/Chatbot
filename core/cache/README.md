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
    ├── cache_flood_redis.py
    └── cache_webhook_erro_inesperado.py
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

O cliente exige Redis remoto: recusa loopback, endereço indefinido e IP da
própria máquina. Endereços privados de outra máquina são aceitos. O fallback
em memória descrito abaixo não é um servidor Redis local.

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

Esse cache é global por cliente, não por unidade, e tem TTL de 180 dias. Se um
ID obsoleto provocar a violação `conversa_id_cliente_fkey`, o `flow_worker`
tenta remover a entrada para que o próximo retry consulte o banco novamente.

## Unidade

`cache_unidade.py` mantém o mapa `phone_number_id -> id_unidade` e metadados de
versão. As consultas que carregam ou confirmam esse mapa consideram somente
unidades com `status_pagamento = TRUE`; `bpa_ativo` não é o filtro de admissão.

```text
cache válido e unidade presente -> usa Redis
cache ausente/inválido ou Redis indisponível -> consulta banco
divergência de versão -> tenta recarregar
FK de unidade obsoleta detectada -> tenta recarregar para o retry
```

No webhook, um phone ID ausente mesmo em cache válido é confirmado no banco;
se a unidade existir, tenta recarregar o mapa. Se a confirmação no banco
falhar, levanta `ValidacaoUnidadeIndisponivel`, convertida em HTTP 503. Já o
worker lança `UnidadeNaoEncontrada` quando o mapa válido não contém um ID
válido para o phone solicitado, sem consultar o banco nesse caminho.

A versão persistida é conferida no primeiro uso, a cada 300 segundos por
processo e após falha Redis sinalizada. Falha nessa conferência mantém o
cache atual; não há garantia de detectar edição manual que preserve a
contagem e não altere a versão.

O Django Admin incrementa a versão persistida quando uma unidade muda. Falha no
preflight do Redis bloqueia a alteração administrativa prevista.

## Conversa bloqueada

`runtime/cache_conversas_bloqueadas.py` acelera o bloqueio após encerramento,
com TTL calculado a partir de `finalizou_em` e `bloqueio_dias` da política da
etapa; a duração não é fixa dentro do módulo. Se Redis falhar, consulta o
banco e tenta reparar o cache. Um miss normal no Redis retorna `False` sem
essa consulta. Se Redis e banco falharem, levanta
`ValidacaoBloqueioConversaIndisponivel`, convertida em HTTP 503 no webhook.

O par da chave é cliente e unidade. Esse bloqueio de conversa não é o mesmo que
bloqueio de usuário na Meta.

## Flood

`runtime/cache_flood_redis.py` é a primeira camada do rate limit. A chave combina:

```text
wa_id_cliente + phone_id_unidade
```

Clientes diferentes da mesma unidade não compartilham contagem.

O Redis usa janela fixa e deduplica o WAMID por duas horas; a deduplicação e o
incremento dos contadores são uma única operação Lua atômica. A regra atual
do webhook é 15 WAMIDs distintos em cinco segundos. Em falha Redis, o
webhook tenta o contador do banco antes da memória.

`cache_flood_memoria.py` é a última barreira quando Redis e banco falham. É local
ao processo, limitada e não substitui Redis em ambiente com múltiplas instâncias.

## Erro inesperado do webhook

`runtime/cache_webhook_erro_inesperado.py` mantém um contador Redis por WAMID
para o tratamento genérico de exceções do POST. Permite três respostas 503;
da quarta ocorrência em diante, o webhook retorna 200 e ignora o evento. O
TTL de sete dias é renovado a cada incremento.

Sem WAMID ou com contador Redis indisponível, esse tratamento também retorna
200, sem fallback de contagem no banco ou em memória. Os 503 específicos de
validação e persistência não usam esse limite.

## Follow-up e cache

O estado do follow-up não fica no Redis. Elegibilidade, lock, recibos e retomadas
são lidos/persistidos diretamente no PostgreSQL. Limpar caches não zera
`followup_stage` nem remove os registros de envio. O proativo consulta os
bloqueios e eventos de flood persistidos no banco; o webhook mantém a cadeia
Redis/banco/memória descrita acima.

## Reset de desenvolvimento

`cache_reset.py` conserva o reset dos caches do chatbot usado pelo setup de
desenvolvimento: remove as chaves do mapa de unidades e os prefixos
operacionais e tenta recarregar o mapa. Não executa `FLUSHDB`. Comandos manuais
ficam em
[`utilitarios/maintenance/cache_reset.py`](../../utilitarios/maintenance/cache_reset.py).

## Reset operacional de produção

Após uma remoção planejada de clientes e conversas do banco, o modo
`--operacional` limpa os caches operacionais com as variáveis de produção
carregadas. O cliente aceita somente Redis remoto; não utiliza servidor
Redis na própria VM:

```bash
cd /opt/chatbot/app
sudo -u chatbot env -i PYTHONPATH=/opt/chatbot/app /opt/chatbot/venv/bin/python -m utilitarios.maintenance.cache_reset --env-file /etc/chatbot/chatbot.env --operacional --confirmar
```

Esse modo remove somente os prefixos `cliente_cache:`,
`conversa_bloqueada:`, `webhook_flood_rate:` e
`webhook_erro_inesperado:`. O mapa de unidades, suas chaves
de versão e outras configurações do Redis permanecem intactos. O comando falha
com código diferente de zero se o Redis estiver indisponível. Excluir chaves
já ausentes é idempotente, mas uma nova execução também apaga estado
operacional criado desde a execução anterior.

O modo `--unidades` reconstrói somente o mapa de unidades a partir do banco.
Todos os modos manuais exigem `--confirmar`.

Para apagar exclusivamente bloqueios temporários de conversa, use o modo
`--bloqueios` conforme o comando protegido em
[`regras_deploy/servicos_e_redis_remoto.md`](../../regras_deploy/servicos_e_redis_remoto.md).

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`.

Esses arquivos cobrem o núcleo transacional; consulte também
[`tests/README.md`](../../tests/README.md).
