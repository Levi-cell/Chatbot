# Plano de implementacao: protecoes simples no webhook e POST enxuto

Este plano adiciona validacoes locais baratas no webhook, validacao de assinatura da Meta, mantem `views.py` enxuto e deixa o anti-flood logo depois da assinatura e do parse do JSON.

## Decisao tecnica

Ordem recomendada para POST em producao:

```text
1. Validar Content-Type JSON
2. Validar tamanho maximo do body
3. Validar assinatura Meta
4. Fazer parse do JSON uma unica vez
5. Rodar anti-flood
6. Validar unidade ativa
7. Validar conversa bloqueada temporariamente
8. Inserir na fila
```

Motivo:

- Content-Type responde: "isso parece um POST JSON esperado?"
- Tamanho maximo responde: "esse POST e grande demais para ser um webhook normal?"
- Assinatura Meta responde: "essa request veio mesmo da Meta?"
- Anti-flood responde: "esse wa_id esta enviando uma rajada forte demais para esse phone_id?"
- Unidade ativa responde: "esse phone_id ainda esta ativo no meu sistema?"

Content-Type e tamanho maximo nao usam Redis nem banco. Sao validacoes locais no proprio `request`, antes de assinatura, parse, Redis, banco e fila.

Sem assinatura obrigatoria, nao e recomendavel colocar anti-flood antes de unidade ativa em endpoint publico, porque qualquer pessoa poderia mandar POST falso com `phone_number_id` aleatorio e criar lixo no Redis.

Com assinatura obrigatoria, payload falso morre antes de Redis, banco e fila. Por isso fica aceitavel e coerente rodar anti-flood antes de `unidade_esta_ativa`.

## Custo real entre as duas ordens

Comparacao direta, pensando no codigo atual:

```text
assinatura -> anti-flood -> unidade ativa
assinatura -> unidade ativa -> anti-flood
```

Resposta objetiva: nao existe um vencedor absoluto.

Para mensagem normal de unidade ativa, o custo total e praticamente o mesmo, porque as duas verificacoes vao acontecer de qualquer forma. Mudar a ordem quase nao muda custo.

Para mensagem assinada com unidade inexistente/inativa, `assinatura -> unidade ativa -> anti-flood` e mais barato, porque descarta antes de executar o anti-flood. No seu codigo, `unidade_esta_ativa` tende a ser uma consulta simples no cache Redis quando o cache esta saudavel.

Para flood real contra uma unidade ativa, `assinatura -> anti-flood -> unidade ativa` pode ser melhor depois que o limite estoura, porque corta antes da validacao de unidade, conversa bloqueada, fila e worker. Ainda assim, a economia da validacao de unidade isolada e pequena; o ganho principal e cortar o ataque cedo no fluxo.

Conclusao pratica:

```text
Mais barato em trafego normal valido: praticamente empate.
Mais barato para unidade invalida: unidade ativa antes.
Mais refinado para flood real assinado: anti-flood antes.
```

Minha recomendacao para producao, com assinatura Meta obrigatoria:

```text
assinatura -> anti-flood -> unidade ativa
```

Nao porque sempre seja matematicamente mais barato em toda situacao, mas porque prioriza cortar sobrecarga real antes das regras de negocio.

## Logs esperados

Os logs devem ser objetivos, sem token, sem app secret, sem assinatura completa e sem corpo bruto da mensagem.

Eventos coerentes:

```text
------------ NOVO EVENTO POST ------------
request_bloqueado | motivo=content_type_invalido acao=retornar_415 content_type=text/plain
request_bloqueado | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=300000 limite_bytes=262144
assinatura_meta_falhou | motivo=header_ausente acao=bloquear_request
assinatura_meta_falhou | motivo=formato_invalido acao=bloquear_request
assinatura_meta_falhou | motivo=hash_incompativel acao=bloquear_request
assinatura_meta_config_invalida | motivo=app_secret_vazio acao=bloquear_request
mensagem_ignorada | motivo=flood_redis regra=rajada_curta acao=bloqueio_meta_nao_enfileirar
mensagem_ignorada | motivo=unidade_inativa acao=nao_enfileirar
```

O separador do POST fica sem contador:

```python
logger.info("------------ NOVO EVENTO POST ------------")
```

Motivo: em producao contador por processo pode ficar pouco util e confuso. Timestamp, nome do logger, linha, `wa_id` mascarado, `phone_id` mascarado e `id_hash_msg` mascarado ja dao contexto melhor.

## Passo 1: configurar variaveis em `callback/callback/settings.py`

Adicionar `import os` no topo do arquivo:

```python
import os
from pathlib import Path
```

Adicionar depois de `ALLOWED_HOSTS`:

