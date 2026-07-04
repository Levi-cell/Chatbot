import unittest

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_triagem import (
    RESPOSTA_TRIAGEM_AS_VEZES,
    RESPOSTA_TRIAGEM_FREQUENTEMENTE,
    RESPOSTA_TRIAGEM_NUNCA,
    validar_resposta_triagem,
)


class ValidadorTriagemTests(unittest.TestCase):
    def test_aceita_as_tres_opcoes_em_texto_ou_botao(self):
        casos = (
            ("Nunca", "interactive", RESPOSTA_TRIAGEM_NUNCA),
            (" nunca ", "text", RESPOSTA_TRIAGEM_NUNCA),
            ("Às vezes", "interactive", RESPOSTA_TRIAGEM_AS_VEZES),
            ("AS VEZES", "text", RESPOSTA_TRIAGEM_AS_VEZES),
            (
                "Frequentemente",
                "button",
                RESPOSTA_TRIAGEM_FREQUENTEMENTE,
            ),
        )

        for texto, tipo, esperado in casos:
            with self.subTest(texto=texto, tipo=tipo):
                self.assertEqual(
                    validar_resposta_triagem(texto, tipo),
                    esperado,
                )

    def test_rejeita_conteudo_que_nao_seja_exatamente_uma_opcao(self):
        casos = (
            "",
            "1",
            "Nunca esqueço",
            "Às vezes eu esqueço",
            "Frequentemente!",
            "Sempre",
            "quanto custa?",
        )

        for texto in casos:
            with self.subTest(texto=texto):
                self.assertIsNone(
                    validar_resposta_triagem(texto, "text")
                )

    def test_rejeita_midia_mesmo_que_haja_texto_equivalente(self):
        for tipo in ("image", "audio", "video", "document", "sticker"):
            with self.subTest(tipo=tipo):
                self.assertIsNone(
                    validar_resposta_triagem("Nunca", tipo)
                )


if __name__ == "__main__":
    unittest.main()
