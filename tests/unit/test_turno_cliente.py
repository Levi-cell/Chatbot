import unittest
from unittest.mock import patch

from core.repositories import turno_cliente
from tests.helpers import FakeCursor


class TurnoClienteTests(unittest.TestCase):
    def test_dados_invalidos_bloqueiam_turno(self):
        resultado = turno_cliente.avaliar_turno_cliente_para_fila(
            cursor=object(),
            cliente_telefone="",
            id_phone_unidade="123456",
        )

        self.assertFalse(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "dados_invalidos")

    def test_sem_fila_aberta_libera(self):
        with patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            return_value={
                "existe_fila_aberta": False,
                "todas_abertas_respondidas": False,
                "total_abertas": 0,
                "id_mensagem_bloqueadora": None,
            },
        ):
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone="5571999999999",
                id_phone_unidade="123456",
            )

        self.assertTrue(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "sem_fila_aberta")

    def test_fila_aberta_sem_resposta_bloqueia(self):
        with patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            return_value={
                "existe_fila_aberta": True,
                "todas_abertas_respondidas": False,
                "total_abertas": 1,
                "id_mensagem_bloqueadora": 20,
            },
        ):
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone="5571999999999",
                id_phone_unidade="123456",
            )

        self.assertFalse(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "fila_aberta_sem_resposta_bot")

    def test_fila_aberta_respondida_pelo_bot_libera_recuperacao(self):
        with patch.object(
            turno_cliente,
            "avaliar_filas_abertas_turno",
            return_value={
                "existe_fila_aberta": True,
                "todas_abertas_respondidas": True,
                "total_abertas": 1,
                "id_mensagem_bloqueadora": None,
            },
        ):
            resultado = turno_cliente.avaliar_turno_cliente_para_fila(
                cursor=object(),
                cliente_telefone="5571999999999",
                id_phone_unidade="123456",
            )

        self.assertTrue(resultado["pode_enfileirar"])
        self.assertEqual(resultado["motivo"], "fila_aberta_respondida_bot")

    def test_advisory_lock_usa_phone_id_e_cliente_como_chaves(self):
        cursor = FakeCursor()

        turno_cliente.adquirir_lock_turno_cliente(
            cursor,
            cliente_telefone="5571999999999",
            id_phone_unidade="123456",
        )

        sql, params = cursor.calls[0]
        self.assertIn("pg_advisory_xact_lock", sql)
        self.assertEqual(params, ("123456", "5571999999999"))

    def test_consulta_turno_usa_historico_vinculado_sem_last_from(self):
        cursor = FakeCursor(fetchone_result=(True, True, 1, None))

        resultado = turno_cliente.avaliar_filas_abertas_turno(
            cursor,
            cliente_telefone="5571999999999",
            id_phone_unidade="123456",
        )

        sql, params = cursor.calls[0]
        self.assertNotIn("last_message_from", sql)
        self.assertIn("h.id_mensagem_fila = f.id_mensagem", sql)
        self.assertIn("h.id_hash_cliente_origem = f.id_hash_msg", sql)
        self.assertEqual(params, ("5571999999999", "123456"))
        self.assertTrue(resultado["todas_abertas_respondidas"])


if __name__ == "__main__":
    unittest.main()
