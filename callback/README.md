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
- `bloqueio_meta_guard.py`: consulta da lista local de bloqueio, promoção de
  suspeita e nova tentativa de bloqueio na Meta;
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

O `GET` devolve `hub.challenge` quando `hub.mode=subscribe` e
`hub.verify_token` coincide com `META_WEBHOOK_VERIFY_TOKEN`; nos demais casos,
devolve `Webhook ativo` com HTTP 200.

O limite do body é configurado por `WEBHOOK_MAX_BODY_BYTES` (padrão: 256 KiB).
Quando `META_WEBHOOK_SIGNATURE_REQUIRED=true`, o POST exige HMAC-SHA256 do body
original, calculado com `META_APP_SECRET` e comparado com
`X-Hub-Signature-256` por `hmac.compare_digest`. Secret vazio, header ausente ou
assinatura inválida resultam em 403. O padrão dessa flag no código é `False`;
a exigência efetiva depende da configuração do ambiente.

## Ordem do POST

```text
Content-Type
-> tamanho do body
-> assinatura Meta
-> parse JSON
-> classificação do evento Meta
-> lista local de bloqueio / suspeita de bot
-> anti-flood
-> unidade ativa
-> conversa bloqueada
-> preparação da mensagem
-> transação da fila
-> resposta HTTP
```

O webhook não envia etapas, não avança conversa e não executa dequeue.

Eventos contendo apenas `statuses` retornam 200 sem processamento na V1.
Eventos sem `messages`/`statuses`, ou com ambos, também retornam 200 sem
enfileirar. Esses descartes ocorrem antes dos controles de bloqueio e flood.

## Contrato HTTP

| Cenário | HTTP | Resultado |
|---|---:|---|
| Mensagem inserida | 200 | `status=ok` |
| Descarte por regra de negócio | 200 | `status=ignored` ou `status=ok`, conforme o ponto do fluxo |
| JSON inválido | 200 | `status=ignored`, `reason=invalid_json` |
| Falha de conexão, inserção ou commit da fila | 503 | `status=unavailable`, `reason=insert_exception` |
| Falha ao confirmar a unidade no banco após cache sem resposta conclusiva | 503 | `status=unavailable`, `reason=unit_validation_unavailable` |
| Falha de Redis e banco ao validar bloqueio de conversa | 503 | `status=unavailable`, `reason=conversation_block_validation_unavailable` |
| Falha na consulta ou promoção da lista local de bloqueio | 503 | `status=unavailable`, `reason=blocklist_validation_unavailable` |
| Flood detectado sem conseguir consultar ou persistir o bloqueio local | 503 | `status=unavailable`, `reason=flood_<origem>_banco_indisponivel` ou `flood_<origem>_persistencia_local_falhou` |
| Erro inesperado identificável, nas três primeiras ocorrências por WAMID | 503 | `status=unavailable`, `reason=unexpected_error_retry`, com `attempt` |
| Erro inesperado com limite esgotado ou contador indisponível | 200 | `status=ignored`, `reason=unexpected_error_retry_exhausted` ou `unexpected_error_retry_unavailable` |
| Assinatura inválida | 403 | `status=forbidden` |
| Payload grande | 413 | `status=payload_too_large` |
| `Content-Type` inválido | 415 | `status=unsupported_media_type` |
| `Content-Length` inválido | 400 | `status=bad_request` |
| Método não permitido | 405 | `status=method_not_allowed` |

Turno ocupado, duplicidade, unidade inativa, conversa bloqueada e flood com
bloqueio local persistido são descartes com HTTP 200. Falhas operacionais de
validação ou persistência usam os motivos 503 acima. Em motivos de flood,
`<origem>` é `redis`, `banco` ou `memoria`.

O limite de três respostas 503 aplica-se somente ao tratamento genérico de
erro inesperado, com contador Redis por WAMID e TTL de sete dias renovado a cada
ocorrência. Sem WAMID ou sem Redis, esse tratamento retorna 200 com
`unexpected_error_retry_unavailable`; os demais cenários 503 não passam por
esse contador.

## Turno e duplicidade

O par lógico é:

```text
cliente_telefone + id_phone_unidade
```

`core/repositories/seguranca/turno_cliente.py` usa advisory lock transacional para impedir
corridas. Enquanto existir fila aberta sem resposta própria do bot, mensagens
posteriores do mesmo par são descartadas.

