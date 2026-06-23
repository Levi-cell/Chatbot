import json
import logging

from django.conf import settings
from django.http import JsonResponse

from core.cache.runtime.cache_conversas_bloqueadas import conversa_esta_bloqueada_cache
from core.cache.cache_unidade import (
    ValidacaoUnidadeIndisponivel,
    unidade_esta_ativa,
)
from core.database.connection_aws import get_conn
from core.logging_config import short_value
from .flood_guard import responder_se_flood
from .meta_signature import validar_assinatura_meta
from .populating_fila_mensagens import preparar_dados_fila, povoando_fila


logger = logging.getLogger("webhook.post_flow")
fila_logger = logging.getLogger("webhook.fila")


def responder_post_webhook(request):
    print("\n\n\n-----------------------------------------------------------------NOVO EVENTO-----------------------------------------------------------------\n\n\n")

    if resposta := _validar_content_type(request):
        return resposta

    if resposta := _validar_tamanho_body(request):
        return resposta

    if not validar_assinatura_meta(request):
        logger.warning(
            "mensagem_ignorada | motivo=assinatura_meta_invalida acao=retornar_403 path=%s",
            request.path,
        )
        return JsonResponse({"status": "forbidden"}, status=403)

    try:
        data = json.loads(request.body.decode("utf-8"))

    except json.JSONDecodeError as exc:
        logger.warning(
            "mensagem_ignorada | motivo=json_invalido acao=nao_enfileirar erro=%s",
            exc,
        )
        return JsonResponse({
            "status": "ignored",
            "reason": "invalid_json",
        })

    try:
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

        preparacao_fila = preparar_dados_fila(data)

        if preparacao_fila["status"] == "ready":
            resultado_fila = _executar_transacao_fila(preparacao_fila["dados"])

        else:
            resultado_fila = {
                "status": "ignored",
                "reason": preparacao_fila["reason"],
            }

        if resultado_fila["status"] == "inserted":
            logger.info(
                "request_processado | status=enfileirado acao=fila_insert cliente=%s phone_number_id=%s",
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )

        elif resultado_fila["status"] == "ignored":
            logger.info(
                "mensagem_ignorada | motivo=%s acao=nao_enfileirar cliente=%s phone_number_id=%s",
                resultado_fila["reason"],
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )

        else:
            logger.error(
                "request_indisponivel | motivo=%s acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s",
                resultado_fila["reason"],
                short_value(cliente_telefone),
                short_value(phone_number_id),
            )
            return JsonResponse({
                "status": "unavailable",
                "reason": resultado_fila["reason"],
            }, status=503)

    except ValidacaoUnidadeIndisponivel as exc:
        logger.error(
            "request_indisponivel | motivo=validacao_unidade_indisponivel acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_number_id),
            exc,
        )
        return JsonResponse({
            "status": "unavailable",
            "reason": "unit_validation_unavailable",
        }, status=503)

    except Exception:
        logger.exception(
            "request_erro | acao=retornar_ok metodo=%s path=%s",
            request.method,
            request.path,
        )

    return JsonResponse({"status": "ok"})


def _executar_transacao_fila(dados):
    conn_webhook = None

    try:
        conn_webhook = get_conn(application_name="webhook_chatbot")
        cursor_webhook = conn_webhook.cursor()
        resultado = povoando_fila(dados, cursor_webhook)
        conn_webhook.commit()

        if resultado["status"] == "inserted":
            fila_logger.info(
                "fila_insert_ok | acao=enfileirar id_msg=%s cliente=%s phone_number_id=%s tipo=%s",
                short_value(dados["id_hash_msg"]),
                short_value(dados["cliente_telefone"]),
                short_value(dados["id_phone_unidade"]),
                dados["tipo_mensagem"],
            )

        return resultado

    except Exception:
        if conn_webhook:
            conn_webhook.rollback()

        fila_logger.exception(
            "fila_insert_erro | acao=rollback id_msg=%s",
            short_value(dados.get("id_hash_msg") if dados else None),
        )
        return {
            "status": "error",
            "reason": "insert_exception",
        }

    finally:
        if conn_webhook:
            conn_webhook.close()


def _validar_content_type(request):
    content_type = (request.content_type or "").lower()

    if content_type.startswith("application/json"):
        return None

    logger.warning(
        "mensagem_ignorada | motivo=content_type_invalido acao=retornar_415 content_type=%s",
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
                "mensagem_ignorada | motivo=content_length_invalido acao=retornar_400 content_length=%s",
                tamanho_header,
            )
            return JsonResponse({"status": "bad_request"}, status=400)

        if tamanho_bytes > limite_bytes:
            logger.warning(
                "mensagem_ignorada | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=%s limite_bytes=%s origem=content_length",
                tamanho_bytes,
                limite_bytes,
            )
            return JsonResponse({"status": "payload_too_large"}, status=413)

    tamanho_real = len(request.body)

    if tamanho_real > limite_bytes:
        logger.warning(
            "mensagem_ignorada | motivo=body_muito_grande acao=retornar_413 tamanho_bytes=%s limite_bytes=%s origem=request_body",
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
