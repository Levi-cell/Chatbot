# Padrões de arquitetura do Chatbot

## Finalidade

Este documento define onde cada responsabilidade deve ser implementada e quais
dependências são permitidas no projeto.

Antes de alterar código, leia também
[`REGRAS_DE_NEGOCIO.md`](REGRAS_DE_NEGOCIO.md). Os documentos possuem papéis
diferentes:

- `REGRAS_DE_NEGOCIO.md` define o comportamento esperado do sistema;
- `PADROES_DE_ARQUITETURA.md` define a organização e as fronteiras do código.

Uma reorganização nunca pode alterar silenciosamente uma regra de negócio. Caso
uma necessidade não se encaixe neste documento, a exceção deve ser discutida e
documentada antes da implementação.

## Princípios gerais

1. Cada módulo deve possuir uma responsabilidade principal clara.
2. Fluxo de negócio, persistência e integração externa não devem ser misturados.
3. Funções de baixo nível não devem controlar transações de alto nível.
4. O código deve depender de camadas mais internas, nunca do ponto de entrada.
5. Comportamentos críticos devem possuir testes em `tests/`.
6. Refatorações estruturais devem preservar entradas, saídas, logs relevantes e
   efeitos persistidos.
7. Não criar abstrações apenas para movimentar código; cada pasta deve representar
   uma fronteira real.

## Mapa de responsabilidades

```text
callback/webhook  -> entrada HTTP e enfileiramento
workers           -> processamento assíncrono e fluxo da conversa
core/repositories -> SQL e persistência
core/database     -> conexão, DDL e preparação do banco
core/cache        -> Redis, fallback e autocura detectável
core/integrations -> comunicação com serviços externos
tests             -> testes, mocks, fakes e contratos
```

Direção esperada das dependências:

```text
webhook ─┐
         ├──> core/repositories
worker  ─┤──> core/cache
admin   ─┤──> core/integrations
tools   ─┘

core nunca importa webhook ou worker
```

## Documentação por camada

O [`README.md`](README.md) da raiz é o portal da documentação. Cada README local
explica somente a responsabilidade e os contratos da sua camada:

- [`callback/README.md`](callback/README.md): entrada HTTP e enfileiramento;
- [`core/README.md`](core/README.md): mapa dos recursos compartilhados;
- [`workers/README.md`](workers/README.md): ciclo, checkpoints e recuperação;
- [`tests/README.md`](tests/README.md): estratégia e execução dos testes;
- [`core/cache/README.md`](core/cache/README.md): Redis, fallback e autocura;
- [`core/database/README.md`](core/database/README.md): conexão, DDL e setup;
- [`core/repositories/README.md`](core/repositories/README.md): contratos SQL;
- [`core/integrations/README.md`](core/integrations/README.md): integrações externas;
- [`core/integrations/whatsapp/README.md`](core/integrations/whatsapp/README.md):
  organização da integração Meta/PyWa.

READMEs locais não devem copiar regras completas. Eles apontam para
`REGRAS_DE_NEGOCIO.md` quando uma decisão de produto precisa ser interpretada e
para este documento quando a dúvida é sobre organização do código.

## `core`

`core` contém recursos compartilhados pelos diferentes pontos de entrada do
sistema. Um módulo pertence a `core` quando pode ser utilizado por webhook,
worker, Admin ou scripts sem depender do fluxo específico de nenhum deles.

Responsabilidades permitidas:

- conexão e preparação do banco;
- funções SQL de repositório;
- cache e fallback;
- integrações externas;
- configuração de logging;
- exceções compartilhadas.

Responsabilidades que não pertencem a `core`:

- laço infinito do worker;
- resposta HTTP do webhook;
- decisão de rota específica de uma etapa do worker;
- controle completo de uma transação de negócio;
- mocks ou dados exclusivos de teste.

## SQL e repositórios

### Localização

Consultas e alterações de dados da aplicação devem ficar em
`core/repositories/`.

Exemplos:

- `querys.py`: consultas e locks persistidos;
- `inserts.py`: inserções;
- `updates.py`: atualizações e reagendamentos;
- `deletes.py`: exclusões;
- repositórios específicos podem ser criados quando um domínio crescer, como
  `bloqueio_meta.py` e `turno_cliente.py`.

DDL, criação de funções PostgreSQL e preparação de ambiente pertencem a
`core/database/deploy/`, não aos repositórios de runtime.

### Contrato das funções SQL

Uma função de repositório deve:

