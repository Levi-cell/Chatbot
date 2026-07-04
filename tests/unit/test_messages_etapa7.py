import unittest

from core.integrations.whatsapp.messages.etapa7_messages import (
    BOTAO_ETAPA7_QUERO_AGENDAR,
    BOTAO_ETAPA7_TALVEZ_MAIS_TARDE,
    montar_botoes_etapa7,
    montar_mensagem_retorno_cliente_contexto_invalido_etapa7,
    montar_mensagem_retorno_cliente_etapa7,
    montar_mensagem_retorno_cliente_financeiro_etapa7,
    montar_mensagem_retorno_cliente_midia_etapa7,
    montar_mensagem_retorno_dependente_contexto_invalido_etapa7,
    montar_mensagem_retorno_dependente_etapa7,
    montar_mensagem_retorno_dependente_financeiro_etapa7,
    montar_mensagem_retorno_dependente_midia_etapa7,
)


class MessagesEtapa7Tests(unittest.TestCase):
    def test_mensagens_de_dependente_recebem_nome(self):
        mensagens = (
            montar_mensagem_retorno_dependente_etapa7("Alice"),
            montar_mensagem_retorno_dependente_midia_etapa7("Alice"),
            montar_mensagem_retorno_dependente_financeiro_etapa7("Alice"),
            montar_mensagem_retorno_dependente_contexto_invalido_etapa7(
                "Alice"
            ),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertIn("Alice", mensagem)
                self.assertNotIn("{nome}", mensagem)

    def test_mensagens_de_cliente_tem_contexto_correto(self):
        mensagens = (
            montar_mensagem_retorno_cliente_etapa7(),
            montar_mensagem_retorno_cliente_midia_etapa7(),
            montar_mensagem_retorno_cliente_financeiro_etapa7(),
            montar_mensagem_retorno_cliente_contexto_invalido_etapa7(),
        )

        for mensagem in mensagens:
            with self.subTest(mensagem=mensagem):
                self.assertIn("agendamento", mensagem)

    def test_botoes_repetem_as_opcoes_da_oferta(self):
        self.assertEqual(
            montar_botoes_etapa7(),
            (
                BOTAO_ETAPA7_QUERO_AGENDAR,
                BOTAO_ETAPA7_TALVEZ_MAIS_TARDE,
            ),
        )


if __name__ == "__main__":
    unittest.main()
