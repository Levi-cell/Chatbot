import unittest

from core.integrations.whatsapp.messages.etapa9_messages import (
    BOTAO_ETAPA9_INICIAR_TRIAGEM,
    MENSAGEM_TRIAGEM_COGNITIVA_ETAPA9,
    montar_botoes_etapa9,
    montar_mensagem_triagem_cognitiva_etapa9,
)


class MessagesEtapa9Tests(unittest.TestCase):
    def test_mensagem_apresenta_as_seis_perguntas(self):
        self.assertEqual(
            montar_mensagem_triagem_cognitiva_etapa9(),
            MENSAGEM_TRIAGEM_COGNITIVA_ETAPA9,
        )
        self.assertIn(
            "6 perguntas objetivas de seleção única",
            MENSAGEM_TRIAGEM_COGNITIVA_ETAPA9,
        )

    def test_possui_somente_botao_iniciar_triagem(self):
        self.assertEqual(
            montar_botoes_etapa9(),
            (BOTAO_ETAPA9_INICIAR_TRIAGEM,),
        )


if __name__ == "__main__":
    unittest.main()
