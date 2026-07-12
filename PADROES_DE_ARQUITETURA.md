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

## Modelo de execução da V1 e evolução para a V2

Na V1, a implantação deverá manter uma única instância ativa do worker. Essa
escolha atende ao volume inicial esperado, simplifica a operação e reduz o custo
de infraestrutura enquanto o sistema atende poucas unidades.

"Uma única instância ativa na V1" não deve ser confundida com a regra "um worker
por conversa". A primeira é uma decisão operacional desta versão; a segunda é
uma proteção que continuará válida mesmo quando existirem vários workers no
sistema: dois workers nunca poderão processar simultaneamente a mesma conversa.

Processamento paralelo permitido:

```text
Worker 1 -> conversa do cliente A
Worker 2 -> conversa do cliente B
```

Processamento que deverá continuar bloqueado:

```text
Worker 1 -> conversa do cliente A
Worker 2 -> conversa do cliente A ao mesmo tempo
```

Assim, vários workers poderão atender clientes diferentes em paralelo, mas cada
conversa ficará sob responsabilidade de apenas um worker por vez.

Embora a V1 execute apenas uma instância, seu ciclo já deve preservar as
proteções necessárias para concorrência e recuperação:

- dequeue atômico com `FOR UPDATE SKIP LOCKED`;
- exclusão mútua por conversa com `lock_version`;
- ordenação de mensagens anteriores ainda abertas;
- timeout e retomada de mensagens abandonadas em `processing`;
- idempotência pelo histórico vinculado à mensagem da fila;
- checkpoints, commits, rollbacks e fechamento da conexão por ciclo;
- `sent` somente depois da persistência da resposta do bot.

O objetivo arquitetural da V2 será permitir múltiplas instâncias de worker para
atender maior volume sem descartar essas garantias. Cada instância deverá
reutilizar os mesmos contratos de ordenação, lock, retry, idempotência e
recuperação estabelecidos na V1.

A forma de implementação da V2 permanece aberta. Classe, processos, containers,
threads ou um controlador dedicado são opções técnicas, não requisitos por si
só. A escolha deverá ser guiada por testes de concorrência, capacidade do banco,
observabilidade, desligamento gracioso e demanda real de produção.

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
- [`_V2/desafios_v2.md`](_V2/desafios_v2.md): evolução de capacidade e desafios
  técnicos previstos para a V2.

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
- configuração por ambiente;
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
- `flow_sender.py`: preservação da idempotência e seleção do resolver da etapa
  atual;
- `etapas/resolver_etapa<n>.py`: validação da etapa atual e encaminhamento para o
  destino autorizado;
- `etapas/validadores_universais/`: validações reutilizáveis entre etapas;
- `etapas/validadores_contexto/`: validações específicas da pergunta atual;
- `transicoes/contexto_transicao.py`: montagem explícita da fotografia de
  origem e destinos permitidos no contexto histórico;
- `transicoes/resolver_transicao.py`: resolução de
  `origem + evento -> destino`;
- `transacoes/movimento_conversa.py`: inicialização, transição ou permanência;
- `transacoes/efeitos_transicao.py`: efeitos de banco específicos de cada
  aresta autorizada.

Esses arquivos podem escolher qual integração chamar, mas não devem criar cliente
PyWa, montar `Button` ou manter textos de saída.

A navegação não utiliza `id_etapa + 1`. O worker identifica o evento, consulta
as transições permitidas para a origem e transporta a decisão no contexto. A
persistência final revalida a mesma aresta no PostgreSQL antes do commit.

Tratamentos não produzem evento de transição e permanecem na etapa atual.

### Escolha entre validador universal e contextual

Um validador só pertence a `validadores_universais` quando:

- é usado por mais de uma etapa;
- possui o mesmo significado em todas elas;
- apenas identifica tratamento/permanência ou permite seguir o fluxo;
- não escolhe entre diferentes arestas do mapa.

Mídia, financeiro e nome atendem a esse contrato. O resultado deles não muda
de significado conforme a etapa que os chama.

Um validador pertence a `validadores_contexto` quando a resposta produz eventos
próprios daquela etapa, especialmente quando pode pular ou retroceder no mapa.
Mesmo que duas etapas reconheçam textos idênticos, cada uma mantém seu
validador quando devolve eventos diferentes:

```text
validar_etapa5("Quero agendar") -> oferta_aceita
validar_etapa7("Quero agendar") -> retorno_confirmado
```

Nesse caso, a semelhança da gramática não transforma o validador em universal.
O contrato relevante é o evento de negócio produzido para a origem atual.

O resolver deve receber diretamente esse evento:

```python
evento_transicao = validar_etapa5(texto_cliente)

destinos_esperados = _destinos_esperados_por_evento(evento_transicao)
etapa_destino = resolver_destino_transicao(
    contexto_historico,
    evento_transicao,
    destinos_esperados=destinos_esperados,
)
```

Não criar uma decisão neutra intermediária para depois traduzi-la em evento no
resolver. A interpretação de uma resposta que escolhe arestas pertence ao
validador contextual da própria etapa.

Todo resolver de etapa deve marcar explicitamente a fronteira entre validação e
resolução do destino. O marcador fica depois de todos os retornos de tratamento
e imediatamente antes da consulta ao mapa:

