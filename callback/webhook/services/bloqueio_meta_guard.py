import logging

from django.http import JsonResponse

from core.database.connection_aws import get_conn
from core.integrations.whatsapp.tools.usuarios import bloquear_usuario_meta
from core.logging_config import short_value
from core.repositories.seguranca.bloqueio_meta import (
    cliente_bloqueado_meta_existe_banco,
    registrar_cliente_bloqueado_meta_banco,
)
from core.repositories.seguranca.suspeita_bot import (
    buscar_conversa_no_limite_sem_avanco,
)


logger = logging.getLogger("webhook.bloqueio_meta_guard")


def responder_se_cliente_marcado_para_bloqueio(
    wa_id_cliente,
    phone_id_unidade,
    nome_cliente=None,
):
    """
    Intercepta a denylist existente ou promove uma conversa no limite.

    O banco é confirmado antes da chamada externa à Meta. Se a Meta recusar,
    a mensagem continua sendo ignorada e a próxima mensagem fará nova
    tentativa.
    """
    if not wa_id_cliente or not phone_id_unidade:
        return None

    consulta = _consultar_cliente_marcado_para_bloqueio(
        wa_id_cliente,
        phone_id_unidade,
        nome_cliente=nome_cliente,
    )

    if not consulta["banco_ok"]:
        return JsonResponse(
            {
                "status": "unavailable",
                "reason": "blocklist_validation_unavailable",
            },
            status=503,
        )

    if not consulta["marcado"]:
        return None

    meta_ok = False

    try:
        bloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
        meta_ok = True
        logger.warning(
            "bloqueio_meta_reconfirmado | acao=bloquear_novamente "
            "wa_id_cliente=%s phone_id_unidade=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
        )

    except Exception as exc:
        logger.warning(
            "bloqueio_meta_retentativa_falhou | "
            "acao=ignorar_e_tentar_na_proxima_mensagem "
            "wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )

    logger.warning(
        "mensagem_ignorada | motivo=cliente_marcado_bloqueio_meta "
        "acao=nao_enfileirar wa_id_cliente=%s phone_id_unidade=%s meta_ok=%s",
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        meta_ok,
    )
    return JsonResponse({
        "status": "ignored",
        "reason": "cliente_marcado_bloqueio_meta",
    })


def _consultar_cliente_marcado_para_bloqueio(
    wa_id_cliente,
    phone_id_unidade,
    nome_cliente=None,
):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        marcado = cliente_bloqueado_meta_existe_banco(
            wa_id_cliente,
            phone_id_unidade,
            cursor,
        )

        if not marcado:
            suspeita = buscar_conversa_no_limite_sem_avanco(
                wa_id_cliente,
                phone_id_unidade,
                cursor,
            )

            if suspeita:
                id_bloqueio = registrar_cliente_bloqueado_meta_banco(
                    suspeita["id_cliente"],
                    wa_id_cliente,
                    suspeita["id_unidade"],
                    suspeita["phone_id_unidade"],
                    cursor,
                    nome_cliente=(
                        suspeita["nome_cliente"] or nome_cliente
                    ),
                )

                if not id_bloqueio:
                    raise RuntimeError(
                        "Promoção de suspeita não retornou id_bloqueio"
                    )

                marcado = True
                logger.warning(
                    "suspeita_bot_promovida | "
                    "acao=registrar_denylist_antes_da_meta "
                    "id_bloqueio=%s id_conversa=%s turnos_sem_avanco=%s "
                    "wa_id_cliente=%s phone_id_unidade=%s",
                    id_bloqueio,
                    suspeita["id_conversa"],
                    suspeita["turnos_sem_avanco"],
                    short_value(wa_id_cliente),
                    short_value(phone_id_unidade),
                )

        conn.commit()
        return {
            "banco_ok": True,
            "marcado": marcado,
        }

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.exception(
            "bloqueio_meta_consulta_falhou | "
            "acao=retornar_503_para_reentrega "
            "wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            "banco_ok": False,
            "marcado": False,
        }

    finally:
        if conn:
            conn.close()
