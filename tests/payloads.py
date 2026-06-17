def payload_texto_meta(
    wa_id="5571999999999",
    phone_number_id="123456",
    display_phone_number="5571000000000",
    message_id="wamid.test.1",
    texto="ola",
    timestamp="1760000000",
):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba_id",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {
                                "display_phone_number": display_phone_number,
                                "phone_number_id": phone_number_id,
                            },
                            "contacts": [
                                {
                                    "profile": {"name": "Cliente Teste"},
                                    "wa_id": wa_id,
                                }
                            ],
                            "messages": [
                                {
                                    "from": wa_id,
                                    "id": message_id,
                                    "timestamp": timestamp,
                                    "text": {"body": texto},
                                    "type": "text",
                                }
                            ],
                        },
                        "field": "messages",
                    }
                ],
            }
        ],
    }


def payload_sem_mensagem():
    payload = payload_texto_meta()
    del payload["entry"][0]["changes"][0]["value"]["messages"]
    return payload


def payload_interactive_button_meta(
    wa_id="5571999999999",
    phone_number_id="123456",
    display_phone_number="5571000000000",
    message_id="wamid.test.button.1",
    titulo_botao="Aperte em mim",
    button_id="botao_etapa_1",
    timestamp="1760000000",
):
    payload = payload_texto_meta(
        wa_id=wa_id,
        phone_number_id=phone_number_id,
        display_phone_number=display_phone_number,
        message_id=message_id,
        timestamp=timestamp,
    )

    payload["entry"][0]["changes"][0]["value"]["messages"] = [
        {
            "from": wa_id,
            "id": message_id,
            "timestamp": timestamp,
            "interactive": {
                "type": "button_reply",
                "button_reply": {
                    "id": button_id,
                    "title": titulo_botao,
                },
            },
            "type": "interactive",
        }
    ]
    return payload


def payload_interactive_list_meta(
    wa_id="5571999999999",
    phone_number_id="123456",
    display_phone_number="5571000000000",
    message_id="wamid.test.list.1",
    titulo_opcao="Opcao A",
    list_id="opcao_a",
    timestamp="1760000000",
):
    payload = payload_texto_meta(
        wa_id=wa_id,
        phone_number_id=phone_number_id,
        display_phone_number=display_phone_number,
        message_id=message_id,
        timestamp=timestamp,
    )

    payload["entry"][0]["changes"][0]["value"]["messages"] = [
        {
            "from": wa_id,
            "id": message_id,
            "timestamp": timestamp,
            "interactive": {
                "type": "list_reply",
                "list_reply": {
                    "id": list_id,
                    "title": titulo_opcao,
                    "description": "Descricao opcional",
                },
            },
            "type": "interactive",
        }
    ]
    return payload


def payload_imagem_meta(
    wa_id="5571999999999",
    phone_number_id="123456",
    display_phone_number="5571000000000",
    message_id="wamid.test.image.1",
    media_id="media_id_123",
    timestamp="1760000000",
):
    payload = payload_texto_meta(
        wa_id=wa_id,
        phone_number_id=phone_number_id,
        display_phone_number=display_phone_number,
        message_id=message_id,
        timestamp=timestamp,
    )

    payload["entry"][0]["changes"][0]["value"]["messages"] = [
        {
            "from": wa_id,
            "id": message_id,
            "timestamp": timestamp,
            "image": {
                "id": media_id,
                "mime_type": "image/jpeg",
                "sha256": "fake-sha256",
            },
            "type": "image",
        }
    ]
    return payload
