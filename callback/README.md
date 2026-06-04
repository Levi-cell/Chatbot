# Webhook do Chatbot

Este documento descreve o funcionamento do webhook responsável por receber eventos da Meta/WhatsApp, validar a requisição, proteger o sistema contra flood e inserir mensagens válidas na fila para o worker.

O objetivo é que este arquivo sirva como referência para revisão, manutenção e onboarding de futuros colaboradores.

## Endpoint

Endpoint oficial usado na Meta:

```text
POST /webhook
GET /webhook
```

Observação importante: a rota correta é `/webhook`, sem barra final.

## Responsabilidade do Webhook

O webhook é responsável por:

- Receber eventos enviados pela Meta.
- Validar se a requisição tem formato esperado.
- Validar assinatura da Meta, quando habilitada.
- Impedir que payloads inválidos entrem no fluxo.
- Detectar flood antes de inserir mensagem na fila.
- Bloquear cliente floodador na Meta.
- Ignorar mensagens de unidades inativas.
- Ignorar conversas temporariamente bloqueadas pela regra de negócio.
- Inserir mensagens válidas em `fila_mensagens`.

O webhook não processa a conversa em si. O processamento da mensagem é responsabilidade do worker.

## Arquivos Envolvidos

### Entrada HTTP

```text
callback/webhook/urls.py
callback/webhook/views.py
```

### Fluxo principal do POST

```text
callback/webhook/services/post_flow.py
```

### Validação da assinatura Meta

```text
callback/webhook/services/meta_signature.py
```

### Anti-flood e bloqueio Meta

```text
callback/webhook/services/flood_guard.py
core/cache/cache_bloqueio_meta.py
core/cache/cache_flood_memoria.py
core/repositories/bloqueio_meta.py
core/integrations/whatsapp/block.py
core/integrations/whatsapp/tools/conta.py
```

### Alertas locais de reconciliação

```text
callback/webhook/services/alerta_flood_memoria.py
core/integrations/whatsapp/block_report.py
logs/reconciliacao_pendente/
```

### Cache de unidade e conversa bloqueada

```text
core/cache/cache_unidade.py
core/cache/cache_conversas_bloqueadas.py
```

### Inserção na fila

```text
callback/webhook/services/populating_fila_mensagens.py
```

### Administração manual

```text
callback/webhook/admin.py
callback/webhook/models.py
core/integrations/whatsapp/block.py
core/integrations/whatsapp/tools/ativando_numero.py
```

## Fluxo Geral do POST

Ordem atual do fluxo:

```text
1. Receber POST em /webhook
2. Validar Content-Type
3. Validar tamanho máximo do body
4. Validar assinatura Meta
5. Fazer parse do JSON
6. Rodar anti-flood
7. Verificar unidade ativa
8. Verificar conversa temporariamente bloqueada
9. Inserir na fila
10. Retornar resposta HTTP
```

## Fluxo Detalhado

### 1. Entrada em `views.py`

Arquivo:

```text
callback/webhook/views.py
```

A função `callback(request)` recebe todas as requisições do endpoint `/webhook`.

Ela trata:

- `GET`: verificação inicial da Meta.
- `POST`: eventos reais da Meta.
- Outros métodos: resposta `405`.

### 2. Verificação GET da Meta

Quando a Meta configura o webhook, ela faz uma requisição `GET` com:

```text
hub.mode
hub.verify_token
hub.challenge
```

Se `hub.mode` for `subscribe` e o token bater com `VERIFY_TOKEN`, o webhook retorna o `challenge`.

Resposta esperada em caso válido:

```text
HTTP 200
<hub.challenge>
```

Se a verificação falhar:

```text
HTTP 200
Webhook ativo
```

## Validações Iniciais do POST

As validações iniciais são feitas em:

```text
callback/webhook/services/post_flow.py
```

### Content-Type

O webhook espera:

```text
application/json
```

Se vier outro tipo:

```text
HTTP 415
{"status": "unsupported_media_type"}
```

Nesse caso:

- Não faz parse do JSON.
- Não chama Redis.
- Não chama banco.
- Não chama Meta.
- Não insere na fila.

### Tamanho máximo do body

Configuração:

```text
WEBHOOK_MAX_BODY_BYTES = 262144
```

