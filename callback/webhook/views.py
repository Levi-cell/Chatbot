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