```python
# VALIDANDO DESTINO(S)
# A resposta já passou pelos tratamentos; agora o mapa autoriza a aresta.
etapa_destino = resolver_destino_transicao(...)
```

Antes dessa fronteira, o resolver apenas valida a resposta e pode permanecer na
etapa atual. Depois dela, a resposta já é válida: o código resolve o destino,
chama o sender correspondente e anexa a transição ao contexto de envio.

Quando o resolver produz somente um evento e possui um único destino possível,
o conjunto esperado deve ficar explícito na chamada:

```python
etapa_destino = resolver_destino_transicao(
    contexto_historico,
    EVENTO_RESPOSTA_VALIDA,
    destinos_esperados={ETAPA_DESTINO},
)
```

Quando a mesma origem produz múltiplos eventos e destinos, o resolver deve
centralizar essa correspondência em
`_destinos_esperados_por_evento(evento_transicao)`. A função interna não é
necessária em fluxos lineares, pois apenas esconderia uma constante sem
representar uma decisão real.

### Constantes e efeitos de etapa

Toda constante de estado deve mostrar o número persistido e o significado:

```python
ETAPA_1_NOME_CLIENTE = 1
ETAPA_2_DESTINO_ATENDIMENTO = 2
ETAPA_3_NOME_DEPENDENTE = 3
ETAPA_4_IDADE_ALUNO = 4
```

Não usar números mágicos como `etapa_origem == 2` e não omitir o número no nome
da constante. Esse padrão permite localizar a etapa sem perder seu significado.

Em `transacoes/efeitos_transicao.py`, os efeitos devem ser agrupados primeiro
pela etapa de origem e depois pelo evento:

```python
# ETAPA 2
if etapa_origem == ETAPA_2_DESTINO_ATENDIMENTO:
    if evento == EVENTO_PARA_MIM:
        # 2 -> 4

    if evento == EVENTO_PARA_OUTRA_PESSOA:
        # 2 -> 3
```

Cada comentário de evento deve mostrar `origem -> destino`. A tabela
`etapa_transicao` continua sendo a fonte de verdade, e o código apenas torna
visíveis os efeitos de cada aresta autorizada.

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

Componentes compartilhados por um grupo de etapas podem possuir um helper
próprio. `triagem_componentes.py`, por exemplo, atende exclusivamente às etapas
10 a 15 e centraliza botões e rodapé, sem conter envio ou decisão de fluxo.

Componentes visuais usados por diferentes etapas pertencem a
`componentes_compartilhados.py`. Esse helper pode armazenar textos comuns e
funções puras de composição, mas não pode conhecer cliente, conversa, evento ou
destino.

Na PyWa utilizada pelo projeto, `header` e `footer` só são enviados quando a
mensagem possui botões e se torna interativa. Em mensagens de texto simples,
esses argumentos são ignorados.

O fluxo atual restringe cabeçalhos à introdução e às perguntas da triagem,
etapas 9 a 15. As demais etapas não devem passar `header` para a Meta nem
simular cabeçalho dentro do corpo da mensagem.

Rodapés continuam permitidos nos pontos definidos pelo produto e devem aparecer
em itálico. Como o Markdown não produz efeito no campo `footer` de uma mensagem
interativa, o projeto incorpora o rodapé ao próprio corpo usando `_texto_`,
mesmo quando a mensagem possui botões. O sender não deve passar `footer` para a
Meta nesses casos.

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

Quando várias etapas compartilham exatamente o mesmo contrato de transporte,
um sender-base pode centralizar apenas a mecânica comum. `triagem_base.py`
atende às etapas 10 a 15: monta os componentes PyWa, envia, extrai o ID da
mensagem e produz o contexto de envio. Os senders públicos de cada etapa
continuam responsáveis pelo conteúdo e o helper-base não pode validar respostas,
produzir eventos ou escolher destinos.

Separação interna recomendada:

- `cliente.py`: criação e normalização do cliente;
- `envios.py`: primitivas genéricas de envio;
- `etapas.py`: envios específicos de etapas;
- `tratamentos_type.py`: envios de tratamento para mídia ou tipo não suportado;
- `tratamentos_context.py`: envios de tratamento para resposta fora do contexto
  da etapa;
- `tratamentos_financeiros.py`: envios de tratamento para dúvidas sobre valor,
  custo ou investimento;
- `usuarios.py`: bloqueio, desbloqueio e consulta de usuários.

### `tools`

Contém scripts administrativos ou operacionais executados de forma consciente,
como ativação de número, inscrição do WABA e reconciliação de bloqueios.

Um `tool` não deve se tornar dependência do fluxo normal. Quando uma operação é
reutilizada em runtime, mova a implementação para a camada apropriada e faça o
tool chamá-la.

Configuração operacional:

```text
core/integrations/whatsapp/tools/config.py
```

Esse arquivo fornece a configuração compartilhada da integração WhatsApp, mas os
valores vêm de `core/config_env.py` e das variáveis de ambiente. Ele não deve
armazenar token, WABA ID, phone number ID ou outro valor sensível diretamente no
código.

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
- usar `core/config_env.py` para leitura e validação de variáveis de ambiente;
- manter `.env.example` sem segredos reais;
- manter `.env` fora do Git;
- IDs públicos e limites podem ser constantes quando não forem segredos;
- mudanças de configuração não devem alterar fluxo, fila, histórico ou regra de
  negócio;
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
