import unittest

from core.repositories.funil import (
    listar_conversas_pendentes_funil,
    marcar_conversa_como_enviada_ao_funil,
)


class CursorFake:
    def __init__(self, *, fetchall=None, fetchone=None):
        self._fetchall = fetchall or []
        self._fetchone = fetchone
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return self._fetchall

    def fetchone(self):
        return self._fetchone


class RepositorioFunilTests(unittest.TestCase):
    def test_lista_somente_conversas_finalizadas_pendentes(self):
        cursor = CursorFake(fetchall=[(10,), (20,)])

        resultado = listar_conversas_pendentes_funil(
            7,
            cursor,
            limite=50,
        )

        self.assertEqual(resultado, [10, 20])
        self.assertEqual(cursor.params, (7, 50))
        self.assertIn("id_etapa_atual = %s", cursor.sql)
        self.assertIn("status_ativa = FALSE", cursor.sql)
        self.assertIn("finalizou_em IS NOT NULL", cursor.sql)
        self.assertIn("lead_no_funil IS NOT TRUE", cursor.sql)

    def test_rejeita_etapa_final_ou_limite_invalidos(self):
        cursor = CursorFake()

        with self.assertRaises(ValueError):
            listar_conversas_pendentes_funil(0, cursor)

        with self.assertRaises(ValueError):
            listar_conversas_pendentes_funil(7, cursor, limite=0)

    def test_marca_envio_ao_funil_com_sucesso(self):
        cursor = CursorFake(fetchone=(10,))

        atualizado = marcar_conversa_como_enviada_ao_funil(
            10,
            cursor,
        )

        self.assertTrue(atualizado)
        self.assertEqual(cursor.params, (10,))
        self.assertIn("SET lead_no_funil = TRUE", cursor.sql)
        self.assertIn("lead_no_funil IS NOT TRUE", cursor.sql)

    def test_marcacao_repetida_e_idempotente(self):
        cursor = CursorFake(fetchone=None)

        atualizado = marcar_conversa_como_enviada_ao_funil(
            10,
            cursor,
        )

        self.assertFalse(atualizado)


if __name__ == "__main__":
    unittest.main()
