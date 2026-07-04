import unittest

from core.integrations.whatsapp.messages.etapa8_messages import (
    montar_mensagem_contexto_email_invalido_etapa8,
    montar_mensagem_email_etapa8,
    montar_mensagem_email_etapa8_financeiro,
    montar_mensagem_email_etapa8_midia,
)


class MessagesEtapa8Tests(unittest.TestCase):
    def test_mensagem_normal_pergunta_email(self):
        self.assertEqual(
            montar_mensagem_email_etapa8(),
            "Qual o seu melhor email?",
        )

    def test_tratamentos_repetem_pergunta_da_etapa(self):
        mensagens = (
            montar_mensagem_email_etapa8_midia(),
            montar_mensagem_email_etapa8_financeiro(),
            montar_mensagem_contexto_email_invalido_etapa8(),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertIn("qual o seu melhor email?", mensagem.lower())

    def test_contexto_invalido_orienta_formato_completo(self):
        mensagem = montar_mensagem_contexto_email_invalido_etapa8()

        self.assertIn("email válido", mensagem)
        self.assertIn("nome@gmail.com", mensagem)

    def test_financeiro_mantem_gratuidade_em_negrito(self):
        self.assertIn(
            "*gratuita*",
            montar_mensagem_email_etapa8_financeiro(),
        )


if __name__ == "__main__":
    unittest.main()
