"""Indicador opcional da Meta: uma chamada curta, sem efeitos na fila."""

import logging
from time import monotonic

import httpx

from core.integrations.whatsapp.pywa_functions.cliente import conta_wa

logger = logging.getLogger("whatsapp.digitacao")


def indicar_digitacao(phone_id, id_hash_msg, *, id_mensagem=None, id_conversa=None):
    """Marca a entrada como lida e solicita os pontinhos; falhas não barram resposta."""
    phone_id = str(phone_id).strip() if phone_id is not None else ""
    id_hash_msg = id_hash_msg.strip() if isinstance(id_hash_msg, str) else ""
    if not phone_id or not id_hash_msg.startswith("wamid.") or id_hash_msg == "wamid.":
        logger.warning(
            "digitacao_omitida | motivo=identificador_ausente_ou_invalido "
            "id_mensagem=%s id_conversa=%s",
            id_mensagem, id_conversa,
        )
        return False

    inicio = monotonic()
    try:
        # Sessão exclusiva: não altera o timeout dos envios de atendimento.
        # Limites por fase, não um prazo total de dois segundos.
        with httpx.Client(
            timeout=httpx.Timeout(2.0, connect=1.0, pool=1.0),
            transport=httpx.HTTPTransport(retries=0),
        ) as session:
            cliente = conta_wa(phone_id, session=session)
            resultado = cliente.indicate_typing(message_id=id_hash_msg)
            confirmado = resultado.success is True
    except Exception as erro:
        # Não incluir mensagem da exceção: SDK/HTTP podem expor dados externos.
        logger.warning(
            "digitacao_falhou | acao=continuar_resposta tipo=%s "
            "id_mensagem=%s id_conversa=%s duracao_ms=%d",
            type(erro).__name__, id_mensagem, id_conversa,
            int((monotonic() - inicio) * 1000),
        )
        return False

    if not confirmado:
        logger.warning(
            "digitacao_nao_confirmada | acao=continuar_resposta "
            "id_mensagem=%s id_conversa=%s",
            id_mensagem, id_conversa,
        )
        return False

    logger.debug(
        "digitacao_solicitada | id_mensagem=%s id_conversa=%s duracao_ms=%d",
        id_mensagem, id_conversa, int((monotonic() - inicio) * 1000),
    )
    return True
