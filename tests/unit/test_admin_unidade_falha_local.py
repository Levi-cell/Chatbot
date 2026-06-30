import inspect
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin
from django.db import DatabaseError

from webhook.admin import UnidadeAdmin
from webhook.models import Unidade


class AdminUnidadeFalhaLocalTests(unittest.TestCase):
    def setUp(self):
        self.model_admin = UnidadeAdmin(Unidade, admin.site)

    def test_mensagem_banco_sem_meta_nao_declara_sucesso_meta(self):
        request = SimpleNamespace()

        mensagem = self.model_admin._mensagem_falha_banco(request)

        self.assertIn("banco falhou", mensagem)
        self.assertIn("Nenhuma operação Meta", mensagem)

    def test_mensagem_banco_com_meta_preserva_estado_externo(self):
        request = SimpleNamespace(
            _unidade_meta_sucesso={
                "acao": "desregistrar",
                "phone_number_id": "123",
            }
        )

        mensagem = self.model_admin._mensagem_falha_banco(request)

        self.assertIn(
            "Meta concluiu a operação com sucesso",
            mensagem,
        )
        self.assertIn("alteração da Meta foi mantida", mensagem)
        self.assertIn("conferência manual", mensagem)

    def test_mensagem_redis_com_meta_nao_promete_compensacao(self):
        request = SimpleNamespace(
            _unidade_meta_sucesso={
                "acao": "registrar",
                "phone_number_id": "123",
            }
        )

        mensagem = self.model_admin._mensagem_falha_redis(request)

        self.assertIn("Redis falhou", mensagem)
        self.assertIn("alteração da Meta foi mantida", mensagem)
        self.assertNotIn("compens", mensagem.lower())

    def test_cache_wrapped_database_error_e_identificado(self):
        erro_banco = DatabaseError("banco caiu")
        erro_cache = RuntimeError("cache não atualizou")
        erro_cache.__cause__ = erro_banco

        self.assertTrue(
            self.model_admin._falha_cache_originada_no_banco(
                erro_cache
            )
        )

    def test_plano_nao_adiciona_compensacao_ao_admin(self):
        source = inspect.getsource(UnidadeAdmin)

        self.assertNotIn("compensar", source)
        self.assertNotIn(
            "sincronizar_edicao_unidade",
            source,
        )

    def test_sucesso_meta_e_marcado_antes_da_persistencia_local(self):
        request = SimpleNamespace()

        with patch(
            "webhook.admin.registrar_numero_whatsapp",
            return_value=(200, {"success": True}),
        ):
            resultado = (
                self.model_admin._registrar_meta_antes_de_salvar(
                    request,
                    "phone-1",
                )
            )

        self.assertTrue(resultado)
        self.assertEqual(
            request._unidade_meta_sucesso,
            {
                "acao": "registrar",
                "phone_number_id": "phone-1",
            },
        )


if __name__ == "__main__":
    unittest.main()
