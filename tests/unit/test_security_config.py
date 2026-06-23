import os
import unittest
from unittest.mock import patch

from core.config_env import env_bool, env_csv, env_int, env_required
from core.logging_config import short_value


class SecurityConfigTests(unittest.TestCase):
    def test_short_value_mascara_wa_id_com_13_digitos(self):
        self.assertEqual(short_value("5571999999999"), "55...99")

    def test_short_value_mascara_telefone_com_11_digitos(self):
        self.assertEqual(short_value("71999999999"), "71...99")

    def test_short_value_preserva_identificador_curto(self):
        self.assertEqual(short_value("123"), "123")

    def test_env_required_rejeita_valor_ausente(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "SEGREDO_TESTE"):
                env_required("SEGREDO_TESTE")

    def test_helpers_convertem_tipos_sem_ambiguidade(self):
        with patch.dict(
            os.environ,
            {
                "BOOL_TESTE": "sim",
                "INT_TESTE": "42",
                "CSV_TESTE": "um, dois",
            },
            clear=False,
        ):
            self.assertTrue(env_bool("BOOL_TESTE"))
            self.assertEqual(env_int("INT_TESTE"), 42)
            self.assertEqual(env_csv("CSV_TESTE"), ["um", "dois"])


if __name__ == "__main__":
    unittest.main()
