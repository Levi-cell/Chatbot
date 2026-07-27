import logging

from django.http import JsonResponse

from core.cache.runtime.cache_flood_redis import avaliar_flood_redis
from core.cache.cache_flood_memoria import avaliar_flood_memoria
from core.database.connection_aws import get_conn
from core.integrations.whatsapp.tools.usuarios import (
    bloquear_usuario_meta,
)
from core.logging_config import short_value
from core.repositories.seguranca.bloqueio_meta import (
    buscar_cliente_por_wa_id,
    buscar_unidade_bloqueio_por_phone_id,
    contar_eventos_flood_banco,
    limpar_eventos_flood_antigos,
    registrar_cliente_bloqueado_meta_banco,
    registrar_evento_flood_banco,
)
from .alerta_flood_memoria import registrar_alerta_flood_memoria


logger = logging.getLogger("webhook.flood_guard")

REGRAS_FLOOD = (
    {
        "nome": "rajada_curta",
        "limite": 15,
        "janela_segundos": 5,
    },
)


def responder_se_flood(data):
    phone_id_unidade = _extrair_phone_number_id(data)
    wa_id_cliente = _extrair_cliente_telefone(data)
    id_hash_msg = _extrair_id_hash_msg(data)
    nome_cliente = _extrair_nome_cliente(data)

    flood = bloquear_cliente_se_flood(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
        nome_cliente=nome_cliente,
    )

    if not flood["bloqueado"]:
        return None

    logger.warning(
        "mensagem_ignorada | motivo=%s regra=%s "
        "acao=bloqueio_local_nao_enfileirar cliente=%s phone_number_id=%s "
        "total=%s persistencia_ok=%s meta_ok=%s",
        flood["motivo"],
        flood.get("regra"),
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        flood["total"],
        flood.get("persistencia_ok"),
        flood.get("meta_ok"),
    )

    if flood.get("reentregar"):
        return JsonResponse(
            {
                "status": "unavailable",
                "reason": flood["motivo"],
            },
            status=503,
        )

    return JsonResponse({
        "status": "ignored",
        "reason": flood["motivo"],
    })


def bloquear_cliente_se_flood(
    wa_id_cliente,
    phone_id_unidade,
    id_hash_msg,
    nome_cliente=None,
):
    if not wa_id_cliente or not phone_id_unidade or not id_hash_msg:
        return {
            "bloqueado": False,
            "motivo": "dados_invalidos",
            "total": 0,
            "regra": None,
            "meta_ok": None,
        }

    rate_redis = avaliar_flood_redis(
        wa_id_cliente,
        phone_id_unidade,
        regras=REGRAS_FLOOD,
    )

    if rate_redis["redis_ok"]:
        if rate_redis["flood"]:
            return _bloquear_e_registrar(
                wa_id_cliente,
                phone_id_unidade,
                origem="redis",
                total=rate_redis["total"],
                regra=rate_redis["regra"],
                nome_cliente=nome_cliente,
            )

        return {
            "bloqueado": False,
            "motivo": "abaixo_limite_redis",
            "total": rate_redis["total"],
            "regra": None,
            "meta_ok": None,
        }

    rate_banco = _avaliar_flood_banco(
        wa_id_cliente,
        phone_id_unidade,
        id_hash_msg,
    )

    if rate_banco["flood"]:
        return _bloquear_e_registrar(
            wa_id_cliente,
            phone_id_unidade,
            origem="banco",
            total=rate_banco["total"],
            regra=rate_banco["regra"],
            nome_cliente=nome_cliente,
        )

    if not rate_banco["banco_ok"]:
        rate_memoria = avaliar_flood_memoria(
            wa_id_cliente,
            phone_id_unidade,
            regras=REGRAS_FLOOD,
        )

        if rate_memoria["flood"]:
            return _bloquear_via_memoria_e_alertar(
                wa_id_cliente,
                phone_id_unidade,
                total=rate_memoria["total"],
                regra=rate_memoria["regra"],
                id_hash_msg=id_hash_msg,
                nome_cliente=nome_cliente,
            )

        return {
            "bloqueado": False,
            "motivo": rate_memoria["motivo"],
            "total": rate_memoria["total"],
            "regra": None,
            "meta_ok": None,
        }

    return {
        "bloqueado": False,
        "motivo": rate_banco["motivo"],
        "total": rate_banco["total"],
        "regra": None,
        "meta_ok": None,
    }


def _avaliar_flood_banco(wa_id_cliente, phone_id_unidade, id_hash_msg):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

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
            "flood": False,
            "total": 0,
            "motivo": "banco_indisponivel",
            "regra": None,
        }

    finally:
        if conn:
            conn.close()