Valor atual:

```text
256 KB
```

Se o body for maior que o permitido:

```text
HTTP 413
{"status": "payload_too_large"}
```

Se o header `Content-Length` vier inválido:

```text
HTTP 400
{"status": "bad_request"}
```

### Assinatura Meta

Arquivo:

```text
callback/webhook/services/meta_signature.py
```

Header esperado:

```text
X-Hub-Signature-256
```

Quando `META_WEBHOOK_SIGNATURE_REQUIRED=True`, o webhook valida a assinatura usando:

```text
META_APP_SECRET
```

Se a assinatura for inválida:

```text
HTTP 403
{"status": "forbidden"}
```

Nesse caso:

- Não chama anti-flood.
- Não chama Redis.
- Não chama banco.
- Não chama Meta.
- Não insere na fila.

Importante: payload com assinatura inválida nunca deve bloquear cliente na Meta, porque a origem ainda não é confiável.

### JSON inválido

Se o body for `application/json`, mas o conteúdo não for JSON válido:

```text
HTTP 200
{"status": "ignored", "reason": "invalid_json"}
```

Esse evento é ignorado e não entra na fila.

## Anti-Flood

Arquivo principal:

```text
callback/webhook/services/flood_guard.py
```

Regra atual:

```text
15 mensagens em 5 segundos
```

Chave lógica do rate limit:

```text
wa_id_cliente + phone_id_unidade
```

Isso significa que o bloqueio é por cliente e por unidade.

Se o mesmo cliente floodar outra unidade, o fluxo se repete para aquela outra unidade.

## Camadas de Detecção de Flood

O anti-flood usa três camadas:

```text
1. Redis
2. Banco
3. Memória local
```

### Redis

Arquivo:

```text
core/cache/cache_bloqueio_meta.py
```

Redis é a camada principal de rate limit.

Ele guarda contadores temporários por janela de tempo.

O cache permanente de cliente bloqueado não é usado. O motivo é simples:

```text
Se o cliente está bloqueado na Meta, a Meta não deve enviar mensagens dele para o webhook.
```

Portanto, o webhook não consulta Redis nem banco para perguntar se toda mensagem pertence a um cliente bloqueado.

### Banco como fallback

Arquivo:

```text
core/repositories/bloqueio_meta.py
```

Se Redis falhar, o banco tenta registrar e contar eventos de flood na tabela de eventos.

Se o banco detectar 15 mensagens em 5 segundos, o sistema tenta bloquear o cliente na Meta.

### Memória local como última barreira

Arquivo:

```text
core/cache/cache_flood_memoria.py
```

Se Redis e banco falharem juntos, a memória local tenta detectar flood.

Essa camada é uma proteção emergencial.

Limitações:

- A memória local é apagada se o processo reiniciar.
- Cada processo Django tem sua própria memória.
- Ela não substitui Redis em produção escalada.

Mesmo assim, ela evita que o sistema fique completamente cego se Redis e banco falharem ao mesmo tempo.

## Bloqueio na Meta

Função usada:

```text
core/integrations/whatsapp/block.py
bloquear_usuario_meta()
```

Regra principal:

```text
Primeiro bloqueia na Meta.
Depois registra no banco.
```

O banco `cliente_bloqueado_meta` só deve registrar bloqueios confirmados pela Meta.

## Cenários do Anti-Flood

### Mensagem normal

```text
Redis conta abaixo do limite
Webhook continua o fluxo
Unidade ativa é validada
Conversa bloqueada é validada
Mensagem entra na fila
```

Resposta final:

```text
HTTP 200
{"status": "ok"}
```

### Redis detecta flood

```text
Redis detecta 15 mensagens em 5 segundos
Webhook tenta bloquear cliente na Meta
Se Meta bloquear, registra em cliente_bloqueado_meta
Mensagem é ignorada
Mensagem não entra na fila
```

Resposta:

```text
HTTP 200
{"status": "ignored", "reason": "flood_redis"}
```

### Redis detecta flood, mas Meta falha

```text
Redis detecta flood
Webhook tenta bloquear na Meta
Meta falha
Webhook não registra no banco
Webhook ignora a mensagem
Próxima mensagem tentará bloquear novamente
```

Resposta:

