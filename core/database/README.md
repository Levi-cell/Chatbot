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
├── criar_particao.py
└── deploy/
    ├── setup_database.py
    ├── bank_script.py
    ├── cache_control_script.py
    ├── etapa_transicao_script.py
    ├── floodscript.py
    ├── turno_cliente_script.py
    └── povoar_etapas.py
```

## Runtime e deploy

- `connection_aws.py` fornece conexões para os orquestradores;
- `connection_check.py` valida acesso ao PostgreSQL;
- `deploy/` cria schema, tabelas, índices e funções;
- `criar_particao.py` é ferramenta manual para partições futuras do histórico;
- SQL de negócio executado durante atendimento fica em `core/repositories`.

## Setup

A partir da raiz:

```powershell
python -m core.database.deploy.setup_database
```

Ordem atual:

```text
healthcheck
-> timezone do role
-> tabelas e índices principais
-> controle de cache
-> tabelas de flood
-> índices de turno
-> função de dequeue
-> funções de lock
-> timeouts do role
-> seed de etapas
-> whitelist de transições de etapas
-> reset de cache de desenvolvimento
```

`povoar_etapas.py` mantém o catálogo de estados com IDs estáveis.
`etapa_transicao_script.py` mantém a whitelist executável de
`origem + evento -> destino`. Uma aresta só deve entrar no seed quando resolver,
sender, efeitos transacionais e testes estiverem prontos.

Cada função controla sua conexão e transação. Funções concluídas anteriormente
podem ter commit próprio; uma falha posterior não desfaz commits de funções
anteriores.

Os comandos utilizam `IF NOT EXISTS`, `CREATE OR REPLACE` ou `ON CONFLICT` onde
aplicável. Por isso, um setup interrompido normalmente pode ser executado de novo
sem apagar o banco. Consulte os logs: os scripts atuais registram falhas dentro
de cada função.

`IF NOT EXISTS` não migra uma estrutura criada por uma versão antiga. Evolução
de schema existente exige migração explícita ou decisão consciente de recriação
em desenvolvimento.

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
```

Novas credenciais não devem ser adicionadas ao código, README, logs ou prints.
Em desenvolvimento, use `.env` local baseado em `.env.example`. Em produção, use
variáveis do serviço, arquivo de ambiente com permissão restrita ou gerenciador
de segredos.

## Testes relacionados

- `tests/unit/test_deploy_contract.py`;
- `tests/unit/test_retry_lock_lifecycle.py`;
- `tests/unit/test_worker_flow_contract.py`.
