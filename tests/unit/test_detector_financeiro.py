import unittest

from workers.worker_flow.response_flow.etapas.detector_etapas.detector_financeiro import (
    detecta_pergunta_financeira,
)


class DetectorFinanceiroTests(unittest.TestCase):
    def test_detecta_perguntas_e_termos_de_valor(self):
        frases = [
            "qual o valor?",
            "qual o preço da aula?",
            "quanto custa?",
            "tem mensalidade?",
            "qual o investimento?",
            "aceita pix?",
            "posso pagar no cartão?",
            "tem desconto?",
            "é gratuito?",
            "fica por R$ 100?",
            "tem taxa de matrícula?",
            "qual o plano?",
            "tem boleto?",
            "é caro?",
        ]

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertTrue(detecta_pergunta_financeira(frase))

    def test_nao_detecta_texto_sem_relacao_com_valor(self):
        frases = [
            "meu nome é Maria",
            "quero conhecer o supera",
            "boa tarde",
            "posso fazer uma aula?",
        ]

        for frase in frases:
            with self.subTest(frase=frase):
                self.assertFalse(detecta_pergunta_financeira(frase))


if __name__ == "__main__":
    unittest.main()