```text
HTTP 200
{"status": "ignored", "reason": "flood_redis_meta_falhou"}
```

### Redis falha e banco detecta flood

```text
Redis falha
Banco registra/conta evento
Banco detecta 15 mensagens em 5 segundos
Webhook tenta bloquear na Meta
Se Meta bloquear, registra em cliente_bloqueado_meta
Mensagem é ignorada
```

Resposta:

```text
HTTP 200
{"status": "ignored", "reason": "flood_banco"}
```

### Redis falha, banco detecta flood, mas Meta falha

```text
Redis falha
Banco detecta flood
Meta falha ao bloquear
Banco não registra bloqueio
Mensagem é ignorada
Próxima mensagem tentará bloquear novamente
```

Resposta:

```text
HTTP 200
{"status": "ignored", "reason": "flood_banco_meta_falhou"}
```

### Redis falha, banco falha e memória local não detecta flood

```text
Redis falha
Banco falha
Memória local conta abaixo do limite
Webhook continua o fluxo
```

Resposta possível:

```text
HTTP 200
{"status": "ok"}
```

### Redis falha, banco falha e memória local detecta flood

```text
Redis falha
Banco falha
Memória local detecta 15 mensagens em 5 segundos
Webhook tenta bloquear na Meta
Webhook registra alerta em TXT
Mensagem é ignorada
Mensagem não entra na fila
```

Resposta se Meta bloquear:

```text
HTTP 200
{"status": "ignored", "reason": "flood_memoria"}
```

Resposta se Meta falhar:

```text
HTTP 200
{"status": "ignored", "reason": "flood_memoria_meta_falhou"}
```

## Alertas TXT de Flood pela Memória

Arquivo:

```text
callback/webhook/services/alerta_flood_memoria.py
```

Diretório:

```text
logs/reconciliacao_pendente/
```

Quando Redis e banco falham, mas a memória local detecta flood, o webhook registra um alerta em TXT.

O arquivo é diário:

```text
flood_memoria_YYYYMMDD.txt
```

Cada evento crítico é adicionado no mesmo TXT do dia, separado por bloco.

Informações registradas:

- Data e hora.
- Motivo.
- Origem do rate limit.
- Regra aplicada.
- Total de mensagens na janela.
- `meta_ok`.
- `wa_id_cliente`.
- `phone_id_unidade`.
- `id_hash_msg`.
- Erro da Meta, se existir.
- Ação recomendada.

Esse TXT existe porque, se o banco está fora, o webhook não consegue registrar `cliente_bloqueado_meta` naquele momento.

Quando esse TXT aparecer, a ação manual recomendada hoje é executar o utilitário:

```python
from core.integrations.whatsapp.block_report import job_reconciliacao_bloqueios_meta

job_reconciliacao_bloqueios_meta()
```

Comportamento atual desse utilitário:

- Consulta bloqueados reais na Meta por unidade.
- Consulta bloqueios registrados no banco.
- Mostra inconsistências entre Meta e banco.
- Não altera banco automaticamente.
- Não bloqueia nem desbloqueia ninguém automaticamente.

## Unidade Ativa

Arquivo:

```text
core/cache/cache_unidade.py
```

Depois do anti-flood, o webhook verifica se o `phone_number_id` pertence a uma unidade ativa.

Se a unidade não estiver ativa:

```text
HTTP 200
{"status": "ignored"}
```

Nesse caso a mensagem não entra na fila.

## Conversa Temporariamente Bloqueada

Arquivo:

```text
core/cache/cache_conversas_bloqueadas.py
```

Essa regra é de negócio, não é bloqueio Meta.

O cliente fica temporariamente bloqueado quando conclui a etapa final de agendamento.

Regra atual:

```text
Cliente que finalizou na etapa 7 fica bloqueado por 30 dias.
```

Se a conversa estiver bloqueada:

```text
HTTP 200
{"status": "ignored", "reason": "blocked_conversation"}
```

## Inserção na Fila

Arquivo:

```text
callback/webhook/services/populating_fila_mensagens.py
```

Se a mensagem passar por todas as validações, o webhook extrai:

- Telefone do cliente.
- ID da mensagem.
- Tipo da mensagem.
- Texto, quando for mensagem de texto.
- ID do telefone da unidade.
- Telefone exibido da unidade.
- Data/hora recebida.