- receber `cursor` como argumento;
- executar SQL parametrizado;
- retornar dados ou quantidade de linhas afetadas;
- validar invariantes persistidas quando necessário;
- registrar logs técnicos sem dados sensíveis completos.

Uma função de repositório não deve:

- abrir conexão com `get_conn`;
- executar `commit`, `rollback` ou `close`;
- decidir retry do worker;
- retornar `JsonResponse`;
- chamar Meta, PyWa ou Redis;
- esconder falha de persistência necessária para a regra de negócio.

Evite SQL em worker, webhook, integração ou cache quando a operação representa
persistência da aplicação. O ponto de entrada chama o repositório apropriado.

## Conexões e transações

O arquivo que conhece o fluxo completo é o dono da transação.

### Worker

No processamento principal do worker, conexão, `commit`, `rollback` e `close`
devem permanecer em:

```text
workers/worker_flow/response_flow/flow_worker.py
```

Repositórios e funções auxiliares recebem o cursor aberto pelo `flow_worker`.
Commits intermediários devem representar estados recuperáveis documentados nas
regras de negócio.

### Webhook

A transação de enfileiramento pertence a:

```text
callback/webhook/services/post_flow.py
```

As transações independentes do anti-flood pertencem a:

```text
callback/webhook/services/flood_guard.py
```

O módulo `populating_fila_mensagens.py` prepara, valida e insere usando o cursor
recebido, mas não abre ou finaliza conexão.

### Scripts e Admin

Scripts operacionais podem controlar a própria conexão quando são o ponto de
entrada completo da operação. No Django Admin, preserve o comportamento
Meta-first definido nas regras de negócio e utilize o gerenciamento transacional
do Django ou uma fronteira explícita quando necessário.

## Webhook

`callback/webhook` é a fronteira HTTP do sistema.

Responsabilidades:

- validar método, `Content-Type`, tamanho e assinatura;
- interpretar o payload da Meta;
- aplicar anti-flood;
- verificar se a mensagem pode entrar no turno;
- inserir a mensagem válida na fila;
- devolver a resposta HTTP apropriada;
- oferecer operações administrativas do Django relacionadas ao webhook.

O webhook não deve:

- responder a etapa da conversa;
- executar o fluxo do bot;
- retirar mensagens da fila;
- avançar etapa;
- manter textos de resposta do bot;
- importar PyWa diretamente.

Serviços HTTP pequenos ficam em `callback/webhook/services/`. `views.py` deve ser
uma borda fina e delegar o fluxo para esses serviços.

## Workers

`workers` contém processamento assíncrono e decisões do fluxo da conversa.

### `worker_flow`

Responsabilidades:

- selecionar mensagem da fila;
- validar cliente, unidade e conversa;
- adquirir e liberar lock da conversa;
- reconhecer estados intermediários e retries;
- validar histórico;
- rotear resposta ou tratamento;
- persistir resposta e contexto;
- marcar a fila como `sent` somente após a persistência necessária.

### `response_flow`

Contém orquestração de respostas:

- `flow_worker.py`: ciclo e transações;
- `rotear_resposta_cliente.py`: seleção do fluxo;
- `flow_sender.py`: seleção da etapa de envio;
- `flow_treat_*.py`: seleção de tratamentos.

Esses arquivos podem escolher qual integração chamar, mas não devem criar cliente
PyWa, montar `Button` ou manter textos de saída.

### Tratamento de erros

`workers/tratamento_erros_externos/` concentra decisões de retry, exclusão e
tratamentos específicos de falhas externas. Repositórios executam a alteração
solicitada, mas não escolhem a política de retry.

## Integrações externas

Toda integração externa compartilhada pertence a `core/integrations/<serviço>/`.

Exemplos de serviços:

- `whatsapp`;
- `google`;
- `funil`.

Uma integração deve:

- encapsular a biblioteca ou API externa;
- receber dados já validados pelo chamador;
- converter retorno externo para um contrato simples da aplicação;
- traduzir falhas quando houver uma exceção de domínio apropriada;
- não controlar banco, fila, retry ou transação.

## WhatsApp e PyWa

Estrutura oficial:

```text
core/integrations/whatsapp/
├── exceptions.py
├── messages/
├── pywa_functions/
└── tools/
```

### `messages`

Armazena o catálogo de conteúdo enviado ao WhatsApp:

- textos;
- títulos de botão;
- callbacks;
- templates;
- funções puras de formatação ou seleção de template.

Não pode conter:

- `import pywa`;
- envio para a Meta;
- banco ou Redis;
- logging de integração;
- decisão de retry, lock ou etapa persistida.

