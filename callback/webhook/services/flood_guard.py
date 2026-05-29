import logging

from django.http import JsonResponse

from core.cache.cache_bloqueio_meta import (
    avaliar_flood_redis,
    registrar_cliente_bloqueado_meta_cache,
)
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.pywa_tools import bloquear_usuario_meta
from core.logging_config import short_value
from core.repositories.bloqueio_meta import (
    buscar_id_cliente_por_wa_id,
    buscar_unidade_bloqueio_por_phone_id,
    cliente_bloqueado_meta_existe_banco,
    contar_eventos_flood_banco,
    limpar_eventos_flood_antigos,
    registrar_cliente_bloqueado_meta_banco,
    registrar_evento_flood_banco,
)


logger = logging.getLogger("webhook.flood_guard")

REGRAS_FLOOD = (
    {
        "nome": "rajada_extrema",
        "limite": 60,
        "janela_segundos": 1,
    },
    {
        "nome": "rajada_curta",
        "limite": 10,
        "janela_segundos": 5,
    },
    {
        "nome": "spam_minuto",
        "limite": 30,
        "janela_segundos": 60,
    },
)


def responder_se_flood(data):
    phone_id_unidade = _extrair_phone_number_id(data)
    wa_id_cliente = _extrair_cliente_telefone(data)
    id_hash_msg = _extrair_id_hash_msg(data)

    flood = bloquear_cliente_se_flood(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
    )

    if not flood["bloqueado"]:
        return None

    logger.warning(
        "mensagem_ignorada | motivo=%s regra=%s acao=bloqueio_meta_nao_enfileirar cliente=%s phone_number_id=%s total=%s",
        flood["motivo"],
        flood.get("regra"),
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        flood["total"],
    )

    return JsonResponse({
        "status": "ignored",
        "reason": flood["motivo"],
    })


def bloquear_cliente_se_flood(wa_id_cliente, phone_id_unidade, id_hash_msg):
    if not wa_id_cliente or not phone_id_unidade or not id_hash_msg:
        return {
            "bloqueado": False,
            "motivo": "dados_invalidos",
            "total": 0,
            "regra": None,
        }

    rate_redis = avaliar_flood_redis(
        wa_id_cliente,
        phone_id_unidade,
        regras=REGRAS_FLOOD,
    )

    if rate_redis["redis_ok"]:
        if rate_redis["bloqueado"]:
            return {
                "bloqueado": True,
                "motivo": rate_redis["motivo"],
                "total": rate_redis["total"],
                "regra": rate_redis["regra"],
            }

        if rate_redis["flood"]:
            return _bloquear_e_registrar(
                wa_id_cliente,
                phone_id_unidade,
                origem="redis",
                total=rate_redis["total"],
                regra=rate_redis["regra"],
            )

        return {
            "bloqueado": False,
            "motivo": "abaixo_limite_redis",
            "total": rate_redis["total"],
            "regra": None,
        }

    rate_banco = _avaliar_flood_banco(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
    )

    if rate_banco["bloqueado"]:
        return {
            "bloqueado": True,
            "motivo": rate_banco["motivo"],
            "total": rate_banco["total"],
            "regra": rate_banco["regra"],
        }

    if rate_banco["flood"]:
        return _bloquear_e_registrar(
            wa_id_cliente,
            phone_id_unidade,
            origem="banco",
            total=rate_banco["total"],
            regra=rate_banco["regra"],
        )

    return {
        "bloqueado": False,
        "motivo": rate_banco["motivo"],
        "total": rate_banco["total"],
        "regra": None,
    }


def _avaliar_flood_banco(wa_id_cliente, phone_id_unidade, id_hash_msg):
    conn = None

    try:
        conn = get_conn()
        cursor = conn.cursor()

        if cliente_bloqueado_meta_existe_banco(
            wa_id_cliente,
            phone_id_unidade,
            cursor,
        ):
            return {
                "banco_ok": True,
                "bloqueado": True,
                "flood": False,
                "total": 0,
                "motivo": "cliente_ja_bloqueado_banco",
                "regra": None,
            }

        registrar_evento_flood_banco(
            wa_id_cliente,
            phone_id_unidade,
            id_hash_msg,
            cursor,
        )
        maior_total = 0
        total = 0
        regra_estourada = None

        for regra in REGRAS_FLOOD:
            total = contar_eventos_flood_banco(
                wa_id_cliente,
                phone_id_unidade,
                cursor,
                janela_segundos=regra["janela_segundos"],
            )

            maior_total = max(maior_total, total)

            if total >= regra["limite"]:
                regra_estourada = regra
                break

        limpar_eventos_flood_antigos(cursor)

        conn.commit()

        return {
            "banco_ok": True,
            "bloqueado": False,
            "flood": regra_estourada is not None,
            "total": total if regra_estourada else maior_total,
            "motivo": "banco",
            "regra": regra_estourada["nome"] if regra_estourada else None,
        }

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.warning(
            "rate_limit_banco_falhou | acao=seguir_fluxo wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            "banco_ok": False,
            "bloqueado": False,
            "flood": False,
            "total": 0,
            "motivo": "banco_indisponivel",
            "regra": None,
        }

    finally:
        if conn:
            conn.close()


def _bloquear_e_registrar(wa_id_cliente, phone_id_unidade, origem, total, regra):
    registro = _registrar_bloqueio_banco(wa_id_cliente, phone_id_unidade)
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
            raise ValueError(f"Unidade ativa nao encontrada: {phone_id_unidade}")

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
            "bloqueio_meta_registro_banco_falhou | acao=bloquear_meta_mesmo_assim wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return registro_vazio

    finally:
        if conn:
            conn.close()


def _extrair_phone_number_id(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    metadata = value.get("metadata", {})
    return metadata.get("phone_number_id")


def _extrair_cliente_telefone(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    contacts = value.get("contacts", [{}])
    return contacts[0].get("wa_id") if contacts else None


def _extrair_id_hash_msg(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    messages = value.get("messages", [{}])
    return messages[0].get("id") if messages else None