Depois insere na tabela:

```text
fila_mensagens
```

Se o `id_hash_msg` já existir, o banco ignora a duplicidade com `ON CONFLICT DO NOTHING`.

## Respostas Por Cenário

| Cenário | HTTP | Resposta |
|---|---:|---|
| Verificação GET válida da Meta | 200 | `hub.challenge` |
| Método não permitido | 405 | `{"status": "method_not_allowed"}` |
| Content-Type inválido | 415 | `{"status": "unsupported_media_type"}` |
| Content-Length inválido | 400 | `{"status": "bad_request"}` |
| Body maior que 256 KB | 413 | `{"status": "payload_too_large"}` |
| Assinatura Meta inválida | 403 | `{"status": "forbidden"}` |
| JSON inválido | 200 | `{"status": "ignored", "reason": "invalid_json"}` |
| Flood Redis | 200 | `{"status": "ignored", "reason": "flood_redis"}` |
| Flood Redis com falha Meta | 200 | `{"status": "ignored", "reason": "flood_redis_meta_falhou"}` |
| Flood banco | 200 | `{"status": "ignored", "reason": "flood_banco"}` |
| Flood banco com falha Meta | 200 | `{"status": "ignored", "reason": "flood_banco_meta_falhou"}` |
| Flood memória | 200 | `{"status": "ignored", "reason": "flood_memoria"}` |
| Flood memória com falha Meta | 200 | `{"status": "ignored", "reason": "flood_memoria_meta_falhou"}` |
| Unidade inativa | 200 | `{"status": "ignored"}` |
| Conversa bloqueada | 200 | `{"status": "ignored", "reason": "blocked_conversation"}` |
| Mensagem válida | 200 | `{"status": "ok"}` |

## Logs Importantes

Padrão geral:

```text
evento | motivo=... acao=...
```

Exemplos:

```text
mensagem_ignorada | motivo=content_type_invalido acao=retornar_415
mensagem_ignorada | motivo=body_muito_grande acao=retornar_413
mensagem_ignorada | motivo=assinatura_meta_invalida acao=retornar_403
mensagem_ignorada | motivo=json_invalido acao=nao_enfileirar
mensagem_ignorada | motivo=flood_redis acao=bloqueio_meta_nao_enfileirar
flood_bloqueado | acao=registrar_resultado
flood_bloqueado_memoria | acao=ignorar_alertar
alerta_flood_memoria_registrado | acao=adicionar_evento_txt
request_processado | status=enfileirado acao=fila_insert
```

Dados sensíveis não devem ser logados completos. O projeto usa `short_value()` para encurtar valores sensíveis em logs.

## Django Admin Relacionado

Arquivo:

```text
callback/webhook/admin.py
```

Permissões atuais:

| Tabela | Permissão |
|---|---|
| Unidade | Controle total |
| Cliente | Somente visualização |
| Conversa | Somente visualização |
| Etapa | Somente visualização |
| FilaMensagens | Somente visualização |
| HistoricoMensagens | Somente visualização |
| ClienteBloqueadoMeta | Visualização e exclusão individual |

Ao excluir um `ClienteBloqueadoMeta`:

```text
1. Admin tenta desbloquear cliente na Meta.
2. Se a Meta desbloquear, remove o registro do banco.
3. Se a Meta falhar, mantém o registro no banco.
```

Exclusão em massa está desativada.

## Configurações Importantes

Arquivo:

```text
callback/callback/settings.py
```

Configurações relacionadas ao webhook:

```text
WEBHOOK_MAX_BODY_BYTES
META_APP_SECRET
META_WEBHOOK_SIGNATURE_REQUIRED
```

Recomendação para produção:

```text
META_WEBHOOK_SIGNATURE_REQUIRED=True
WEBHOOK_MAX_BODY_BYTES=262144
```

Segredos como App Secret, access token da Meta e senha do banco não devem ficar hardcoded em produção.

## O Que o Webhook Não Faz

O webhook não:

- Processa conversa.
- Executa fluxo do bot.
- Decide próxima etapa da conversa.
- Envia resposta final ao cliente.
- Consulta toda mensagem para saber se o cliente já está bloqueado na Meta.
- Faz reconciliação automática Meta x banco.

