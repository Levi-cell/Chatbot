import unittest
from unittest.mock import patch

from callback.webhook.services import populating_fila_mensagens as fila
from tests.helpers import FakeConn, FakeCursor
from tests.payloads import payload_sem_mensagem, payload_texto_meta


class PopulatingFilaTests(unittest.TestCase):
    def test_extrair_dados_whatsapp_payload_valido(self):
        dados = fila.extrair_dados_whatsapp(payload_texto_meta())

        self.assertNotIn("erro", dados)
        self.assertEqual(dados["status"], "pending")
        self.assertEqual(dados["retry_count"], 0)
        self.assertEqual(dados["cliente_telefone"], "5571999999999")
        self.assertEqual(dados["id_phone_unidade"], "123456")
        self.assertEqual(dados["id_hash_msg"], "wamid.test.1")

    def test_extrair_dados_whatsapp_sem_mensagem(self):
        dados = fila.extrair_dados_whatsapp(payload_sem_mensagem())

        self.assertEqual(dados["erro"], "evento_sem_mensagem")

    def test_turno_bloqueado_nao_insere(self):
        cursor = FakeCursor()
        conn = FakeConn(cursor=cursor)

        with patch.object(fila, "get_conn", return_value=conn), patch.object(
            fila,
            "avaliar_turno_cliente_para_fila",
            return_value={
                "pode_enfileirar": False,
                "motivo": "fila_aberta_sem_resposta_bot",
            },
        ):
            resultado = fila.inserir_dados_na_tabela_fila(
                fila.extrair_dados_whatsapp(payload_texto_meta())
            )

        self.assertEqual(resultado["status"], "ignored")
        self.assertEqual(resultado["reason"], "fila_aberta_sem_resposta_bot")
        self.assertEqual(conn.commits, 1)
        self.assertTrue(conn.closed)
        self.assertFalse(
            any("INSERT INTO chatbot.fila_mensagens" in call[0] for call in cursor.calls)
        )

    def test_turno_liberado_insere(self):
        cursor = FakeCursor(rowcount=1)
        conn = FakeConn(cursor=cursor)

        with patch.object(fila, "get_conn", return_value=conn), patch.object(
            fila,
            "avaliar_turno_cliente_para_fila",
            return_value={"pode_enfileirar": True, "motivo": "sem_fila_aberta"},
        ):
            resultado = fila.inserir_dados_na_tabela_fila(
                fila.extrair_dados_whatsapp(payload_texto_meta())
            )

        self.assertEqual(resultado["status"], "inserted")
        self.assertEqual(conn.commits, 1)
        self.assertTrue(conn.closed)
        self.assertTrue(
            any("INSERT INTO chatbot.fila_mensagens" in call[0] for call in cursor.calls)
        )

    def test_banco_falha_retorna_error_controlado(self):
        cursor = FakeCursor()
        conn = FakeConn(cursor=cursor)

        def fake_turno(**_kwargs):
            raise RuntimeError("banco caiu")

        with patch.object(fila, "get_conn", return_value=conn), patch.object(
            fila,
            "avaliar_turno_cliente_para_fila",
            fake_turno,
        ):
            resultado = fila.inserir_dados_na_tabela_fila(
                fila.extrair_dados_whatsapp(payload_texto_meta())
            )

        self.assertEqual(resultado["status"], "error")
        self.assertEqual(resultado["reason"], "insert_exception")
        self.assertEqual(conn.rollbacks, 1)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
