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
    ├── followup_script.py
    ├── transacao_deploy.py
    ├── cache_control_script.py
    ├── etapa_transicao_script.py
    ├── floodscript.py
    ├── turno_cliente_script.py
    └── povoar_etapas.py
```

## Runtime e deploy

- `connection_aws.py` fornece conexões para os orquestradores e aceita
  `connect_timeout` opcional; o follow-up e seu diagnóstico usam 10 segundos;
- `connection_check.py` valida acesso ao PostgreSQL;
- `deploy_database/` cria schema, tabelas, índices e funções;
- partições mensais são mantidas pelo comando manual
  `utilitarios.maintenance.message_partitions`;
- SQL de negócio executado durante atendimento fica em `core/repositories`.

## Setup

Em uma instalação vazia, prepare primeiro o schema `chatbot` e as tabelas
gerenciadas pelo Django. No banco de destino:

```sql
CREATE SCHEMA IF NOT EXISTS chatbot;
```

Depois, com as variáveis do ambiente configuradas, a partir da raiz:

```powershell
python callback/manage.py migrate --noinput
```

Somente então execute o setup do banco de negócio:

```powershell
python -m core.database.deploy_database.setup_database
```

Ordem atual:

```text
healthcheck
-> configuração única da role
-> schema principal final
   (inclui tabelas de follow-up por followup_script.py)
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

`chatbot.auth_user` é um pré-requisito explícito do DDL de negócio. Sua criação
continua pertencendo às migrations do Django; o DDL não recria tabelas internas
do framework. Se ela não existir, o setup falha com uma orientação antes de
criar as tabelas de negócio.

`unidade.id_usuario_monitoramento` é `INT NULL`, único quando preenchido e
referencia `chatbot.auth_user(id)` com `ON DELETE SET NULL`. O DDL final define
a coluna e suas constraints no `CREATE TABLE` da unidade. O banco garante a
relação 1:1 opcional; a autorização dos recursos pertence ao serviço HTTP e ao
repositório de monitoramento. Excluir um usuário não exclui a unidade.

O schema final inclui `integracao_funil_unidade`, configuração 1:1 da unidade,
`funil_envios`, fila operacional 1:1 da conversa, a profissão informada pelo
cliente naquela conversa, a profissão válida mais recente no cadastro do
cliente e `pesquisa_satisfacao`, registro 1:1 de nota e comentário opcional da
conversa. As etapas 18 a 22 são marcadas como
`elegivel_funil`; os dados da pesquisa não compõem o payload do Funil. A etapa
20 registra a decisão de comentar, a etapa 21 coleta o comentário quando aceito
e a recusa salta diretamente da etapa 20 para a 22. Encerramento e bloqueio de
30 dias são exclusivos da política da etapa 22.

Cada unidade possui `idade_minima_suporte INTEGER NULL DEFAULT NULL`, limitada
por CHECK a NULL/50/60/70/80, e `email_obrigatorio BOOLEAN NOT NULL DEFAULT TRUE`.
O limite encaminha apenas titulares a partir da idade escolhida até 89 anos;
NULL desativa. A coleta de e-mail conserva a exceção universal do titular 60+.

O SQL `deploy/migrations/20260911_idade_minima_suporte.sql` converte a coluna
booleana anterior: TRUE vira 60 e FALSE vira NULL. É transacional, verifica
as configurações por unidade e recusa reaplicação/schema parcial. Não altera
conversas, históricos ou stages do follow-up. Instalação limpa usa o DDL atual;
não deve executar novamente as migrações históricas sobre o schema final.
Ver [procedimento coordenado](../../deploy/idade_minima_suporte.md).

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

A migração que adiciona as duas políticas da unidade e amplia o domínio de
`conversa.motivo_encerramento` está em
`deploy/migrations/20260829_adicionar_suporte_idoso_email_obrigatorio.sql`.
Ela altera somente o schema, aceita reexecução no estado final e não executa
`UPDATE` nem `INSERT` sobre os dados de negócio.

A migração que renomeia `unidade.nome` para `nome_unidade` e adiciona a
apresentação configurável do agente está em
`deploy/migrations/20260812_personalizar_agente_unidade.sql`. Ela preserva os
nomes das unidades existentes, aplica `Suh`/`feminino` somente no primeiro
backfill e recusa schemas parciais antes de publicar o novo contrato.

`IF NOT EXISTS` não migra uma estrutura criada por uma versão antiga. Evolução
de schema existente exige um script de migração separado ou decisão consciente
de recriação em desenvolvimento. Novas migrações não devem ser anexadas ao DDL
de criação final.

