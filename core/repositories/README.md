# Repositórios

SQL de runtime da aplicação. Repositórios recebem cursor, executam uma operação
de persistência e devolvem dados simples ao orquestrador.

- [Portal do projeto](../../README.md)
- [Padrões de arquitetura](../../PADROES_DE_ARQUITETURA.md#sql-e-repositórios)
- [Banco e deploy](../database/README.md)

## Arquivos

| Arquivo | Responsabilidade |
|---|---|
| `querys.py` | consultas da conversa, fila e locks |
| `inserts.py` | clientes, conversas e históricos |
| `updates.py` | contexto, status, retries e locks |
| `deletes.py` | exclusões previstas pela política de tentativas |
| `turno_cliente.py` | decisão de entrada por cliente e unidade |
| `bloqueio_meta.py` | persistência e consulta de flood/bloqueios Meta |
| `cache_control.py` | versão persistida do cache de unidades |

## Contrato

Uma função de repositório deve:

- receber `cursor`;
- usar SQL parametrizado;
- retornar linha, tupla, booleano ou quantidade afetada;
- validar invariantes persistidas quando necessário;
- deixar exceções de persistência chegarem ao orquestrador.

Uma função de repositório não deve:

- chamar `get_conn`;
- executar `commit`, `rollback` ou `close`;
- decidir retry;
- retornar resposta HTTP;
- acessar Redis ou Meta;
- escolher a próxima etapa do atendimento.

## Propriedade da transação

```text
worker  -> flow_worker.py
webhook -> post_flow.py ou flood_guard.py
scripts -> próprio ponto de entrada
```

O repositório não anuncia rollback que não executou. Ele propaga a exceção para o
dono real da transação registrar e decidir recuperação.

## Turno do cliente

`turno_cliente.py` combina filas `pending/processing` com o histórico específico
do bot. `status='sent'` não é a única evidência de resposta.

O advisory lock transacional usa cliente e unidade para impedir duas inserções
simultâneas no mesmo turno.

## Idempotência

- `id_hash_msg` evita duplicidade na fila;
- históricos reutilizam vínculo com mensagem da fila e hash de origem;
- resposta do bot é procurada pela mensagem específica;
- `transicoes_etapa.py` carrega somente as arestas permitidas para a origem;
- updates de conversa exigem a combinação exata de origem, evento e destino;
- tratamentos atualizam a interação do bot sem alterar a etapa;
- reaplicação idempotente aceita somente a origem ou o destino exato e nunca
  regride a conversa.

## Ao criar um repositório

Crie arquivo específico quando o domínio tiver operações relacionadas. Não crie
um `utils.py` genérico e não mova DDL para esta pasta.

## Testes relacionados

- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_lastfrom_semantico.py`.
