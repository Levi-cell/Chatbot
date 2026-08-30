# Repositorios

SQL de runtime da aplicacao. Os modulos sao agrupados por dominio e entidade,
nao pelo consumidor nem pelo tipo de comando SQL.

- [Portal do projeto](../../README.md)
- [Padroes de arquitetura](../../PADROES_DE_ARQUITETURA.md#sql-e-repositórios)
- [Banco e deploy](../database/README.md)

## Estrutura

```text
core/repositories/
|-- atendimento/
|   |-- clientes.py
|   |-- conversas.py
|   |-- dependentes.py
|   |-- fila.py
|   `-- historico.py
|-- fluxo/
|   |-- contextos/
|   |-- pesquisa_satisfacao.py
|   |-- politicas.py
|   |-- transicoes.py
|   `-- triagem.py
|-- unidades/
|   |-- consultas.py
|   `-- cache_control.py
|-- seguranca/
|   |-- bloqueio_meta.py
|   |-- suspeita_bot.py
|   `-- turno_cliente.py
`-- funil/
    |-- integracao.py
    |-- envios.py
    `-- leads.py
```

`atendimento` persiste as entidades centrais da conversa. `fluxo` consulta e
registra regras do mapa de etapas. `unidades` concentra consultas e versao do
cache. `seguranca` guarda as barreiras de turno e bloqueio. `funil` cobre a
configuracao por unidade e o estado dos envios ao CRM.

No domínio `funil`:

- `integracao.py` lê widget, link e canal da unidade;
- `leads.py` reúne cliente, dependente e triagem, preservando a profissão da
  conversa e a resposta histórica de e-mail;
- `envios.py` materializa, reivindica, reagenda e confirma a fila
  `chatbot.funil_envios`.

O repositório não executa HTTP. O `workers/worker_funil` controla commits e
chama `core/integrations/funil` depois de encerrar a transação de leitura.

## Contextos e histórico do atendimento

- `fluxo/contextos/etapa6.py` lê `suporte_idoso`, `bpa_ativo` e número comercial
  da unidade; `fluxo/contextos/etapa10.py` lê `email_obrigatorio`, destino do
  atendimento e idade do titular. Os repositórios validam a integridade dos
  dados, mas o resolver aplica a regra de atendimento.
- `atendimento/conversas.py` grava `conversa.profissao`, o snapshot capturado
  na etapa 4; `atendimento/clientes.py` também atualiza o cadastro corrente.
  O Funil usa a profissão da conversa, nunca `cliente.profissao` como fallback.
- `funil/leads.py` busca o e-mail pela mensagem do cliente na etapa 10 ligada
  ao envio confirmado do bot na etapa 11, na mesma conversa, fila e mensagem
  de origem. `cliente.email` só é fallback para legado sem esse vínculo;
  a classificação do valor ocorre fora do SQL, em `core/validacoes/email.py`.
- `atendimento/historico.py` fornece o nome e o último bot `sent` da conversa
  para a saudação de retorno. O repositório não decide o intervalo de três
  horas nem dispara mensagens.

## Contrato

Uma funcao de repositorio deve:

- receber `cursor`;
- usar SQL parametrizado;
- retornar linha, tupla, booleano, quantidade afetada ou uma representacao
  simples do resultado;
- validar invariantes persistidas quando necessario;
- deixar excecoes de persistencia chegarem ao orquestrador.

Uma funcao de repositorio nao deve:

- chamar `get_conn`;
- executar `commit`, `rollback` ou `close`;
- decidir retry;
- retornar resposta HTTP;
- acessar Redis, Meta ou outro servico externo;
- escolher a proxima etapa do atendimento.

## Mapeamento de resultados

Converter uma linha SQL em `dict`, tupla nomeada ou dataclass pertence ao
repositorio quando isso apenas nomeia os dados consultados. Decisoes de negocio,
montagem de mensagens, retry e efeitos externos continuam fora desta pasta.

## Propriedade da transacao

```text
worker_flow  -> flow_worker.py
worker_funil -> funil_worker.py e processamento.py
webhook      -> post_flow.py ou flood_guard.py
scripts      -> proprio ponto de entrada
```

O repositorio nao anuncia rollback que nao executou. Ele propaga a excecao para
o dono real da transacao registrar e decidir a recuperacao.

## Idempotencia e concorrencia

- `seguranca/turno_cliente.py` usa advisory lock por cliente e unidade;
- `atendimento/fila.py` preserva a ordem por timestamp Meta e ID;
- `atendimento/historico.py` reutiliza os vinculos da mensagem original;
- `fluxo/transicoes.py` carrega somente as arestas permitidas para a origem;
- updates de conversa exigem origem, evento e destino compativeis;
- reaplicacao idempotente aceita somente a origem ou o destino exato.

## Ao criar um repositorio

Acrescente a operacao ao modulo da entidade correspondente. Crie um novo modulo
quando houver um dominio real e coeso; nao crie `utils.py` generico e nao mova
DDL para esta pasta.

## Testes relacionados

- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`;
- `tests/unit/test_suporte_idoso_email_obrigatorio.py`;
- `tests/unit/test_saudacao_retorno.py`.

O núcleo transacional e os testes específicos estão descritos em
[`tests/README.md`](../../tests/README.md).
