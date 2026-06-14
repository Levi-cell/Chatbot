import unittest
from unittest.mock import patch

from django.contrib import admin, messages

from webhook.admin import UnidadeAdmin
from webhook.models import Unidade
from core.cache import cache_reset, cache_unidade
from core.cache.runtime import cache_cliente, cache_conversas_bloqueadas


class FakeRedis:
    def __init__(self):
        self.deleted = []
        self.patterns = []

    def delete(self, *keys):
        self.deleted.extend(keys)
        return len(keys)

    def scan_iter(self, match, count=500):
        self.patterns.append((match, count))
        return [f"{match}:1", f"{match}:2"]


class FakeRequest:
    user = "tester"

    def __init__(self):
        self.messages = []


def capturar_message_user(_self, request, message, level=messages.INFO):
    request.messages.append((message, level))


class CacheAndAdminTests(unittest.TestCase):
    def test_cache_cliente_redis_falha_retorna_none(self):
        with patch.object(
            cache_cliente,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ):
            self.assertIsNone(cache_cliente.buscar_cliente_cache("5571999999999"))

    def test_cache_unidade_redis_falha_usa_banco(self):
        chamadas = []

        with patch.object(
            cache_unidade,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_unidade,
            "_unidade_esta_ativa_banco_e_repara_cache",
            lambda phone: chamadas.append(phone) or True,
        ):
            self.assertTrue(cache_unidade.unidade_esta_ativa("123456"))

        self.assertEqual(chamadas, ["123456"])

    def test_cache_conversa_bloqueada_redis_falha_usa_banco(self):
        chamadas = []

        with patch.object(
            cache_conversas_bloqueadas,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_conversas_bloqueadas,
            "_conversa_esta_bloqueada_banco_e_repara_cache",
            lambda cliente, phone: chamadas.append((cliente, phone)) or True,
        ):
            self.assertTrue(
                cache_conversas_bloqueadas.conversa_esta_bloqueada_cache(
                    "5571999999999",
                    "123456",
                )
            )

        self.assertEqual(chamadas, [("5571999999999", "123456")])

    def test_cache_reset_limpa_prefixos_e_recria_unidades(self):
        fake_redis = FakeRedis()

        with patch.object(cache_reset, "get_redis_safe", return_value=fake_redis), patch.object(
            cache_reset,
            "recarregar_cache_unidades",
            return_value=3,
        ):
            resultado = cache_reset.resetar_cache_redis_dev()

        self.assertEqual(resultado["unidades_recriadas"], 3)
        self.assertGreaterEqual(resultado["chaves_exatas_removidas"], 1)
        self.assertEqual(resultado["chaves_por_prefixo_removidas"], 6)
        self.assertTrue(
            any(padrao == "cliente_cache:*" for padrao, _count in fake_redis.patterns)
        )
        self.assertTrue(
            any(padrao == "conversa_bloqueada:*" for padrao, _count in fake_redis.patterns)
        )
        self.assertTrue(
            any(padrao.startswith("webhook_flood_rate") for padrao, _count in fake_redis.patterns)
        )

    def test_admin_unidade_bloqueia_alteracao_se_redis_falhar(self):
        unidade_admin = UnidadeAdmin(Unidade, admin.site)
        request = FakeRequest()

        with patch.object(UnidadeAdmin, "message_user", capturar_message_user), patch(
            "webhook.admin.validar_cache_unidades_disponivel_ou_erro",
            side_effect=cache_unidade.CacheUnidadesIndisponivel("redis caiu"),
        ):
            resultado = unidade_admin._validar_cache_unidades_antes_de_alterar(
                request,
                "salvar",
                meta_validada=True,
            )

        self.assertFalse(resultado)
        self.assertEqual(request.messages[0][1], messages.ERROR)
        self.assertIn("Redis falhou", request.messages[0][0])
        self.assertIn("Nenhuma alteracao foi feita no banco", request.messages[0][0])


if __name__ == "__main__":
    unittest.main()
