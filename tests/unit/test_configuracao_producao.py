import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import core.config_env  # Carrega o .env antes dos ambientes isolados dos testes.


ROOT_DIR = Path(__file__).resolve().parents[2]
SETTINGS_PATH = ROOT_DIR / "callback" / "callback" / "settings.py"
CONNECTION_PATH = ROOT_DIR / "core" / "database" / "connection_aws.py"

BASE_ENV = {
    "DJANGO_SECRET_KEY": "test-secret-key-not-for-production",
    "DB_HOST": "localhost",
    "DB_NAME": "test_chatbot",
    "DB_USER": "test_user",
    "DB_PASSWORD": "test_password",
    "DB_PORT": "5432",
}


def carregar_modulo(caminho, nome, ambiente=None):
    variaveis = {**BASE_ENV, **(ambiente or {})}

    with patch.dict(os.environ, variaveis, clear=True):
        spec = importlib.util.spec_from_file_location(nome, caminho)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)

    return modulo


class ConfiguracaoProducaoTests(unittest.TestCase):
    def test_settings_preservam_defaults_locais(self):
        settings = carregar_modulo(
            SETTINGS_PATH,
            "settings_defaults_locais",
        )

        self.assertEqual(
            settings.STATIC_ROOT,
            settings.BASE_DIR / "staticfiles",
        )
        self.assertIsNone(settings.SECURE_PROXY_SSL_HEADER)
        self.assertEqual(
            settings.DATABASES["default"]["OPTIONS"],
            {"options": "-c search_path=chatbot"},
        )

    def test_settings_ativam_proxy_e_ssl_somente_por_ambiente(self):
        settings = carregar_modulo(
            SETTINGS_PATH,
            "settings_producao",
            {
                "DJANGO_TRUST_X_FORWARDED_PROTO": "True",
                "DB_SSLMODE": "verify-full",
                "DB_SSLROOTCERT": "/etc/ssl/certs/rds-ca.pem",
            },
        )

        self.assertEqual(
            settings.SECURE_PROXY_SSL_HEADER,
            ("HTTP_X_FORWARDED_PROTO", "https"),
        )
        self.assertEqual(
            settings.DATABASES["default"]["OPTIONS"],
            {
                "options": "-c search_path=chatbot",
                "sslmode": "verify-full",
                "sslrootcert": "/etc/ssl/certs/rds-ca.pem",
            },
        )

    def test_conexao_psycopg_preserva_default_sem_ssl_explicito(self):
        connection = carregar_modulo(
            CONNECTION_PATH,
            "connection_defaults_locais",
        )

        self.assertNotIn("sslmode", connection.setup)
        self.assertNotIn("sslrootcert", connection.setup)

    def test_conexao_psycopg_repassa_ssl_e_application_name(self):
        connection = carregar_modulo(
            CONNECTION_PATH,
            "connection_producao",
            {
                "DB_SSLMODE": "verify-full",
                "DB_SSLROOTCERT": "/etc/ssl/certs/rds-ca.pem",
            },
        )

        with patch.object(
            connection.psycopg,
            "connect",
            return_value="conexao",
        ) as conectar:
            resultado = connection.get_conn("worker_flow")

        self.assertEqual(resultado, "conexao")
        conectar.assert_called_once_with(
            host="localhost",
            dbname="test_chatbot",
            user="test_user",
            password="test_password",
            port=5432,
            sslmode="verify-full",
            sslrootcert="/etc/ssl/certs/rds-ca.pem",
            application_name="worker_flow",
        )


if __name__ == "__main__":
    unittest.main()