Essas responsabilidades pertencem a outras partes do sistema ou a implementações futuras.

## Implementações Futuras

### 1. Job automático de reconciliação por TXT

Criar um job que:

- Lê arquivos em `logs/reconciliacao_pendente`.
- Consulta bloqueios reais na Meta por unidade.
- Consulta bloqueios registrados em `cliente_bloqueado_meta`.
- Compara Meta x banco.
- Sincroniza banco e Meta automaticamente quando for seguro.
- Move o TXT processado para uma pasta de processados.
- Gera relatório final.

Importante: isso é uma implementação futura. O utilitário atual `job_reconciliacao_bloqueios_meta()` apenas relata inconsistências; ele ainda não sincroniza automaticamente.

Fluxo futuro sugerido:

```text
TXT pendente
-> job lê evento
-> consulta Meta
-> consulta banco
-> identifica divergência
-> corrige caso seguro
-> marca TXT como processado
```

Primeira versão recomendada:

```text
Somente relatório, sem corrigir automaticamente.
```

Depois evoluir para:

```text
Correção automática apenas em casos controlados.
```

### 2. Proteção por IP na infraestrutura

Implementar proteção antes do Django.

Opções:

- AWS WAF.
- CloudFront + WAF.
- Application Load Balancer com regras.
- Nginx rate limit.

Objetivos:

- Reduzir tráfego inválido antes de chegar no Django.
- Bloquear IPs abusivos.
- Criar rate limit por IP/origem.
- Reduzir custo de processamento no backend.

### 3. Proteções adicionais na AWS

Configurações futuras recomendadas:

- Domínio HTTPS definitivo.
- Certificado no AWS Certificate Manager.
- Load Balancer ou CloudFront.
- Security Groups restritos.
- Banco em subnet privada.
- Redis em subnet privada.
- CloudWatch Logs.
- CloudWatch Alarms.
- AWS WAF com managed rules.
- Rate-based rules no WAF.
- Secrets Manager para tokens e segredos.

### 4. Configurações futuras na Meta

Checklist futuro:

- App em modo produção/live.
- Callback URL final usando domínio real.
- Verify token seguro.
- Assinatura obrigatória com App Secret.
- Eventos `messages` configurados.
- WABA e números corretamente conectados.
- Token de System User em vez de token temporário.
- Permissões mínimas necessárias.

### 5. Melhorias futuras no código

Tarefas futuras:

- Mover `VERIFY_TOKEN` para variável de ambiente.
- Mover `META_APP_SECRET` para Secrets Manager ou variável segura.
- Remover qualquer token hardcoded.
- Criar testes automatizados para todos os cenários do webhook.
- Criar health check.
- Criar comando de management para rodar reconciliação.
- Criar rotina de arquivamento dos TXTs antigos.
- Criar métrica para quantidade de floods detectados.
- Criar métrica para falhas de bloqueio na Meta.
- Criar alerta quando o fallback de memória for acionado.

### 6. Observabilidade

Melhorias recomendadas:

- Painel com total de POSTs recebidos.
- Total de mensagens enfileiradas.
- Total de mensagens ignoradas.
- Total de floods por unidade.
- Total de falhas Redis.
- Total de falhas banco.
- Total de falhas Meta.
- Total de alertas TXT criados.

## Resumo Final

O webhook deve permanecer simples e defensivo.

Regra central:

```text
Nada entra na fila antes de passar pelas validações e pelo anti-flood.
```

Regra de bloqueio:

```text
Primeiro bloqueia na Meta.
Depois registra no banco.
```

Regra de segurança:

```text
Payload inválido, assinatura inválida ou body anormal deve ser ignorado/rejeitado e não deve bloquear cliente na Meta.
```

Motivo:

```text
Antes da assinatura Meta ser validada, o payload não é confiável.
Um atacante poderia falsificar um wa_id de um cliente real e tentar induzir o sistema a bloquear esse cliente indevidamente.
Por isso, nesses casos o webhook apenas ignora/rejeita a requisição e não executa bloqueio na Meta.
```

Regra de fallback:

```text
Redis falhou -> banco tenta.
Banco falhou -> memória local tenta.
Memória local detectou -> ignora, tenta Meta e registra TXT.
```
