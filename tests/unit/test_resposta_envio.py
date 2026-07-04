import unittest
from types import SimpleNamespace

from core.integrations.whatsapp.pywa_functions.resposta_envio import (
    extrair_id_hash_msg_bot,
)


class RespostaEnvioTests(unittest.TestCase):
    def test_extrai_id_de_objeto_pywa(self):
        resposta = SimpleNamespace(id="wamid.objeto")

        self.assertEqual(
            extrair_id_hash_msg_bot(resposta),
            "wamid.objeto",
        )

    def test_extrai_id_de_resposta_bruta_meta(self):
        resposta = {
            "messages": [
                {"id": "wamid.dicionario"},
            ]
        }

        self.assertEqual(
            extrair_id_hash_msg_bot(resposta),
            "wamid.dicionario",
        )

    def test_objeto_tem_prioridade_sobre_formato_de_dicionario(self):
        class RespostaDictComId(dict):
            id = "wamid.objeto"

        resposta = RespostaDictComId(
            messages=[{"id": "wamid.dicionario"}]
        )

        self.assertEqual(
            extrair_id_hash_msg_bot(resposta),
            "wamid.objeto",
        )

    def test_resposta_sem_id_falha_explicitamente(self):
        respostas_invalidas = (
            None,
            {},
            {"messages": []},
            {"messages": [{}]},
            SimpleNamespace(id=None),
        )

        for resposta in respostas_invalidas:
            with self.subTest(resposta=resposta):
                with self.assertRaisesRegex(
                    ValueError,
                    "Meta confirmou envio",
                ):
                    extrair_id_hash_msg_bot(resposta)


if __name__ == "__main__":
    unittest.main()
