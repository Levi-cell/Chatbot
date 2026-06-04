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
