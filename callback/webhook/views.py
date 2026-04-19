from .webhook_support_functions.povoando_fila_mensagens import povoando_fila
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
import logging
import json

logger = logging.getLogger(__name__)

VERIFY_TOKEN = "123456"

@csrf_exempt
def callback(request):

    # ✅ Log sempre (independente de erro)
    logger.info(f"Webhook chamado | metodo={request.method}")

    # 🔐 Verificação Meta
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("Webhook verificado com sucesso")
            return HttpResponse(challenge)

        logger.warning("Falha na verificação do webhook")
        return HttpResponse("Webhook ativo ✅")

    # 📩 Receber mensagem
    if request.method == "POST":
        try:
            data = json.loads(request.body.decode("utf-8"))
            print(data)


            logger.info("Evento recebido no webhook")

            povoando_fila(data)

        except Exception:
            # ✅ Log correto de erro (com stack trace)
            logger.error("Erro no webhook", exc_info=True)

        return JsonResponse({"status": "ok"})