```python
WEBHOOK_MAX_BODY_BYTES = int(os.getenv("WEBHOOK_MAX_BODY_BYTES", 256 * 1024))

META_APP_SECRET = os.getenv("META_APP_SECRET", "")
META_WEBHOOK_SIGNATURE_REQUIRED = (
    os.getenv("META_WEBHOOK_SIGNATURE_REQUIRED", "False").strip().lower()
    in {"1", "true", "yes", "sim"}
)
```

Uso recomendado:

```text
Dev/local com payload manual:
META_WEBHOOK_SIGNATURE_REQUIRED=False

Producao:
META_WEBHOOK_SIGNATURE_REQUIRED=True
META_APP_SECRET=<app secret do app Meta>
WEBHOOK_MAX_BODY_BYTES=262144
```

Observacao: `META_APP_SECRET` nao deve ser hardcoded no projeto.

## Passo 2: criar `callback/webhook/services/meta_signature.py`

Codigo completo do arquivo novo:

```python
import hashlib
import hmac
import logging

from django.conf import settings


logger = logging.getLogger("webhook.meta_signature")

SIGNATURE_HEADER = "X-Hub-Signature-256"
SIGNATURE_PREFIX = "sha256="


def validar_assinatura_meta(request):
    if not settings.META_WEBHOOK_SIGNATURE_REQUIRED:
        logger.debug(
            "assinatura_meta_desativada | motivo=config_dev acao=permitir_request",
        )
        return True

    app_secret = settings.META_APP_SECRET

    if not app_secret:
        logger.error(
            "assinatura_meta_config_invalida | motivo=app_secret_vazio acao=bloquear_request",
        )
        return False

    assinatura_meta = request.headers.get(SIGNATURE_HEADER, "")

    if not assinatura_meta:
        logger.warning(
            "assinatura_meta_falhou | motivo=header_ausente acao=bloquear_request",
        )
        return False

    if not assinatura_meta.startswith(SIGNATURE_PREFIX):
        logger.warning(
            "assinatura_meta_falhou | motivo=formato_invalido acao=bloquear_request",
        )
        return False

    assinatura_local = SIGNATURE_PREFIX + hmac.new(
        app_secret.encode("utf-8"),
        request.body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(assinatura_meta, assinatura_local):
        logger.warning(
            "assinatura_meta_falhou | motivo=hash_incompativel acao=bloquear_request",
        )
        return False

    logger.debug("assinatura_meta_ok | acao=permitir_request")
    return True
```

## Passo 3: criar `callback/webhook/services/post_flow.py`

Objetivo:

- Manter `views.py` enxuto.
- Concentrar toda a logica do POST em uma funcao chamada em uma linha.
- Validar `Content-Type` antes de qualquer processamento.
- Validar tamanho maximo do body antes da assinatura e do parse.
- Validar assinatura antes do parse.
- Rodar anti-flood antes de `unidade_esta_ativa`.
- Manter conversa bloqueada e fila depois.

Codigo completo do arquivo novo:

```python
import json
import logging

from django.conf import settings
from django.http import JsonResponse

from core.cache.cache_conversas_bloqueadas import conversa_esta_bloqueada_cache
from core.cache.cache_unidade import unidade_esta_ativa
from core.logging_config import short_value
from .flood_guard import responder_se_flood
from .meta_signature import validar_assinatura_meta
from .populating_fila_mensagens import povoando_fila


logger = logging.getLogger("webhook.post_flow")


def responder_post_webhook(request):
    logger.info("------------ NOVO EVENTO POST ------------")

    if resposta := _validar_content_type(request):
        return resposta

    if resposta := _validar_tamanho_body(request):
        return resposta

    if not validar_assinatura_meta(request):
        return JsonResponse({"status": "forbidden"}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))

        phone_number_id = _extrair_phone_number_id(data)
        cliente_telefone = _extrair_cliente_telefone(data)

        if resposta_flood := responder_se_flood(data):
            return resposta_flood

        if not unidade_esta_ativa(phone_number_id):
            logger.info(
                "mensagem_ignorada | motivo=unidade_inativa acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({"status": "ignored"})

        if cliente_telefone and conversa_esta_bloqueada_cache(
            cliente_telefone,
            phone_number_id,
        ):
            logger.info(
                "mensagem_ignorada | motivo=conversa_bloqueada acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({
                "status": "ignored",
                "reason": "blocked_conversation",
            })

        if povoando_fila(data):
            logger.info(
                "request_processado | status=enfileirado acao=fila_insert cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
        else:
            logger.warning(
                "request_processado | status=nao_enfileirado acao=ignorar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )

    except Exception:
        logger.exception(
            "request_erro | acao=retornar_ok metodo=%s path=%s",
            request.method,
            request.path,
        )

    return JsonResponse({"status": "ok"})


def _validar_content_type(request):
    content_type = (request.content_type or "").lower()

    if content_type.startswith("application/json"):
        return None

    logger.warning(
        "request_bloqueado | motivo=content_type_invalido acao=retornar_415 content_type=%s",
        content_type or None,
    )
    return JsonResponse({"status": "unsupported_media_type"}, status=415)


def _validar_tamanho_body(request):
    limite_bytes = settings.WEBHOOK_MAX_BODY_BYTES
    tamanho_header = request.headers.get("Content-Length")

    if tamanho_header:
        try:
            tamanho_bytes = int(tamanho_header)

        except ValueError:
            logger.warning(
                "request_bloqueado | motivo=content_length_invalido acao=retornar_400 content_length=%s",
                tamanho_header,
            )
            return JsonResponse({"status": "bad_request"}, status=400)

        if tamanho_bytes > limite_bytes:
            logger.warning(
                "request_bloqueado | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=%s limite_bytes=%s origem=content_length",
                tamanho_bytes,
                limite_bytes,
            )
            return JsonResponse({"status": "payload_too_large"}, status=413)

    tamanho_real = len(request.body)

    if tamanho_real > limite_bytes:
        logger.warning(
            "request_bloqueado | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=%s limite_bytes=%s origem=request_body",
            tamanho_real,
            limite_bytes,
        )
        return JsonResponse({"status": "payload_too_large"}, status=413)

    return None


def _extrair_phone_number_id(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    metadata = value.get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    contacts = value.get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None
```

