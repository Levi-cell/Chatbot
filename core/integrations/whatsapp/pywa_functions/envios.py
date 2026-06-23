import logging

from pywa.types import Button

from core.integrations.whatsapp.pywa_functions.cliente import conta_wa
from core.logging_config import short_value


logger = logging.getLogger("whatsapp.pywa")


def enviar_mensagem_texto(
    *,
    to,
    text,
    phone_id_unidade,
    botoes=None,
):
    botoes_pywa = _montar_botoes(botoes)
    cliente_wa = conta_wa(phone_id_unidade)

    sent_message = cliente_wa.send_message(
        to=to,
        text=text,
        buttons=botoes_pywa,
    )

    return _finalizar_envio(
        sent_message=sent_message,
        to=to,
        tipo_mensagem="text",
        botoes_pywa=botoes_pywa,
    )


def enviar_mensagem_imagem(
    *,
    to,
    image,
    phone_id_unidade,
    legenda=None,
    botoes=None,
    mime_type=None,
):
    botoes_pywa = _montar_botoes(botoes)
    _validar_legenda_de_midia(legenda, botoes_pywa)
    cliente_wa = conta_wa(phone_id_unidade)

    sent_message = cliente_wa.send_image(
        to=to,
        image=image,
        caption=legenda,
        buttons=botoes_pywa,
        mime_type=mime_type,
    )

    return _finalizar_envio(
        sent_message=sent_message,
        to=to,
        tipo_mensagem="image",
        botoes_pywa=botoes_pywa,
    )


def enviar_mensagem_video(
    *,
    to,
    video,
    phone_id_unidade,
    legenda=None,
    botoes=None,
    mime_type=None,
):
    botoes_pywa = _montar_botoes(botoes)
    _validar_legenda_de_midia(legenda, botoes_pywa)
    cliente_wa = conta_wa(phone_id_unidade)

    sent_message = cliente_wa.send_video(
        to=to,
        video=video,
        caption=legenda,
        buttons=botoes_pywa,
        mime_type=mime_type,
    )

    return _finalizar_envio(
        sent_message=sent_message,
        to=to,
        tipo_mensagem="video",
        botoes_pywa=botoes_pywa,
    )


def enviar_mensagem_documento(
    *,
    to,
    document,
    phone_id_unidade,
    nome_arquivo=None,
    legenda=None,
    botoes=None,
    mime_type=None,
):
    botoes_pywa = _montar_botoes(botoes)
    _validar_legenda_de_midia(legenda, botoes_pywa)
    cliente_wa = conta_wa(phone_id_unidade)

    parametros = {
        "to": to,
        "document": document,
        "caption": legenda,
        "buttons": botoes_pywa,
        "mime_type": mime_type,
    }

    if nome_arquivo is not None:
        parametros["filename"] = nome_arquivo

    sent_message = cliente_wa.send_document(**parametros)

    return _finalizar_envio(
        sent_message=sent_message,
        to=to,
        tipo_mensagem="document",
        botoes_pywa=botoes_pywa,
    )


def _montar_botoes(botoes):
    if not botoes:
        return None

    return [
        Button(
            title=botao["titulo"],
            callback_data=botao["callback_data"],
        )
        for botao in botoes
    ]


def _validar_legenda_de_midia(legenda, botoes_pywa):
    if botoes_pywa and not legenda:
        raise ValueError("Midia com botoes exige legenda")


def _finalizar_envio(sent_message, to, tipo_mensagem, botoes_pywa):
    id_hash_msg = _extrair_id_mensagem_enviada(sent_message)

    logger.info(
        "whatsapp_mensagem_enviada | acao=enviar tipo=%s to=%s "
        "id_hash_msg=%s quantidade_botoes=%s",
        tipo_mensagem,
        short_value(to),
        id_hash_msg,
        len(botoes_pywa or []),
    )

    return id_hash_msg


def _extrair_id_mensagem_enviada(sent_message):
    id_hash_msg = getattr(sent_message, "id", None)

    if not id_hash_msg:
        raise ValueError("PyWa nao retornou id da mensagem enviada")

    return id_hash_msg