A migração atual de monitoramento está em
`deploy/migrations/20260902_adicionar_usuario_monitoramento_unidade.sql`.
Execute-a inteira no DBeaver antes de publicar o código atualizado, com
`chatbot.unidade` e `chatbot.auth_user` já existentes. Ela adiciona a coluna
opcional e suas constraints. Se a tabela da proposta anterior existir,
transfere seus vínculos, confere o resultado e só então remove essa tabela,
sem `CASCADE`. Vínculos inválidos ou ambíguos interrompem a transação.
O SQL anterior de criação da tabela foi substituído e não deve ser executado.
A migração atual é de aplicação única: coluna já existente causa erro em vez
de aceitar uma estrutura divergente. Em caso de erro, execute `ROLLBACK`.
`ALTER TABLE`, transferência e remoção de legado ficam somente na migração;
o DDL continua sendo exclusivamente a definição final para instalação nova.

## Registros de follow-up

O DDL de instalação limpa inclui três tabelas não particionadas, criadas por
`deploy_database/followup_script.py` dentro da transação de `bank_script.py`:

| Tabela | Responsabilidade |
|---|---|
| `followup_envio` | Recibo por conversa e ID/data da mensagem do bot que originou o ciclo; registra o histórico e o WAMID do lembrete confirmado. |
| `followup_retomada` | Checkpoint da reação do cliente por conversa, fila e hash; preserva etapa, stage anterior e conclusão para retries. |
| `followup_legado` | Auditoria das conversas ativas marcadas na migração, com stage anterior e data da marcação. |

As FKs dessas tabelas apontam para a conversa com `ON DELETE CASCADE`; o
histórico de mensagens continua particionado. Não há nova tabela Django nem
ação administrativa para editar esses registros. `followup_stage` e
`followup_last_sent_at` já pertencem à tabela `conversa`.

Para uma base anterior à V1.2.0, use uma única vez
[followup_registros.sql](../../deploy/migrations/followup_registros.sql), com
flow parado e follow-up desligado. O script inteiro é transacional: cria os
registros, audita todas as conversas ativas e marca `followup_stage = 1`, inclusive
nas etapas 18–21. Não altera etapa, histórico, finalização ou datas anteriores e
não envia mensagens. Legado ativo terminal/inconsistente cancela a migração.

Na produção atual, essa migração já foi aplicada. Não a repita em deploys
seguintes: a reaplicação falha em vez de remarcar conversas. O setup de banco
vazio cria a estrutura sem marcar o legado. A role da aplicação precisa ter
permissões de leitura e escrita nas novas tabelas, por propriedade ou grants.
O [diagnóstico sem envio](../../utilitarios/README.md#diagnóstico-de-follow-up)
confere as consultas; ele não comprova as permissões de escrita.

Para habilitar a segunda camada em base existente, aplicar
[`20260924_segundo_followup.sql`](../../deploy/migrations/20260924_segundo_followup.sql).
Ela só amplia `ck_conversa_motivo_encerramento` com `followup_sem_resposta` e
preserva todas as conversas. O DDL de instalação limpa já inclui esse motivo.
Não há novas colunas ou tabelas. O segundo recibo usa o ID/data do primeiro envio
como âncora, preservando a unicidade e a rastreabilidade de cada camada.

Histórico, recibo e stage 1 são confirmados juntos pelo worker proativo; no segundo,
o mesmo commit grava stage 2, status inativo, horário e motivo de encerramento.
Histórico da resposta, efeitos da etapa, conclusão da retomada, reset do stage,
eventual encerramento e finalização da fila são confirmados juntos pelo flow.
A chamada à Meta ocorre fora dessa atomicidade local;
aceite externo seguido de falha no commit ainda pode gerar duplicidade.

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
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_followup.py`;
- `tests/integration/test_followup_postgres.py` (PostgreSQL local descartável).

A organização e o comando da suíte completa estão em `tests/README.md`.


## Encerramentos por idade e configuração atual

A migração `20260926_filtro_comercial_regras_idade.sql` amplia o CHECK de motivos,
preserva legados, normaliza suporte 90 para NULL e exige telefone comercial válido.
Não cria coluna nem altera motivos históricos. A entrada vinculada à resposta
conserva a idade informada; o motivo específico conserva o limite aplicado.
Instalações novas usam o DDL final e não reaplicam migrações antigas.

## Consumo mensal Meta

DDL versionado: `deploy/migrations/20260929_consumo_mensal_meta.sql`. O setup inicial
reutiliza somente seu bloco DDL, sem executar BEGIN/COMMIT dentro da transação externa.
Adiciona o par nullable `unidade.id_fuso`/`nome_fuso` e `fuso_verificado_em`.
`consumo_mensal_meta` tem unicidade unidade/mês, volumes não negativos, fronteiras
e fuso preservados e os três estados de apuração. `consumo_meta_coletas` mantém
agenda/diagnóstico, inclusive antes do primeiro sucesso. Nenhuma conversa/fila
é alterada. Migração, operação e reversão: [guia](../../deploy/consumo_mensal_meta.md).