## Passo 4: modificar `callback/webhook/views.py`

Objetivo:

- Deixar a view apenas com roteamento HTTP.
- `GET` continua validando o webhook com `VERIFY_TOKEN`.
- `POST` chama a funcao do fluxo em uma linha.

Codigo completo do arquivo modificado:

```python
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .services.post_flow import responder_post_webhook


logger = logging.getLogger("webhook.request")

VERIFY_TOKEN = "123456"


@csrf_exempt
def callback(request):
    logger.info("request_recebido | metodo=%s path=%s", request.method, request.path)

    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("verificacao_meta_ok | mode=%s", mode)
            return HttpResponse(challenge)

        logger.warning("verificacao_meta_falhou | mode=%s", mode)
        return HttpResponse("Webhook ativo")

    if request.method == "POST":
        return responder_post_webhook(request)

    logger.warning("metodo_nao_permitido | metodo=%s", request.method)
    return JsonResponse({"status": "method_not_allowed"}, status=405)
```

## Passo 5: ajustar `callback/webhook/services/flood_guard.py`

Como o anti-flood passa a rodar antes de `unidade_esta_ativa`, o bloqueio precisa ser defensivo: se o `phone_id` nao estiver cadastrado na tabela `unidade`, a mensagem que estourou flood deve ser ignorada, mas o sistema nao deve chamar bloqueio Meta sem conseguir registrar a unidade no banco.

Tambem simplificar a regra de flood para uma unica janela:

```text
15 mensagens em 5 segundos
```

Essa regra cobre ataques de rajada forte e reduz falso positivo em cliente real que encaminha algumas mensagens. Ela nao detecta spam lento sustentado, como uma mensagem a cada poucos segundos por varios minutos. Essa troca e intencional para manter o bloqueio Meta permanente menos agressivo.

Substituir a constante `REGRAS_FLOOD` por:

```python
REGRAS_FLOOD = (
    {
        "nome": "rajada_curta",
        "limite": 15,
        "janela_segundos": 5,
    },
)
```

Substituir a funcao `_registrar_bloqueio_banco` por esta versao:

```python
def _registrar_bloqueio_banco(wa_id_cliente, phone_id_unidade):
    conn = None
    registro_vazio = {
        "id_bloqueio": None,
        "id_cliente": None,
        "id_unidade": None,
    }

    try:
        conn = get_conn()
        cursor = conn.cursor()

        id_cliente = buscar_id_cliente_por_wa_id(wa_id_cliente, cursor)
        unidade = buscar_unidade_bloqueio_por_phone_id(
            phone_id_unidade,
            cursor,
        )

        if not unidade:
            logger.warning(
                "bloqueio_meta_registro_ignorado | motivo=unidade_nao_cadastrada acao=nao_bloquear_meta wa_id_cliente=%s phone_id_unidade=%s",
                short_value(wa_id_cliente),
                short_value(phone_id_unidade),
            )
            conn.rollback()
            return registro_vazio

        id_unidade, phone_id_cadastrado = unidade

        id_bloqueio = registrar_cliente_bloqueado_meta_banco(
            id_cliente,
            wa_id_cliente,
            id_unidade,
            phone_id_cadastrado,
            cursor,
        )

        conn.commit()

        return {
            "id_bloqueio": id_bloqueio,
            "id_cliente": id_cliente,
            "id_unidade": id_unidade,
        }

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.exception(
            "bloqueio_meta_registro_banco_falhou | acao=nao_bloquear_meta wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return registro_vazio

    finally:
        if conn:
            conn.close()
```