Novos textos não devem ser escritos diretamente no worker ou em
`pywa_functions`. Organize-os por responsabilidade, como `etapas.py` e
`tratamentos.py`.

### `pywa_functions`

É o único local permitido para chamadas diretas à biblioteca PyWa.

Responsabilidades:

- criar o cliente `WhatsApp`;
- criar tipos PyWa, como `Button`;
- chamar `send_message`;
- bloquear, desbloquear e consultar usuários na Meta via PyWa;
- extrair IDs retornados;
- produzir o contexto de envio esperado pelo worker;
- converter falhas de envio para `ErroEnvioMeta` quando aplicável.

Não pode conter:

- SQL;
- Redis;
- `commit`, `rollback` ou `close`;
- decisão sobre limite de retry;
- mutação direta de conversa, histórico ou fila.

Separação interna recomendada:

- `cliente.py`: criação e normalização do cliente;
- `envios.py`: primitivas genéricas de envio;
- `etapas.py`: envios específicos de etapas;
- `tratamentos.py`: envios específicos de tratamentos;
- `usuarios.py`: bloqueio, desbloqueio e consulta de usuários.

### `tools`

Contém scripts administrativos ou operacionais executados de forma consciente,
como ativação de número, inscrição do WABA e reconciliação de bloqueios.

Um `tool` não deve se tornar dependência do fluxo normal. Quando uma operação é
reutilizada em runtime, mova a implementação para a camada apropriada e faça o
tool chamá-la.

Exceção legada atual:

```text
core/integrations/whatsapp/tools/config.py
```

Esse arquivo ainda fornece configuração compartilhada para a integração. Ele não
deve servir de exemplo para novas configurações. Uma futura migração de
credenciais deve movê-las para configuração segura de ambiente sem ser misturada
com outra refatoração.

## Cache

`core/cache` concentra Redis, cache local e mecanismos de fallback.

Regras:

- banco continua sendo a fonte persistida da verdade;
- cache deve possuir fallback quando a regra de negócio exigir disponibilidade;
- falhas detectáveis de cache stale devem permitir reparo seguro;
- chaves devem ser normalizadas e centralizadas;
- cache não controla transações do banco;
- uma falha de Redis não deve ser silenciosamente tratada como dado válido;
- logs devem informar fallback e autocura sem expor dados completos.

`core/cache/runtime/` contém caches utilizados durante a execução normal.
Operações administrativas de reset devem permanecer separadas do caminho comum.

## Django Admin

O Admin é uma interface operacional, não uma segunda implementação das regras.

Regras:

- reutilizar funções de integração e repositório existentes;
- não duplicar chamadas PyWa;
- preservar operações Meta-first;
- se a Meta falhar, não confirmar alteração correspondente no banco ou Redis;
- manter tabelas de auditoria majoritariamente somente para leitura;
- ações permitidas devem seguir `REGRAS_DE_NEGOCIO.md`.

## Logging e exceções

- utilizar `logging`, não `print`, nos fluxos de runtime;
- obter logger por responsabilidade, como `worker.*`, `webhook.*` e
  `whatsapp.*`;
- utilizar `short_value` para dados identificadores nos logs;
- nunca registrar tokens, segredos, payloads completos ou credenciais;
- usar `logger.exception` quando o traceback é necessário;
- não capturar `Exception` apenas para ocultar erro sem fallback definido;
- exceções de integração devem carregar contexto mínimo útil, sem segredo.

`print` é aceitável em scripts de relatório executados manualmente e em saídas de
desenvolvimento já delimitadas.

## Configuração e segredos

- não adicionar novos tokens ou credenciais diretamente no código;
- preferir variáveis de ambiente ou configuração externa;
- IDs públicos e limites podem ser constantes quando não forem segredos;
- não misturar migração de credenciais com refatoração estrutural;
- testes devem usar valores fictícios e nunca credenciais reais.

## Testes

Todo teste, mock, fake e payload exclusivo de teste deve ficar em `tests/`.

Estrutura atual:

```text
tests/
├── helpers.py
├── payloads.py
└── unit/
    └── test_*.py
```

Regras:

- não criar testes em módulos de produção;
- não adicionar `Mock`, `MagicMock`, `patch` ou classes `Fake*` fora de `tests/`;
- testar comportamento e contratos, não somente linhas internas;
- falhas externas devem ser simuladas sem acessar Meta, Redis ou AWS reais;
- alterações de fluxo crítico devem cobrir sucesso, falha e retry;
- alterações estruturais devem possuir testes que impeçam regressão da
  organização quando isso for relevante;
