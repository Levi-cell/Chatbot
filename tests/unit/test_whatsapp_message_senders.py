import unittest
from types import SimpleNamespace

from core.integrations.whatsapp.messages.senders import (
    enviar_mensagem_texto_com_botao,
)


class FakeClienteWa:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(id="wamid.bot.fake")


class WhatsappMessageSendersTests(unittest.TestCase):
    def test_enviar_mensagem_texto_com_botao_monta_button_pywa(self):
        cliente_wa = FakeClienteWa()

        id_hash = enviar_mensagem_texto_com_botao(
            to="5571999999999",
            text="Ola!",
            titulo_botao="Aperte em mim",
            phone_id_unidade="123456",
            cliente_wa_mock=cliente_wa,
        )

        self.assertEqual(id_hash, "wamid.bot.fake")
        self.assertEqual(len(cliente_wa.calls), 1)

        chamada = cliente_wa.calls[0]
        self.assertEqual(chamada["to"], "5571999999999")
        self.assertEqual(chamada["text"], "Ola!")
        self.assertEqual(len(chamada["buttons"]), 1)

        botao = chamada["buttons"][0]
        self.assertEqual(botao.title, "Aperte em mim")
        self.assertEqual(botao.callback_data, "Aperte em mim")


if __name__ == "__main__":
    unittest.main()
