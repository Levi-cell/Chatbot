import logging

import requests

from core.integrations.whatsapp.tools.config import (
    construir_url_graph_api,
    get_meta_http_timeout,
    get_token_usuario_meta,
)
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.waba")


def ativar_waba_id(waba_id):
    """Assina o App atual aos webhooks da WABA recebida como argumento.

    A URL pública e o verify token do webhook continuam configurados uma única
    vez no App Meta. Na arquitetura atual, o mesmo token de usuário do sistema
    administra todas as WABAs previamente autorizadas para esse App. A WABA
    nunca é obtida do ambiente global: o identificador vem da unidade criada
    no Django Admin.
    """
    waba_id = str(waba_id or "").strip()

    if not waba_id:
        raise ValueError("waba_id nao informado para ativacao")

    url = construir_url_graph_api(f"{waba_id}/subscribed_apps")

    headers = {
        "Authorization": f"Bearer {get_token_usuario_meta()}",
        "Content-Type": "application/json",
    }

    response = requests.post(
        url,
        headers=headers,
        timeout=get_meta_http_timeout(),
    )
    resposta = _normalizar_resposta(response)
    print(response)
    print(resposta)

    logger.info(
        "whatsapp_waba_subscribe_resposta | acao=subscribe_apps "
        "waba_id=%s status=%s sucesso=%s",
        short_value(waba_id),
        response.status_code,
        resposta.get("success"),
    )

    return response.status_code, resposta


def _normalizar_resposta(response):
    try:
        dados = response.json()

        if isinstance(dados, dict):
            return dados

        return {
            "success": response.ok,
            "data": dados,
        }

    except ValueError:
        return {
            "success": response.ok,
            "text": response.text,
        }


ativar_waba_id(1334896588725096)