- a suíte completa deve permanecer executável por descoberta.

Comando padrão:

```powershell
python -m unittest discover -s tests -v
```

Fluxos críticos que não podem perder cobertura:

- A/B/C e primeira mensagem do turno;
- idempotência após resposta persistida;
- falha do banco após envio confirmado pela Meta;
- limite de retries e exclusão;
- ordenação e locks;
- retrocesso e salto de etapa;
- `last_message_from` semântico;
- fallback e autocura de cache;
- transações de worker e webhook;
- bloqueio/desbloqueio Meta-first.

## Nomes e organização de arquivos

- arquivos e funções devem usar `snake_case`;
- nomes devem descrever responsabilidade, não detalhes passageiros;
- evitar arquivos genéricos como `utils.py` quando existe um domínio claro;
- uma função reutilizada deve morar na camada proprietária da responsabilidade;
- constantes de um domínio devem ficar próximas ao domínio;
- não criar pasta nova para apenas um arquivo sem perspectiva clara de fronteira;
- não criar arquivo que apenas reexporta outro sem necessidade real de
  compatibilidade.

## Imports e dependências

- preferir imports absolutos a partir da raiz do projeto;
- evitar import circular por meio de fronteiras claras, não por imports tardios
  espalhados;
- worker e webhook podem importar `core`;
- `core` não importa worker ou webhook;
- `messages` não importa `pywa_functions`;
- `pywa_functions` pode importar `messages`, cliente e exceções da integração;
- repositórios não importam integrações;
- testes podem importar qualquer módulo necessário para validar contratos.

## Anti-padrões proibidos

- SQL diretamente em `flow_worker.py` ou `post_flow.py`;
- `commit` dentro de `core/repositories`;
- texto de WhatsApp escrito dentro do worker;
- `send_message` fora de `pywa_functions`;
- regra de retry dentro de um sender;
- acesso ao Redis dentro de uma função PyWa;
- `JsonResponse` dentro de repositório;
- mock dentro de código de produção;
- duplicação de regra de negócio no Admin;
- fachada ou wrapper sem responsabilidade própria;
- captura silenciosa de erro que transforme falha em sucesso;
- refatoração estrutural misturada com mudança de comportamento sem testes e
  documentação explícita.

## Como decidir onde criar uma função

Use esta sequência:

1. Executa SQL da aplicação? `core/repositories`.
2. Abre ou prepara infraestrutura de banco? `core/database`.
3. Gerencia cache ou fallback de cache? `core/cache`.
4. Chama serviço externo compartilhado? `core/integrations/<serviço>`.
5. Chama diretamente PyWa? `core/integrations/whatsapp/pywa_functions`.
6. Define texto ou callback do WhatsApp? `messages`.
7. Trata entrada HTTP? `callback/webhook`.
8. Decide processamento assíncrono ou etapa? `workers`.
9. É script manual operacional? `tools`.
10. Existe apenas para validar comportamento? `tests`.

Se a função responder positivamente a mais de uma pergunta, provavelmente deve
ser dividida em orquestração e operação de baixo nível.

## Checklist para alterações futuras

Antes de implementar:

1. Ler `REGRAS_DE_NEGOCIO.md` e este documento.
2. Identificar a camada proprietária da responsabilidade.
3. Mapear contratos, chamadores e estados intermediários afetados.
4. Confirmar que a mudança não duplica uma função existente.

Durante a implementação:

1. Manter transações no orquestrador correto.
2. Preservar logs e exceções relevantes.
3. Não misturar refatoração com nova regra de negócio.
4. Criar ou atualizar testes somente em `tests/`.

Depois da implementação:

```powershell
python -m unittest discover -s tests -v
python -m compileall core workers callback tests
python callback/manage.py check
git diff --check
```

Também confira:

- imports antigos removidos;
- chamadas PyWa apenas em `pywa_functions`;
- textos de WhatsApp apenas em `messages`;
- SQL e transações nas camadas corretas;
- nenhum segredo novo no diff;
- nenhuma alteração não relacionada à tarefa.

## Atualização deste documento

Este documento deve ser atualizado quando:

- uma nova camada for criada;
- a propriedade de uma transação mudar;
- uma integração externa ganhar estrutura própria;
- uma exceção arquitetural deixar de ser temporária;
- um padrão recorrente for aprovado para uso futuro.

Mudanças neste documento não substituem testes nem alteram automaticamente as
regras de negócio.
