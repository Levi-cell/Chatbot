import unittest

from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_oferta_adiada_etapa6,
)


class MessagesEtapa6Tests(unittest.TestCase):
    def test_mensagem_inclui_instagram_da_unidade(self):
        mensagem = montar_mensagem_oferta_adiada_etapa6(
            "https://instagram.com/supera.saj/"
        )

        self.assertTrue(mensagem.startswith("Tudo bem! ☺️"))
        self.assertIn(
            "https://instagram.com/supera.saj/",
            mensagem,
        )
        self.assertEqual(mensagem, mensagem.strip())

    def test_link_ausente_falha_cedo(self):
        with self.assertRaises(ValueError):
            montar_mensagem_oferta_adiada_etapa6("  ")


if __name__ == "__main__":
    unittest.main()
