import unittest

from core.integrations.whatsapp.messages.etapa4_messages import (
    montar_mensagem_cliente_menor_18_etapa4,
    montar_mensagem_contexto_idade_dependente_invalida_etapa4,
    montar_mensagem_contexto_idade_invalida_etapa4,
    montar_mensagem_dependente_menor_5_etapa4,
    montar_mensagem_idade_dependente_etapa4,
    montar_mensagem_idade_dependente_etapa4_financeiro,
    montar_mensagem_idade_dependente_etapa4_midia,
    montar_mensagem_idade_etapa4,
    montar_mensagem_idade_etapa4_financeiro,
    montar_mensagem_idade_etapa4_midia,
    montar_mensagem_idade_acima_99_etapa4,
)


class MessagesEtapa4Tests(unittest.TestCase):
    def test_mensagem_acima_de_99_exibe_numero_comercial(self):
        mensagem = montar_mensagem_idade_acima_99_etapa4(
            "557536321234"
        )

        self.assertIn("557536321234", mensagem)

    def test_mensagem_acima_de_99_exige_numero_comercial(self):
        with self.assertRaises(ValueError):
            montar_mensagem_idade_acima_99_etapa4("")

    def test_mensagens_do_cliente_perguntam_a_propria_idade(self):
        mensagens = (
            montar_mensagem_idade_etapa4(),
            montar_mensagem_idade_etapa4_midia(),
            montar_mensagem_idade_etapa4_financeiro(),
            montar_mensagem_contexto_idade_invalida_etapa4(),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertIn("sua idade", mensagem)
                self.assertNotIn("{nome}", mensagem)

    def test_mensagens_do_dependente_interpolam_o_nome(self):
        mensagens = (
            montar_mensagem_idade_dependente_etapa4("Alice"),
            montar_mensagem_idade_dependente_etapa4_midia("Alice"),
            montar_mensagem_idade_dependente_etapa4_financeiro("Alice"),
            montar_mensagem_contexto_idade_dependente_invalida_etapa4(
                "Alice"
            ),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertIn("idade de Alice", mensagem)
                self.assertNotIn("{nome}", mensagem)

    def test_tratamento_de_contexto_orienta_resposta_numerica(self):
        self.assertIn(
            "Digite apenas o número",
            montar_mensagem_contexto_idade_invalida_etapa4(),
        )
        self.assertIn(
            "Digite apenas o número",
            montar_mensagem_contexto_idade_dependente_invalida_etapa4(
                "Alice"
            ),
        )

    def test_cliente_menor_de_idade_e_orientado_a_retornar_com_adulto(self):
        mensagem = montar_mensagem_cliente_menor_18_etapa4()

        self.assertIn("menos de 18 anos", mensagem)
        self.assertIn("adulto responsável", mensagem)
        self.assertIn("adulto", mensagem)
        self.assertNotIn("botão", mensagem)

    def test_dependente_menor_de_cinco_anos_recebe_orientacao(self):
        mensagem = montar_mensagem_dependente_menor_5_etapa4("Alice")

        self.assertIn("a partir de 5 anos", mensagem)
        self.assertIn("Quando Alice completar 5 anos", mensagem)
        self.assertNotIn("{nome}", mensagem)
        self.assertNotIn("botão", mensagem)


if __name__ == "__main__":
    unittest.main()
