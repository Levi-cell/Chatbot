import logging

import requests

from core.integrations.whatsapp.tools.config import (
    construir_url_graph_api,
    get_meta_http_timeout,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.waba")


def validar_phone_number_id_da_waba(waba_id, phone_number_id):
    """Confirma na Graph API que o phone ID pertence à WABA informada."""
    waba_id = str(waba_id or "").strip()
    phone_number_id = str(phone_number_id or "").strip()

    if not waba_id:
        raise ValueError("waba_id nao informado para validacao")

    if not phone_number_id:
        raise ValueError("phone_number_id nao informado para validacao")

    url = construir_url_graph_api(f"{waba_id}/phone_numbers")
    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
    }
    params = {
        "fields": "id",
        "limit": 100,
    }
    paginas_consultadas = 0

    while url:
        response = requests.get(
            url,
            headers=headers,
            params=params,
            timeout=get_meta_http_timeout(),
        )
        paginas_consultadas += 1
        resposta = _normalizar_resposta(response)

        if not 200 <= response.status_code < 300:
            logger.error(
                "whatsapp_phone_waba_validacao_falhou | "
                "motivo=erro_http acao=bloquear_cadastro "
                "waba_id=%s phone_number_id=%s status=%s",
                short_value(waba_id),
                short_value(phone_number_id),
                response.status_code,
            )
            return response.status_code, {
                "success": False,
                "belongs": False,
                "reason": "meta_http_error",
                "meta": resposta,
            }

        numeros = resposta.get("data")

        if not isinstance(numeros, list):
            logger.error(
                "whatsapp_phone_waba_validacao_falhou | "
                "motivo=resposta_invalida acao=bloquear_cadastro "
                "waba_id=%s phone_number_id=%s status=%s",
                short_value(waba_id),
                short_value(phone_number_id),
                response.status_code,
            )
            return response.status_code, {
                "success": False,
                "belongs": False,
                "reason": "invalid_meta_response",
            }

        if any(
            str(numero.get("id") or "").strip() == phone_number_id
            for numero in numeros
            if isinstance(numero, dict)
        ):
            logger.info(
                "whatsapp_phone_waba_validacao_ok | "
                "acao=permitir_cadastro waba_id=%s "
                "phone_number_id=%s paginas=%s",
                short_value(waba_id),
                short_value(phone_number_id),
                paginas_consultadas,
            )
            return response.status_code, {
                "success": True,
                "belongs": True,
                "waba_id": waba_id,
                "phone_number_id": phone_number_id,
            }

        url = (
            resposta.get("paging", {}).get("next")
            if isinstance(resposta.get("paging"), dict)
            else None
        )
        params = None

    logger.warning(
        "whatsapp_phone_waba_validacao_negada | "
        "motivo=phone_id_nao_pertence_waba acao=bloquear_cadastro "
        "waba_id=%s phone_number_id=%s paginas=%s",
        short_value(waba_id),
        short_value(phone_number_id),
        paginas_consultadas,
    )
    return 200, {
        "success": False,
        "belongs": False,
        "reason": "phone_number_not_in_waba",
        "waba_id": waba_id,
        "phone_number_id": phone_number_id,
    }


def _normalizar_resposta(response):
    try:
        dados = response.json()

        if isinstance(dados, dict):
            return dados

        if isinstance(dados, list):
            return {"data": dados}

        return {
            "success": response.ok,
            "data": dados,
        }

    except ValueError:
        return {
            "success": response.ok,
            "text": response.text,
        }
