import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.pywa_functions import envios as senders_module


class FakeClienteWa:
    def __init__(self):
        self.calls = []

    def send_message(self, **kwargs):
        self.calls.append(("send_message", kwargs))
        return SimpleNamespace(id="wamid.bot.texto")

    def send_image(self, **kwargs):
        self.calls.append(("send_image", kwargs))
        return SimpleNamespace(id="wamid.bot.imagem")

    def send_video(self, **kwargs):
        self.calls.append(("send_video", kwargs))
        return SimpleNamespace(id="wamid.bot.video")

    def send_document(self, **kwargs):
        self.calls.append(("send_document", kwargs))
        return SimpleNamespace(id="wamid.bot.documento")


class WhatsappMessageSendersTests(unittest.TestCase):
    def test_enviar_texto_sem_botao(self):
        cliente_wa = FakeClienteWa()

        with patch.object(senders_module, "conta_wa", return_value=cliente_wa):
            id_hash = senders_module.enviar_mensagem_texto(
                to="5571999999999",
                text="Ola!",
                phone_id_unidade="123456",
            )

        self.assertEqual(id_hash, "wamid.bot.texto")
        metodo, chamada = cliente_wa.calls[0]
        self.assertEqual(metodo, "send_message")
        self.assertEqual(chamada["text"], "Ola!")
        self.assertIsNone(chamada["buttons"])

    def test_enviar_texto_com_varios_botoes(self):
        cliente_wa = FakeClienteWa()

        with patch.object(senders_module, "conta_wa", return_value=cliente_wa):
            senders_module.enviar_mensagem_texto(
                to="5571999999999",
                text="Escolha",
                phone_id_unidade="123456",
                botoes=[
                    {"titulo": "Confirmar", "callback_data": "confirmar"},
                    {"titulo": "Voltar", "callback_data": "voltar"},
                ],
            )

        _, chamada = cliente_wa.calls[0]
        self.assertEqual(len(chamada["buttons"]), 2)
        self.assertEqual(chamada["buttons"][0].title, "Confirmar")
        self.assertEqual(chamada["buttons"][0].callback_data, "confirmar")
        self.assertEqual(chamada["buttons"][1].title, "Voltar")
        self.assertEqual(chamada["buttons"][1].callback_data, "voltar")

    def test_enviar_imagem_com_botao(self):
        cliente_wa = FakeClienteWa()

        with patch.object(senders_module, "conta_wa", return_value=cliente_wa):
            id_hash = senders_module.enviar_mensagem_imagem(
                to="5571999999999",
                image="https://exemplo.com/imagem.jpg",
                phone_id_unidade="123456",
                legenda="Imagem da unidade",
                botoes=[
                    {"titulo": "Continuar", "callback_data": "continuar"}
                ],
            )

        self.assertEqual(id_hash, "wamid.bot.imagem")
        metodo, chamada = cliente_wa.calls[0]
        self.assertEqual(metodo, "send_image")
        self.assertEqual(chamada["image"], "https://exemplo.com/imagem.jpg")
        self.assertEqual(chamada["caption"], "Imagem da unidade")
        self.assertEqual(len(chamada["buttons"]), 1)

    def test_enviar_video_sem_botao(self):
        cliente_wa = FakeClienteWa()

        with patch.object(senders_module, "conta_wa", return_value=cliente_wa):
            id_hash = senders_module.enviar_mensagem_video(
                to="5571999999999",
                video="https://exemplo.com/video.mp4",
                phone_id_unidade="123456",
                legenda="Conheca o Supera",
            )

        self.assertEqual(id_hash, "wamid.bot.video")
        metodo, chamada = cliente_wa.calls[0]
        self.assertEqual(metodo, "send_video")
        self.assertEqual(chamada["video"], "https://exemplo.com/video.mp4")
        self.assertIsNone(chamada["buttons"])

    def test_enviar_documento_com_nome_e_botao(self):
        cliente_wa = FakeClienteWa()

        with patch.object(senders_module, "conta_wa", return_value=cliente_wa):
            id_hash = senders_module.enviar_mensagem_documento(
                to="5571999999999",
                document="https://exemplo.com/guia.pdf",
                phone_id_unidade="123456",
                nome_arquivo="guia-supera.pdf",
                legenda="Guia da unidade",
                botoes=[
                    {"titulo": "Continuar", "callback_data": "continuar"}
                ],
            )

        self.assertEqual(id_hash, "wamid.bot.documento")
        metodo, chamada = cliente_wa.calls[0]
        self.assertEqual(metodo, "send_document")
        self.assertEqual(chamada["document"], "https://exemplo.com/guia.pdf")
        self.assertEqual(chamada["filename"], "guia-supera.pdf")
        self.assertEqual(chamada["caption"], "Guia da unidade")
        self.assertEqual(len(chamada["buttons"]), 1)

    def test_midia_com_botao_sem_legenda_falha_antes_da_pywa(self):
        cliente_wa = FakeClienteWa()

        with patch.object(senders_module, "conta_wa", return_value=cliente_wa):
            with self.assertRaisesRegex(ValueError, "exige legenda"):
                senders_module.enviar_mensagem_imagem(
                    to="5571999999999",
                    image="imagem.jpg",
                    phone_id_unidade="123456",
                    botoes=[
                        {"titulo": "Continuar", "callback_data": "continuar"}
                    ],
                )

        self.assertEqual(cliente_wa.calls, [])

    def test_resposta_sem_id_falha_explicitamente(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            cliente_wa,
            "send_message",
            return_value=SimpleNamespace(id=None),
        ), patch.object(
            senders_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaisesRegex(ValueError, "nao retornou id"):
                senders_module.enviar_mensagem_texto(
                    to="5571999999999",
                    text="Ola!",
                    phone_id_unidade="123456",
                )


if __name__ == "__main__":
    unittest.main()