Mensagens com timestamp anterior a uma interação já registrada também são
descartadas como reentregas fora de ordem. Se todas as filas abertas já têm sua
própria resposta do bot com `status_envio=sent`, o turno pode ser liberado.

`id_hash_msg` é único. Reentregas da Meta não criam duas linhas; o insert utiliza
`ON CONFLICT DO NOTHING`.

## Anti-flood

A regra atual mede cada cliente dentro de cada unidade:

```text
15 WAMIDs distintos em 5 segundos
chave = wa_id_cliente + phone_id_unidade
```

Clientes diferentes da mesma unidade não compartilham contador. A ordem dos
fallbacks é Redis, banco e memória local. No Redis, deduplicação por WAMID e
incremento são atômicos, com janela fixa e deduplicação por duas horas.

O bloqueio utiliza `core/integrations/whatsapp/tools/usuarios.py`. O fluxo
persiste a intenção em `chatbot.cliente_bloqueado_meta` antes de chamar a Meta.
Se a Meta falhar, mantém o bloqueio local e descarta a mensagem com HTTP 200;
uma nova mensagem desse par tenta bloquear na Meta novamente. Se o banco
impedir a persistência, retorna 503 sem chamar a Meta. Unidade não cadastrada
é descartada sem bloqueio externo.

Antes do anti-flood, `bloqueio_meta_guard.py` verifica essa lista local e
também promove conversas que atingiram o limite de turnos sem avanço. A
promoção é confirmada no banco antes da chamada externa.

Relatórios e reconciliação manual ficam em
`utilitarios/monitoring/blocked_users.py`.

O relatório é somente leitura e possui duas conferências distintas:

- bloqueios: compara
  `(waba_id, phone_id_unidade, wa_id_cliente)` entre a lista da Meta e
  `chatbot.cliente_bloqueado_meta`;
- registros Cloud API: percorre o `waba_id` de cada unidade e compara os
  `phone_number_id` retornados pela Meta com `chatbot.unidade`.

Ele também separa falhas de coleta e vínculos divergentes; não bloqueia,
desbloqueia, registra ou remove dados automaticamente.

## Transações

`post_flow.py` é dono da conexão usada para enfileirar:

```text
abrir conexão -> povoando_fila -> commit/rollback -> close
```

`populating_fila_mensagens.py` recebe cursor e não controla conexão.

As transações independentes do anti-flood pertencem a `flood_guard.py`; a
consulta e promoção da lista local pertencem a `bloqueio_meta_guard.py`. Essa
separação está detalhada em
[Padrões de arquitetura](../PADROES_DE_ARQUITETURA.md).

## Django Admin

O Admin é majoritariamente somente leitura. As exceções operacionais são:

- criação, edição e exclusão individual de unidade;
- criação, edição e exclusão de configuração de integração do Funil por unidade;
- desbloqueio individual de cliente bloqueado na Meta.

Cada unidade exige `nome_unidade`, `nome_agente` e `genero`. O campo `genero`
oferece no formulário somente `Masculino` e `Feminino`; ele controla o artigo
usado para apresentar o agente nos inícios padrão, de mídia, financeiro e de
tratamento de reforço escolar da etapa 1.

`waba_id` e `phone_number_id` ficam somente leitura após a criação. O Admin
também expõe `suporte_idoso` e `email_obrigatorio`; ativar suporte ao idoso
exige um `numero_comercial` brasileiro válido.

No Admin, criação/exclusão de unidade e desbloqueio individual seguem
Meta-first. Se a Meta falhar, a alteração local correspondente não é
confirmada. Se a Meta concluir e uma etapa local posterior falhar, a operação
externa não é compensada automaticamente: a unidade exige conferência manual.
O desbloqueio também zera `turnos_sem_avanco` das conversas ativas do par.
Essa ordem administrativa é diferente do bloqueio preventivo do webhook,
que persiste primeiro a lista local.

## Testes relacionados

- `tests/unit/test_fluxo_turno_abc.py`;
- `tests/unit/test_persistencia_essencial.py`;
- `tests/unit/test_retry_essencial.py`;
- `tests/unit/test_worker_flow_runtime.py`.

Esses arquivos cobrem o núcleo transacional; consulte também
[`tests/README.md`](../tests/README.md).
