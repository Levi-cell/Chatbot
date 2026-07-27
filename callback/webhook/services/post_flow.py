import json
import logging

from django.conf import settings
from django.http import JsonResponse

from core.cache.runtime.cache_conversas_bloqueadas import (
    ValidacaoBloqueioConversaIndisponivel,
    conversa_esta_bloqueada_cache,
)
from core.cache.runtime.cache_webhook_erro_inesperado import (
    MAX_RESPOSTAS_503_POR_WAMID,
    registrar_tentativa_erro_inesperado,
)
from core.cache.cache_unidade import (
    ValidacaoUnidadeIndisponivel,
    unidade_esta_ativa,
)
from core.database.connection_aws import get_conn
from core.logging_config import short_value
from .bloqueio_meta_guard import (
    responder_se_cliente_marcado_para_bloqueio,
)
from .flood_guard import responder_se_flood
from .meta_signature import validar_assinatura_meta
from .populating_fila_mensagens import preparar_dados_fila, povoando_fila


logger = logging.getLogger("webhook.post_flow")
fila_logger = logging.getLogger("webhook.fila")

TIPO_EVENTO_MENSAGEM = "messages"
TIPO_EVENTO_STATUS = "statuses"
TIPO_EVENTO_DESCONHECIDO = "unknown"


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

    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        logger.warning(
            "mensagem_ignorada | motivo=json_invalido acao=nao_enfileirar erro=%s",
            exc,
        )
        return JsonResponse({
            "status": "ignored",
            "reason": "invalid_json",
        })

    phone_number_id = None
    cliente_telefone = None

    try:
        tipo_evento = _classificar_evento_meta(data)

        if tipo_evento == TIPO_EVENTO_STATUS:
            return _responder_status_meta_sem_processar(data)

        if tipo_evento != TIPO_EVENTO_MENSAGEM:
            logger.info(
                "evento_meta_ignorado | motivo=evento_sem_messages_ou_statuses acao=retornar_200",
            )
            return JsonResponse({"status": "ok"})

        phone_number_id = _extrair_phone_number_id(data)
        cliente_telefone = _extrair_cliente_telefone(data)
        nome_cliente = _extrair_nome_cliente(data)

        if resposta_bloqueio := responder_se_cliente_marcado_para_bloqueio(
            cliente_telefone,
            phone_number_id,
            nome_cliente=nome_cliente,
        ):
            return resposta_bloqueio

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

    except ValidacaoBloqueioConversaIndisponivel as exc:
        logger.error(
            "request_indisponivel | motivo=validacao_bloqueio_conversa_indisponivel acao=retornar_503_para_reentrega cliente=%s phone_number_id=%s erro=%s",
            short_value(cliente_telefone),
            short_value(phone_number_id),
            exc,
        )
        return JsonResponse({
            "status": "unavailable",
            "reason": "conversation_block_validation_unavailable",
        }, status=503)

    except Exception as exc:
        id_hash_msg = _extrair_id_hash_msg_seguro(data)
        tentativa = registrar_tentativa_erro_inesperado(
            id_hash_msg,
        )

        if tentativa["retornar_503"]:
            logger.exception(
                "request_erro | "
                "acao=retornar_503_para_reentrega "
                "metodo=%s path=%s id_hash_msg=%s "
                "tentativa=%s limite_503=%s",
                request.method,
                request.path,
                short_value(id_hash_msg),
                tentativa["tentativa"],
                MAX_RESPOSTAS_503_POR_WAMID,
            )
            return JsonResponse(
                {
                    "status": "unavailable",
                    "reason": "unexpected_error_retry",
                    "attempt": tentativa["tentativa"],
                },
                status=503,
            )

        logger.error(
            "request_erro | "
            "acao=retornar_200_e_ignorar "
            "metodo=%s path=%s id_hash_msg=%s "
            "tentativa=%s motivo=%s",
            request.method,
            request.path,
            short_value(id_hash_msg),
            tentativa["tentativa"],
            tentativa["motivo"],
            exc_info=(
                type(exc),
                exc,
                exc.__traceback__,
            ),
        )
        reason = (
            "unexpected_error_retry_exhausted"
            if tentativa["motivo"]
            == "limite_503_esgotado"
            else "unexpected_error_retry_unavailable"
        )
        return JsonResponse({
            "status": "ignored",
            "reason": reason,
        })

    return JsonResponse({"status": "ok"})


def _classificar_evento_meta(data):
    value = _extrair_value(data)
    possui_mensagens = bool(value.get("messages"))
    possui_statuses = bool(value.get("statuses"))

    if possui_mensagens and not possui_statuses:
        return TIPO_EVENTO_MENSAGEM

    if possui_statuses and not possui_mensagens:
        return TIPO_EVENTO_STATUS

    return TIPO_EVENTO_DESCONHECIDO


def _responder_status_meta_sem_processar(data):
    statuses = _extrair_value(data).get("statuses") or []
    nomes_status = sorted({
        status.get("status")
        for status in statuses
        if status.get("status")
    })
    primeiro_status = statuses[0] if statuses else {}

    logger.info(
        "status_meta_recebido | acao=ignorar_na_v1 total=%s statuses=%s id_hash_msg_bot=%s",
        len(statuses),
        ",".join(nomes_status) or None,
        short_value(primeiro_status.get("id")),
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


def _extrair_value(data):
    return (
        data.get("entry", [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )


def _extrair_phone_number_id(data):
    metadata = _extrair_value(data).get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    contacts = _extrair_value(data).get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None



def _extrair_id_hash_msg_seguro(data):
    try:
        value = _extrair_value(data)
        messages = value.get("messages")

        if (
            not isinstance(messages, list)
            or not messages
            or not isinstance(messages[0], dict)
        ):
            return None

        id_hash_msg = messages[0].get("id")

        if id_hash_msg is None:
            return None

        id_hash_msg = str(id_hash_msg).strip()
        return id_hash_msg or None

    except Exception:
        return None


def _extrair_nome_cliente(data):
    contacts = _extrair_value(data).get("contacts") or []

    if not contacts or not isinstance(contacts[0], dict):
        return None

    profile = contacts[0].get("profile") or {}
    nome_cliente = profile.get("name")

    if nome_cliente is None:
        return None

    nome_cliente = str(nome_cliente).strip()
    return nome_cliente[:200] or None
