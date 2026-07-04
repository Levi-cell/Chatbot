import importlib
import unittest

from core.integrations.whatsapp.messages.triagem_componentes import (
    BOTOES_TRIAGEM,
    RODAPE_TRIAGEM,
)


class MessagesTriagemTests(unittest.TestCase):
    def test_seis_etapas_possuem_cabecalho_e_quatro_variacoes(self):
        for etapa in range(10, 16):
            with self.subTest(etapa=etapa):
                modulo = importlib.import_module(
                    "core.integrations.whatsapp.messages."
                    f"etapa{etapa}_messages"
                )

                cabecalho = getattr(
                    modulo,
                    f"montar_cabecalho_etapa{etapa}",
                )()
                mensagem_cliente = getattr(
                    modulo,
                    f"montar_mensagem_cliente_etapa{etapa}",
                )()
                mensagem_dependente = getattr(
                    modulo,
                    f"montar_mensagem_dependente_etapa{etapa}",
                )("Alice")
                tratamento_cliente = getattr(
                    modulo,
                    "montar_mensagem_cliente_contexto_invalido_"
                    f"etapa{etapa}",
                )()
                tratamento_dependente = getattr(
                    modulo,
                    "montar_mensagem_dependente_contexto_invalido_"
                    f"etapa{etapa}",
                )("Alice")

                self.assertEqual(
                    cabecalho,
                    f"Teste Cognitivo - Pergunta {etapa - 9}",
                )
                self.assertIn("você", mensagem_cliente)
                self.assertIn("Alice", mensagem_dependente)
                self.assertIn(
                    "Não consegui entender sua resposta.",
                    tratamento_cliente,
                )
                self.assertIn(mensagem_cliente, tratamento_cliente)
                self.assertIn(
                    "Não consegui entender sua resposta.",
                    tratamento_dependente,
                )
                self.assertIn(mensagem_dependente, tratamento_dependente)

    def test_opcoes_e_rodape_sao_unicos_para_toda_triagem(self):
        self.assertEqual(
            BOTOES_TRIAGEM,
            ("Nunca", "Às vezes", "Frequentemente"),
        )
        self.assertEqual(
            RODAPE_TRIAGEM,
            "Selecione apenas uma opção abaixo.",
        )


if __name__ == "__main__":
    unittest.main()
