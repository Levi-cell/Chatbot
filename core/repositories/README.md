# Repositorios

SQL de runtime da aplicacao. Os modulos sao agrupados por dominio e entidade,
nao pelo consumidor nem pelo tipo de comando SQL.

- [Portal do projeto](../../README.md)
- [Padroes de arquitetura](../../PADROES_DE_ARQUITETURA.md#sql-e-repositorios)
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
|   |-- politicas.py
|   |-- transicoes.py
|   `-- triagem.py
|-- unidades/
|   |-- consultas.py
|   `-- cache_control.py
|-- seguranca/
|   |-- bloqueio_meta.py
|   `-- turno_cliente.py
`-- funil/
    |-- integracao.py
    `-- envios.py
```

`atendimento` persiste as entidades centrais da conversa. `fluxo` consulta e
registra regras do mapa de etapas. `unidades` concentra consultas e versao do
cache. `seguranca` guarda as barreiras de turno e bloqueio. `funil` cobre a
configuracao por unidade e o estado dos envios ao CRM.

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
worker  -> flow_worker.py
webhook -> post_flow.py ou flood_guard.py
scripts -> proprio ponto de entrada
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
- `tests/unit/test_transicoes_etapa.py`;
- `tests/unit/test_lastfrom_semantico.py`.