def _bloquear_via_memoria_e_alertar(
    wa_id_cliente,
    phone_id_unidade,
    total,
    regra,
    id_hash_msg,
    nome_cliente=None,
):
    resultado = _bloquear_e_registrar(
        wa_id_cliente,
        phone_id_unidade,
        origem="memoria",
        total=total,
        regra=regra,
        nome_cliente=nome_cliente,
    )

    registrar_alerta_flood_memoria(
        wa_id_cliente=wa_id_cliente,
        phone_id_unidade=phone_id_unidade,
        origem="memoria",
        regra=regra,
        total=total,
        meta_ok=resultado.get("meta_ok"),
        motivo=resultado["motivo"],
        id_hash_msg=id_hash_msg,
        erro_meta=resultado.get("erro_meta"),
    )

    logger.warning(
        "flood_bloqueado_memoria | acao=alertar regra=%s "
        "wa_id_cliente=%s phone_id_unidade=%s total=%s "
        "persistencia_ok=%s meta_ok=%s reentregar=%s",
        regra,
        short_value(wa_id_cliente),
        short_value(phone_id_unidade),
        total,
        resultado.get("persistencia_ok"),
        resultado.get("meta_ok"),
        resultado.get("reentregar"),
    )
    return resultado


def _bloquear_e_registrar(
    wa_id_cliente,
    phone_id_unidade,
    origem,
    total,
    regra,
    nome_cliente=None,
):
    dados_bloqueio = _buscar_dados_bloqueio(
        wa_id_cliente,
        phone_id_unidade,
        nome_cliente=nome_cliente,
    )

    if not dados_bloqueio["id_unidade"]:
        banco_indisponivel = (
            dados_bloqueio["motivo"] == "flood_banco_indisponivel"
        )
        motivo = (
            f"flood_{origem}_banco_indisponivel"
            if banco_indisponivel
            else f"flood_{origem}_unidade_nao_cadastrada"
        )
        logger.warning(
            "flood_detectado_sem_bloqueio_local | motivo=%s acao=%s "
            "origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s total=%s",
            motivo,
            "retornar_503" if banco_indisponivel else "ignorar_phone_desconhecido",
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
        )
        return {
            "bloqueado": True,
            "motivo": motivo,
            "total": total,
            "regra": regra,
            "id_bloqueio": None,
            "id_cliente": dados_bloqueio["id_cliente"],
            "id_unidade": None,
            "persistencia_ok": False,
            "meta_ok": None,
            "erro_meta": None,
            "reentregar": banco_indisponivel,
        }

    id_bloqueio = _registrar_intencao_bloqueio_banco(
        dados_bloqueio["id_cliente"],
        dados_bloqueio["nome_cliente"],
        wa_id_cliente,
        dados_bloqueio["id_unidade"],
        dados_bloqueio["phone_id_unidade"],
    )

    if not id_bloqueio:
        logger.critical(
            "bloqueio_local_registro_falhou | "
            "motivo=banco_falhou acao=retornar_503_sem_chamar_meta "
            "wa_id_cliente=%s id_cliente=%s id_unidade=%s "
            "phone_id_unidade=%s",
            short_value(wa_id_cliente),
            dados_bloqueio["id_cliente"],
            dados_bloqueio["id_unidade"],
            short_value(dados_bloqueio["phone_id_unidade"]),
        )
        return {
            "bloqueado": True,
            "motivo": f"flood_{origem}_persistencia_local_falhou",
            "total": total,
            "regra": regra,
            "id_bloqueio": None,
            "id_cliente": dados_bloqueio["id_cliente"],
            "id_unidade": dados_bloqueio["id_unidade"],
            "persistencia_ok": False,
            "meta_ok": None,
            "erro_meta": None,
            "reentregar": True,
        }

    meta_ok = False
    erro_meta = None

    try:
        bloquear_usuario_meta(wa_id_cliente, phone_id_unidade)
        meta_ok = True

    except Exception as exc:
        erro_meta = str(exc)
        logger.exception(
            "bloqueio_meta_falhou | motivo=meta_indisponivel "
            "acao=manter_bloqueio_local_e_repetir_em_nova_mensagem "
            "origem=%s regra=%s wa_id_cliente=%s phone_id_unidade=%s "
            "total=%s id_bloqueio=%s erro=%s",
            origem,
            regra,
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            total,
            id_bloqueio,
            exc,
        )

    motivo = (
        f"flood_{origem}"
        if meta_ok
        else f"flood_{origem}_meta_falhou"
    )

    logger.warning(
        "flood_bloqueado | acao=registrar_resultado origem=%s regra=%s "
        "wa_id_cliente=%s id_cliente=%s id_unidade=%s phone_id_unidade=%s "
        "total=%s id_bloqueio=%s meta_ok=%s erro_meta=%s",
        origem,
        regra,
        short_value(wa_id_cliente),
        dados_bloqueio["id_cliente"],
        dados_bloqueio["id_unidade"],
        short_value(dados_bloqueio["phone_id_unidade"]),
        total,
        id_bloqueio,
        meta_ok,
        erro_meta,
    )

    return {
        "bloqueado": True,
        "motivo": motivo,
        "total": total,
        "regra": regra,
        "id_bloqueio": id_bloqueio,
        "id_cliente": dados_bloqueio["id_cliente"],
        "id_unidade": dados_bloqueio["id_unidade"],
        "persistencia_ok": True,
        "meta_ok": meta_ok,
        "erro_meta": erro_meta,
        "reentregar": False,
    }


