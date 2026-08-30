from contextlib import contextmanager
from contextvars import ContextVar

from pywa import WhatsApp

from core.integrations.whatsapp.tools.config import (
    TOKEN_USUARIO_META,
    get_meta_graph_api_version,
)


_PREFIXO_MENSAGEM_BOT = ContextVar(
    "prefixo_mensagem_bot",
    default=None,
)


def conta_wa(phone_id, token=TOKEN_USUARIO_META):
    phone_id = _normalizar_phone_id(phone_id)

    cliente = WhatsApp(
        token=token,
        phone_id=phone_id,
        api_version=get_meta_graph_api_version(),
    )

    if _PREFIXO_MENSAGEM_BOT.get():
        return _ClienteWhatsAppComPrefixo(cliente)

    return cliente


@contextmanager
def usar_prefixo_mensagem_bot(prefixo):
    """Limita o prefixo à resolução corrente, inclusive sob exceção."""
    prefixo_normalizado = prefixo if isinstance(prefixo, str) else None
    token = _PREFIXO_MENSAGEM_BOT.set(prefixo_normalizado or None)

    try:
        yield
    finally:
        _PREFIXO_MENSAGEM_BOT.reset(token)


def aplicar_prefixo_mensagem_bot(texto, prefixo=None):
    prefixo = prefixo if prefixo is not None else _PREFIXO_MENSAGEM_BOT.get()

    if not prefixo or not isinstance(texto, str):
        return texto

    if texto.startswith(prefixo):
        return texto

    return f"{prefixo}{texto}"


class _ClienteWhatsAppComPrefixo:
    """Decora textos enviados no escopo corrente do flow sender."""

    def __init__(self, cliente):
        self._cliente = cliente

    def send_message(self, *args, **kwargs):
        return self._enviar_com_prefixo(
            self._cliente.send_message,
            args,
            kwargs,
        )

    def request_contact_info(self, *args, **kwargs):
        return self._enviar_com_prefixo(
            self._cliente.request_contact_info,
            args,
            kwargs,
        )

    @staticmethod
    def _enviar_com_prefixo(metodo, args, kwargs):
        if "text" in kwargs:
            kwargs = dict(kwargs)
            kwargs["text"] = aplicar_prefixo_mensagem_bot(kwargs["text"])

        return metodo(*args, **kwargs)

    def __getattr__(self, nome):
        return getattr(self._cliente, nome)


def _normalizar_phone_id(phone_id):
    if phone_id is None:
        raise ValueError("phone_id da unidade nao informado")

    phone_id = str(phone_id).strip()

    if not phone_id:
        raise ValueError("phone_id da unidade vazio")

    return phone_id