Substituir a funcao `_bloquear_e_registrar` por esta versao:

```python
def _bloquear_e_registrar(wa_id_cliente, phone_id_unidade, origem, total, regra):
    registro = _registrar_bloqueio_banco(wa_id_cliente, phone_id_unidade)

    if not registro["id_unidade"]:
        logger.warning(
            "flood_detectado_sem_unidade_ativa | acao=nao_bloquear_meta origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s",
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
        )
        return {
            "bloqueado": True,
            "motivo": "flood_sem_unidade_ativa",
            "total": total,
            "regra": regra,
            "id_bloqueio": None,
            "id_cliente": None,
            "id_unidade": None,
            "meta_ok": False,
        }

    meta_ok = False

    try:
        bloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
        meta_ok = True

    except Exception as exc:
        logger.exception(
            "bloqueio_meta_falhou | acao=continuar_bloqueio_local origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s erro=%s",
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
            exc,
        )

    if registro["id_bloqueio"] or meta_ok:
        registrar_cliente_bloqueado_meta_cache(
            wa_id_cliente,
            phone_id_unidade,
        )

    logger.warning(
        "flood_bloqueado | acao=registrar_resultado origem=%s regra=%s wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s total=%s id_bloqueio=%s meta_ok=%s",
        origem,
        regra,
        short_value(wa_id_cliente),
        registro["id_cliente"],
        registro["id_unidade"],
        short_value(phone_id_unidade),
        total,
        registro["id_bloqueio"],
        meta_ok,
    )

    return {
        "bloqueado": True,
        "motivo": f"flood_{origem}",
        "total": total,
        "regra": regra,
        "id_bloqueio": registro["id_bloqueio"],
        "id_cliente": registro["id_cliente"],
        "id_unidade": registro["id_unidade"],
        "meta_ok": meta_ok,
    }
```

## Passo 6: testes

Rodar checagens estaticas:

```powershell
C:\Chatbot\venv\.venv\Scripts\python.exe -m compileall -q .
C:\Chatbot\venv\.venv\Scripts\python.exe callback\manage.py check
```

Teste com assinatura desligada:

```text
META_WEBHOOK_SIGNATURE_REQUIRED=False
POST manual sem header deve continuar funcionando.
```

Teste com assinatura ligada e sem header:

```text
META_WEBHOOK_SIGNATURE_REQUIRED=True
META_APP_SECRET preenchido
POST sem X-Hub-Signature-256 deve retornar 403.
```

Teste com assinatura ligada e header errado:

```text
POST com X-Hub-Signature-256 falso deve retornar 403.
```

Teste com assinatura ligada e header correto:

```text
POST com HMAC correto deve seguir o fluxo normal.
```

Teste de ordem do fluxo com mocks:

```text
1. Content-Type invalido retorna 415 e nao chama assinatura, anti-flood, unidade, banco, fila nem Meta.
2. Body acima de 256 KB retorna 413 e nao chama assinatura, anti-flood, unidade, banco, fila nem Meta.
3. Assinatura invalida nao chama anti-flood, unidade, banco, fila nem Meta.
4. Assinatura valida chama anti-flood antes de unidade ativa.
5. Flood detectado nao chama conversa bloqueada nem fila.
6. Mensagem normal de unidade ativa segue para conversa bloqueada e fila.
7. Mensagem normal de unidade inativa nao segue para fila.
8. O log "------------ NOVO EVENTO POST ------------" aparece em todo POST.
```

## O que este plano nao muda

- Nao muda worker.
- Nao muda tabela de bloqueio.
- Nao muda regra de conversa bloqueada temporariamente.
- Nao muda admin.
- Nao adiciona Redis nem banco para Content-Type e tamanho maximo.
- Simplifica o limite de flood para:

```text
15 mensagens em 5 segundos
```

## Resumo

Em producao, Content-Type e tamanho maximo devem ser as primeiras barreiras locais do POST.

A assinatura Meta vem logo depois e deve ser a primeira barreira de autenticidade.

Depois dela, o anti-flood pode vir antes da unidade ativa para cortar sobrecarga real cedo no fluxo.

O `views.py` continua enxuto: o POST chama `responder_post_webhook(request)` em uma linha, e o fluxo pesado fica dentro de `callback/webhook/services/post_flow.py`.
