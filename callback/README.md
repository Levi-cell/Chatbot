# Callback e webhook

Camada HTTP Django responsável por receber eventos da Meta, validar a entrada e
persistir mensagens aceitas na fila. O processamento da conversa pertence ao
worker.

Documentos centrais:

- [Regras de negócio](../REGRAS_DE_NEGOCIO.md)
- [Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md)
- [Portal do projeto](../README.md)

## Estrutura

```text
callback/
├── callback/              configuração Django
├── webhook/
│   ├── admin.py           operações administrativas
│   ├── models.py          mapeamento das tabelas
│   ├── urls.py            rota /webhook
│   ├── views.py           borda GET/POST
│   └── services/          fluxo HTTP e anti-flood
└── manage.py
```

Arquivos principais de `services`:

- `post_flow.py`: validações e transação da fila;
- `meta_signature.py`: assinatura `X-Hub-Signature-256`;
- `flood_guard.py`: Redis, banco, memória e bloqueio Meta;
- `populating_fila_mensagens.py`: parse e inserção usando cursor recebido;
- `alerta_flood_memoria.py`: alerta local quando banco e Redis falham.

## Endpoint

```text
GET  /webhook
POST /webhook
```

A rota não possui barra final. O `GET` atende à verificação inicial da Meta. O
`POST` recebe eventos reais.

## Ordem do POST

```text
Content-Type
-> tamanho do body
-> assinatura Meta
-> parse JSON
-> anti-flood
-> unidade ativa
-> conversa bloqueada
-> preparação da mensagem
-> transação da fila
-> resposta HTTP
```

O webhook não envia etapas, não avança conversa e não executa dequeue.

## Contrato HTTP

| Cenário | HTTP | Resultado |
|---|---:|---|
| Mensagem inserida | 200 | `status=ok` |
| Descarte por regra de negócio | 200 | `status=ignored` ou `status=ok`, conforme o ponto do fluxo |
| Falha de conexão, inserção ou commit da fila | 503 | `status=unavailable`, `reason=insert_exception` |
| Falha de Redis e banco ao validar unidade | 503 | `status=unavailable`, `reason=unit_validation_unavailable` |
| Assinatura inválida | 403 | `status=forbidden` |
| Payload grande | 413 | `status=payload_too_large` |
| `Content-Type` inválido | 415 | `status=unsupported_media_type` |
| `Content-Length` inválido | 400 | `status=bad_request` |
| Método não permitido | 405 | `status=method_not_allowed` |

O HTTP 503 é reservado para cenário operacional em que o sistema não conseguiu
confirmar se uma mensagem válida poderia ser aceita, como falha de persistência
da fila ou indisponibilidade simultânea de Redis e banco na validação de unidade.
Não converta flood, turno ocupado, duplicidade, unidade inativa ou conversa
bloqueada em indisponibilidade.

## Turno e duplicidade

O par lógico é:

```text
cliente_telefone + id_phone_unidade
```

`core/repositories/seguranca/turno_cliente.py` usa advisory lock transacional para impedir
corridas. Enquanto existir fila aberta sem resposta própria do bot, mensagens
posteriores do mesmo par são descartadas.

`id_hash_msg` é único. Reentregas da Meta não criam duas linhas; o insert utiliza
`ON CONFLICT DO NOTHING`.

## Anti-flood

A regra atual mede cada cliente dentro de cada unidade:

```text
15 eventos em 5 segundos
chave = wa_id_cliente + phone_id_unidade
```

Clientes diferentes da mesma unidade não compartilham contador. A ordem dos
fallbacks é Redis, banco e memória local. O bloqueio utiliza
`core/integrations/whatsapp/pywa_functions/usuarios.py` e segue Meta-first.

Relatórios e reconciliação manual ficam em
`core/integrations/whatsapp/tools/block_report.py`.

## Transações

`post_flow.py` é dono da conexão usada para enfileirar:

```text
abrir conexão -> povoando_fila -> commit/rollback -> close
```

`populating_fila_mensagens.py` recebe cursor e não controla conexão.

As transações independentes do anti-flood pertencem a `flood_guard.py`. Essa
separação está detalhada em
[Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md).

## Django Admin

O Admin é majoritariamente somente leitura. As exceções operacionais são:

- criação, edição e exclusão individual de unidade;
- desbloqueio individual de cliente bloqueado na Meta.

Operações externas são Meta-first. Se a Meta falhar, a alteração correspondente
não deve ser confirmada no banco ou Redis.

## Testes relacionados

- `tests/unit/test_webhook_post_flow.py`;
- `tests/unit/test_webhook_statuses_e_cronologia.py`;
- `tests/unit/test_webhook_statuses_e_cronologia.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_flood_guard.py`;
- `tests/unit/test_cache_essencial.py`;
- `tests/unit/test_webhook_post_flow.py`.
