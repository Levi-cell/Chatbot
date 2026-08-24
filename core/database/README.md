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
└── deploy_database/
    ├── setup_database.py
    ├── bank_script.py
    ├── transacao_deploy.py
    ├── cache_control_script.py
    ├── etapa_transicao_script.py
    ├── floodscript.py
    ├── turno_cliente_script.py
    └── povoar_etapas.py
```

## Runtime e deploy

- `connection_aws.py` fornece conexões para os orquestradores;
- `connection_check.py` valida acesso ao PostgreSQL;
- `deploy_database/` cria schema, tabelas, índices e funções;
- partições mensais são mantidas pelo comando manual
  `utilitarios.maintenance.message_partitions`;
- SQL de negócio executado durante atendimento fica em `core/repositories`.

## Setup

A partir da raiz:

```powershell
python -m core.database.deploy_database.setup_database
```

Ordem atual:

```text
healthcheck
-> configuração única da role
-> schema principal final
-> controle de cache
-> tabelas de flood
-> índices de turno
-> função de dequeue
-> funções de lock
-> seed de etapas
-> whitelist de transições de etapas
-> reset de cache de desenvolvimento
```

`povoar_etapas.py` mantém o catálogo de estados com IDs estáveis.
`etapa_transicao_script.py` mantém a whitelist executável de
`origem + evento -> destino`. Uma aresta só deve entrar no seed quando resolver,
sender, efeitos transacionais e testes estiverem prontos.

`transacao_deploy.py` centraliza conexão, commit, rollback e fechamento. Uma
falha é relançada e interrompe o setup antes do log de finalização. Funções
concluídas anteriormente mantêm seu próprio commit; a reexecução idempotente
completa os passos restantes.

Os comandos utilizam `IF NOT EXISTS`, `CREATE OR REPLACE` ou `ON CONFLICT` onde
aplicável. Por isso, um setup interrompido normalmente pode ser executado de
novo sem apagar o banco.

`bank_script.py` descreve diretamente o schema final da V1. Ele não contém
`ALTER TABLE`, correções de colunas antigas, dados de unidade ou migrações
históricas. As tabelas são criadas em ordem de dependência para que chaves
estrangeiras e constraints já nasçam prontas.

O schema final inclui `integracao_funil_unidade`, configuração 1:1 da unidade,
`funil_envios`, fila operacional 1:1 da conversa, a profissão informada pelo
cliente naquela conversa, a profissão válida mais recente no cadastro do
cliente e `pesquisa_satisfacao`, registro 1:1 de nota e comentário opcional da
conversa. As etapas 18 a 22 são marcadas como
`elegivel_funil`; os dados da pesquisa não compõem o payload do Funil. A etapa
20 registra a decisão de comentar, a etapa 21 coleta o comentário quando aceito
e a recusa salta diretamente da etapa 20 para a 22. Encerramento e bloqueio de
30 dias são exclusivos da política da etapa 22.

A migração incremental que insere a confirmação como etapa 3 e remapeia as
referências existentes está em
`deploy/migrations/20260809_adicionar_confirmacao_etapa3.sql`. Ela deve ser
executada inteira no DBeaver, em janela de manutenção e com snapshot recente;
`setup_database.py` não substitui essa migração.

A correção posterior que torna a profissão obrigatória depois da confirmação
está em
`deploy/migrations/20260811_tornar_profissao_obrigatoria_apos_confirmacao.sql`.
Ela troca somente o catálogo de transições, aceita reexecução no estado final e
não retrocede conversas que já passaram pela profissão.

A migração que adiciona `cliente.profissao` está em
`deploy/migrations/20260823_adicionar_profissao_cliente.sql`. Ela mantém
`conversa.profissao` como snapshot e preenche o cadastro com a profissão não
vazia da conversa mais recente de cada cliente.

A migração que renomeia `unidade.nome` para `nome_unidade` e adiciona a
apresentação configurável do agente está em
`deploy/migrations/20260812_personalizar_agente_unidade.sql`. Ela preserva os
nomes das unidades existentes, aplica `Suh`/`feminino` somente no primeiro
backfill e recusa schemas parciais antes de publicar o novo contrato.

`IF NOT EXISTS` não migra uma estrutura criada por uma versão antiga. Evolução
de schema existente exige um script de migração separado ou decisão consciente
de recriação em desenvolvimento. Novas migrações não devem ser anexadas ao DDL
de criação final.

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
DB_SSLMODE
DB_SSLROOTCERT
```

`DB_SSLMODE` e `DB_SSLROOTCERT` são opcionais para preservar o comportamento
local. Em produção, use `DB_SSLMODE=verify-full`, aponte
`DB_SSLROOTCERT` para uma CA confiável e mantenha em `DB_HOST` o hostname real
do servidor, necessário para a validação do certificado.

Novas credenciais não devem ser adicionadas ao código, README, logs ou prints.
Em desenvolvimento, use o `.env` local privado e ignorado pelo Git. Em produção,
use variáveis do serviço, arquivo de ambiente com permissão restrita ou
gerenciador de segredos.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`.

A suíte foi reduzida ao núcleo transacional descrito em `tests/README.md`.
