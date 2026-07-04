import unittest

from core.repositories.email_cliente import atualizar_email_cliente


class FakeCursor:
    def __init__(self, rowcount=1):
        self.rowcount = rowcount
        self.sql = None
        self.params = None

    def execute(self, sql, params):
        self.sql = sql
        self.params = params


class RepositorioEmailClienteTests(unittest.TestCase):
    def test_atualiza_email_do_cliente_correto(self):
        cursor = FakeCursor()

        atualizar_email_cliente(
            20,
            "cliente@exemplo.com",
            cursor,
        )

        self.assertIn("UPDATE chatbot.cliente", cursor.sql)
        self.assertEqual(
            cursor.params,
            ("cliente@exemplo.com", 20),
        )

    def test_cliente_ausente_falha(self):
        cursor = FakeCursor(rowcount=0)

        with self.assertRaises(RuntimeError):
            atualizar_email_cliente(
                20,
                "cliente@exemplo.com",
                cursor,
            )


if __name__ == "__main__":
    unittest.main()
