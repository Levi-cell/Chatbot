import unittest

from core.repositories import inserts, updates
from tests.helpers import FakeCursor


DATA_CLIENTE = "2026-01-01T00:00:00"
DATA_BOT = "2026-01-01T00:01:00"


class RepositoryTests(unittest.TestCase):
    def test_inicializar_conversa_exige_etapa1(self):
        with self.assertRaises(ValueError):
            updates.inicializar_conversa_resposta_bot(
                10,
                2,
                DATA_BOT,
                FakeCursor(),
            )

    def test_inicializar_conversa_falha_se_nenhuma_linha(self):
        with self.assertRaises(ValueError):
            updates.inicializar_conversa_resposta_bot(
                10,
                1,
                DATA_BOT,
                FakeCursor(rowcount=0),
            )

    def test_transicao_exige_origem_evento_e_destino(self):
        casos = (
            (None, "evento", 2),
            (1, None, 2),
            (1, "evento", None),
        )

        for origem, evento, destino in casos:
            with self.subTest(
                origem=origem,
                evento=evento,
                destino=destino,
            ):
                with self.assertRaises(ValueError):
                    updates.atualizar_conversa_por_transicao(
                        10,
                        origem,
                        evento,
                        destino,
                        DATA_BOT,
                        FakeCursor(),
                    )

    def test_transicao_revalida_aresta_no_postgresql(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_conversa_por_transicao(
            10,
            2,
            "para_mim",
            4,
            DATA_BOT,
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("FROM chatbot.etapa_transicao", sql)
        self.assertIn("transicao.id_etapa_origem = %s", sql)
        self.assertIn("transicao.evento = %s", sql)
        self.assertIn("transicao.id_etapa_destino = %s", sql)
        self.assertNotIn("id_etapa_atual + 1", sql)
        self.assertNotIn("GREATEST(id_etapa_atual", sql)
        self.assertEqual(
            params,
            (2, 4, DATA_BOT, 10, 2, "para_mim", 4, 2, False, 4),
        )

    def test_transicao_idempotente_limita_reaplicacao_ao_destino(self):
        cursor = FakeCursor(rowcount=1)

        updates.atualizar_conversa_por_transicao(
            10,
            2,
            "para_mim",
            4,
            DATA_BOT,
            cursor,
            permitir_reaplicacao=True,
        )

        sql, params = cursor.calls[0]
        self.assertIn("ELSE conversa.id_etapa_atual", sql)
        self.assertIn("AND conversa.id_etapa_atual = %s", sql)
        self.assertEqual(params[-3:], (2, True, 4))

    def test_atualizar_conversa_mensagem_cliente_usa_data_persistida(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_conversa_mensagem_cliente(
            10,
            DATA_CLIENTE,
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("last_message_from = 'cliente'", sql)
        self.assertNotIn("NOW()", sql)
        self.assertEqual(params, (DATA_CLIENTE, 10))

    def test_atualizar_conversa_resposta_bot_sem_avancar_usa_data_persistida(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_conversa_resposta_bot_sem_avancar(
            10,
            DATA_BOT,
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("last_message_from = 'bot'", sql)
        self.assertNotIn("id_etapa_atual", sql)
        self.assertNotIn("NOW()", sql)
        self.assertEqual(params, (DATA_BOT, 10))

    def test_atualizar_status_dependente_conversa(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_status_dependente_conversa(
            10,
            True,
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("SET status_dependente = %s", sql)
        self.assertEqual(params, (True, 10))

    def test_atualizar_nome_dependente_por_conversa(self):
        cursor = FakeCursor(rowcount=1)

        resultado = updates.atualizar_nome_dependente_por_conversa(
            10,
            "Aline",
            cursor,
        )

        self.assertEqual(resultado, 1)
        sql, params = cursor.calls[0]
        self.assertIn("UPDATE chatbot.dependente", sql)
        self.assertIn("SET nome_dependente = %s", sql)
        self.assertIn("WHERE id_conversa = %s", sql)
        self.assertEqual(params, ("Aline", 10))

    def test_atualizar_nome_dependente_exige_registro_da_conversa(self):
        with self.assertRaises(ValueError):
            updates.atualizar_nome_dependente_por_conversa(
                10,
                "Aline",
                FakeCursor(rowcount=0),
            )

    def test_atualizar_status_dependente_exige_conversa_existente(self):
        with self.assertRaises(ValueError):
            updates.atualizar_status_dependente_conversa(
                10,
                False,
                FakeCursor(rowcount=0),
            )

    def test_inserir_dependente_para_conversa_e_idempotente(self):
        cursor = FakeCursor(
            fetchone_result=(30, 5, 10, False),
        )

        resultado = inserts.inserir_dependente_para_conversa(
            10,
            cursor,
        )

        self.assertEqual(
            resultado,
            {
                "id_dependente": 30,
                "id_cliente": 5,
                "id_conversa": 10,
                "inserido": False,
            },
        )
        sql, params = cursor.calls[0]
        self.assertIn("INSERT INTO chatbot.dependente", sql)
        self.assertIn("WHERE NOT EXISTS", sql)
        self.assertEqual(params, (10, 10, 10))

    def test_inserir_historico_cliente_retorna_etapa_persistida(self):
        cursor = FakeCursor(
            fetchone_result=(100, "2026-01-01T00:00:00", 1, False)
        )
        mensagem = {
            "id_mensagem": 20,
            "cliente_telefone": "5571999999999",
            "conteudo_texto": "ola",
            "tipo_mensagem": "text",
            "id_phone_unidade": "123456",
            "unidade_telefone": "5571000000000",
            "data_recebimento": "2026-01-01T00:00:00",
            "id_hash": "wamid.cliente",
        }

        resultado = inserts.inserir_historico_mensagem_cliente(
            mensagem,
            id_conversa=10,
            id_etapa=2,
            cursor=cursor,
        )

        self.assertEqual(
            resultado,
            (100, "2026-01-01T00:00:00", 1, False),
        )
        sql, _params = cursor.calls[0]
        self.assertIn("SELECT id_mensagem, received_data_hora, id_etapa", sql)

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
