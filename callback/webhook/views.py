import json
import logging

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from core.cache.cache_conversas_bloqueadas import conversa_esta_bloqueada_cache
from core.cache.cache_unidade import unidade_esta_ativa
from core.logging_config import short_value
from .services.flood_guard import responder_se_flood
from .services.populating_fila_mensagens import povoando_fila


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

    if request.method != "POST":
        logger.warning("metodo_nao_permitido | metodo=%s", request.method)
        return JsonResponse({"status": "method_not_allowed"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))

        phone_number_id = _extrair_phone_number_id(data)
        cliente_telefone = _extrair_cliente_telefone(data)

        if not unidade_esta_ativa(phone_number_id):
            logger.info(
                "mensagem_ignorada | motivo=unidade_inativa acao=nao_enfileirar cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({"status": "ignored"})

        if resposta_flood := responder_se_flood(data):
            return resposta_flood

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


def _extrair_phone_number_id(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    metadata = value.get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    contacts = value.get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None