def _buscar_dados_bloqueio(
    wa_id_cliente,
    phone_id_unidade,
    nome_cliente=None,
):
    conn = None
    dados_vazios = {
        "id_cliente": None,
        "nome_cliente": _normalizar_nome_cliente(nome_cliente),
        "id_unidade": None,
        "phone_id_unidade": phone_id_unidade,
        "motivo": "dados_bloqueio_indisponiveis",
    }

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        cliente = buscar_cliente_por_wa_id(wa_id_cliente, cursor)
        id_cliente = cliente[0] if cliente else None
        nome_cliente_banco = cliente[1] if cliente else None
        nome_bloqueio = (
            _normalizar_nome_cliente(nome_cliente_banco)
            or dados_vazios["nome_cliente"]
        )
        unidade = buscar_unidade_bloqueio_por_phone_id(
            phone_id_unidade,
            cursor,
        )

        if not unidade:
            logger.warning(
                "bloqueio_meta_dados_ignorados | motivo=unidade_nao_cadastrada acao=nao_bloquear_meta wa_id_cliente=%s phone_id_unidade=%s",
                short_value(wa_id_cliente),
                short_value(phone_id_unidade),
            )
            return {
                **dados_vazios,
                "id_cliente": id_cliente,
                "nome_cliente": nome_bloqueio,
                "motivo": "flood_sem_unidade_cadastrada",
            }

        id_unidade, phone_id_cadastrado = unidade

        return {
            "id_cliente": id_cliente,
            "nome_cliente": nome_bloqueio,
            "id_unidade": id_unidade,
            "phone_id_unidade": phone_id_cadastrado,
            "motivo": "ok",
        }

    except Exception as exc:
        logger.exception(
            "bloqueio_meta_dados_falharam | motivo=banco_indisponivel acao=nao_bloquear_meta wa_id_cliente=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            short_value(phone_id_unidade),
            exc,
        )
        return {
            **dados_vazios,
            "motivo": "flood_banco_indisponivel",
        }

    finally:
        if conn:
            conn.close()


def _registrar_intencao_bloqueio_banco(
    id_cliente,
    nome_cliente,
    wa_id_cliente,
    id_unidade,
    phone_id_unidade,
):
    conn = None

    try:
        conn = get_conn(application_name="webhook_chatbot")
        cursor = conn.cursor()

        id_bloqueio = registrar_cliente_bloqueado_meta_banco(
            id_cliente,
            wa_id_cliente,
            id_unidade,
            phone_id_unidade,
            cursor,
            nome_cliente=nome_cliente,
        )

        conn.commit()
        return id_bloqueio

    except Exception as exc:
        if conn:
            conn.rollback()

        logger.exception(
            "bloqueio_local_registro_banco_falhou | motivo=banco_indisponivel "
            "acao=nao_registrado wa_id_cliente=%s id_cliente=%s "
            "id_unidade=%s phone_id_unidade=%s erro=%s",
            short_value(wa_id_cliente),
            id_cliente,
            id_unidade,
            short_value(phone_id_unidade),
            exc,
        )
        return None

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


def _extrair_nome_cliente(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    contacts = value.get("contacts")

    if (
        not isinstance(contacts, list)
        or not contacts
        or not isinstance(contacts[0], dict)
    ):
        return None

    profile = contacts[0].get("profile")
    if not isinstance(profile, dict):
        return None

    return _normalizar_nome_cliente(profile.get("name"))


def _normalizar_nome_cliente(nome_cliente):
    if nome_cliente is None:
        return None

    nome_normalizado = str(nome_cliente).strip()
    return nome_normalizado[:200] or None


def _extrair_id_hash_msg(data):
    value = data.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {})
    messages = value.get("messages", [{}])
    return messages[0].get("id") if messages else None
