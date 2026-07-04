import unittest

from core.repositories.respostas_triagem import registrar_resposta_triagem


class FakeCursor:
    def __init__(self, resultados):
        self.resultados = list(resultados)
        self.execucoes = []

    def execute(self, sql, params):
        self.execucoes.append((sql, params))

    def fetchone(self):
        return self.resultados.pop(0)


class RepositorioRespostasTriagemTests(unittest.TestCase):
    def test_insere_nova_resposta(self):
        cursor = FakeCursor(
            [(30, "frequentemente", 900)]
        )

        resultado = registrar_resposta_triagem(
            10,
            12,
            "frequentemente",
            900,
            cursor,
        )

        self.assertTrue(resultado["inserido"])
        self.assertEqual(resultado["id_resposta_desafio"], 30)
        self.assertEqual(resultado["resposta"], "frequentemente")
        self.assertEqual(
            cursor.execucoes[0][1],
            (10, 12, "frequentemente", 900),
        )

    def test_retry_reutiliza_resposta_identica(self):
        cursor = FakeCursor(
            [
                None,
                (30, "às vezes", 900),
            ]
        )

        resultado = registrar_resposta_triagem(
            10,
            12,
            "às vezes",
            900,
            cursor,
        )

        self.assertFalse(resultado["inserido"])
        self.assertEqual(resultado["id_resposta_desafio"], 30)
        self.assertEqual(len(cursor.execucoes), 2)

    def test_retry_repara_referencia_de_historico_ausente(self):
        cursor = FakeCursor(
            [
                None,
                (30, "nunca", None),
            ]
        )

        resultado = registrar_resposta_triagem(
            10,
            12,
            "nunca",
            900,
            cursor,
        )

        self.assertFalse(resultado["inserido"])
        self.assertEqual(
            resultado["id_historico_mensagem_cliente"],
            900,
        )
        self.assertEqual(len(cursor.execucoes), 3)
        self.assertIn(
            "UPDATE chatbot.respostas_desafios",
            cursor.execucoes[2][0],
        )

    def test_resposta_divergente_para_mesma_pergunta_falha(self):
        cursor = FakeCursor(
            [
                None,
                (30, "nunca", 900),
            ]
        )

        with self.assertRaises(ValueError):
            registrar_resposta_triagem(
                10,
                12,
                "frequentemente",
                901,
                cursor,
            )


if __name__ == "__main__":
    unittest.main()
