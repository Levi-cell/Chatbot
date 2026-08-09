import unittest

from core.repositories.atendimento.dependentes import (
    remover_dependente_placeholder_da_conversa,
)


class CursorFake:
    def __init__(self, *, rowcount, dependente_existente=None):
        self.rowcount = rowcount
        self.dependente_existente = dependente_existente
        self.comandos = []

    def execute(self, sql, parametros):
        self.comandos.append((sql, parametros))

    def fetchone(self):
        return self.dependente_existente


class DependentesRepositorioTests(unittest.TestCase):
    def test_remove_placeholder_vazio(self):
        cursor = CursorFake(rowcount=1)

        removido = remover_dependente_placeholder_da_conversa(10, cursor)

        self.assertTrue(removido)
        self.assertEqual(len(cursor.comandos), 1)
        sql, parametros = cursor.comandos[0]
        self.assertIn("nome_dependente IS NULL", sql)
        self.assertIn("idade IS NULL", sql)
        self.assertEqual(parametros, (10,))

    def test_retry_aceita_placeholder_ja_ausente(self):
        cursor = CursorFake(rowcount=0, dependente_existente=None)

        removido = remover_dependente_placeholder_da_conversa(10, cursor)

        self.assertFalse(removido)
        self.assertEqual(len(cursor.comandos), 2)

    def test_nao_remove_dependente_que_ja_tem_dados(self):
        cursor = CursorFake(rowcount=0, dependente_existente=(30,))

        with self.assertRaisesRegex(ValueError, "com dados"):
            remover_dependente_placeholder_da_conversa(10, cursor)


if __name__ == "__main__":
    unittest.main()
