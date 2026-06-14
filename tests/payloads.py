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
