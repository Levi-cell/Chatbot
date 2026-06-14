import unittest

from core.repositories import inserts, updates
from tests.helpers import FakeCursor


class RepositoryTests(unittest.TestCase):
    def test_atualizar_conversa_resposta_bot_exige_etapa(self):
        with self.assertRaises(ValueError):
            updates.atualizar_conversa_resposta_bot(10, None, FakeCursor())

    def test_atualizar_conversa_resposta_bot_falha_se_nenhuma_linha(self):
        with self.assertRaises(ValueError):
            updates.atualizar_conversa_resposta_bot(10, 1, FakeCursor(rowcount=0))

    def test_atualizar_conversa_resposta_bot_sucesso(self):
        cursor = FakeCursor(rowcount=1)

        self.assertEqual(updates.atualizar_conversa_resposta_bot(10, 1, cursor), 1)
        sql, params = cursor.calls[0]

        self.assertIn("UPDATE chatbot.conversa", sql)
        self.assertEqual(params, (1, 10))

    def test_inserir_historico_mensagem_bot_exige_id_hash_bot(self):
        with self.assertRaises(ValueError):
            inserts.inserir_historico_mensagem_bot(
                {
                    "id_conversa": 10,
                    "mensagem_cliente_atual": {
                        "id_mensagem_fila": 20,
                        "id_hash_msg": "wamid.cliente",
                    },
                },
                {
                    "id_etapa_resultante": 1,
                    "mensagem_bot": "Ola!",
                },
                FakeCursor(),
            )

    def test_inserir_historico_mensagem_bot_sucesso(self):
        cursor = FakeCursor(fetchone_result=(300, "2026-01-01T00:00:00", True))

        resultado = inserts.inserir_historico_mensagem_bot(
            {
                "id_conversa": 10,
                "mensagem_cliente_atual": {
                    "id_mensagem_fila": 20,
                    "id_hash_msg": "wamid.cliente",
                    "cliente_telefone": "5571999999999",
                    "id_phone_unidade": "123456",
                    "unidade_telefone": "5571000000000",
                },
            },
            {
                "id_etapa_resultante": 1,
                "mensagem_bot": "Ola!",
                "id_hash_msg_bot": "wamid.bot",
                "tipo_mensagem": "interactive_button",
            },
            cursor,
        )

        self.assertEqual(resultado, (300, "2026-01-01T00:00:00", True))
        sql, params = cursor.calls[0]

        self.assertIn("INSERT INTO chatbot.historico_mensagens", sql)
        self.assertEqual(params[0:3], (10, 20, "wamid.cliente"))


if __name__ == "__main__":
    unittest.main()
