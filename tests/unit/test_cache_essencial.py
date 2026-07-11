import unittest
from unittest.mock import patch

from core.cache import cache_unidade
from core.cache.runtime import cache_conversas_bloqueadas


class FakeRedisUnidade:
    def __init__(self, presente):
        self.presente = presente

    def hexists(self, _key, _field):
        return self.presente


class CacheEssencialTests(unittest.TestCase):
    def test_hit_de_unidade_e_rapido_e_nao_consulta_banco(self):
        with patch.object(
            cache_unidade,
            "get_redis_safe",
            return_value=FakeRedisUnidade(presente=True),
        ), patch.object(
            cache_unidade,
            "_sincronizar_cache_unidades_por_versao",
        ), patch.object(
            cache_unidade,
            "_cache_valido",
            return_value=True,
        ), patch.object(
            cache_unidade,
            "_unidade_esta_ativa_banco_e_repara_cache",
        ) as fallback_banco:
            resultado = cache_unidade.unidade_esta_ativa("123456")

        self.assertTrue(resultado)
        fallback_banco.assert_not_called()

    def test_miss_de_unidade_e_confirmado_no_banco(self):
        with patch.object(
            cache_unidade,
            "get_redis_safe",
            return_value=FakeRedisUnidade(presente=False),
        ), patch.object(
            cache_unidade,
            "_sincronizar_cache_unidades_por_versao",
        ), patch.object(
            cache_unidade,
            "_cache_valido",
            return_value=True,
        ), patch.object(
            cache_unidade,
            "_unidade_esta_ativa_banco_e_repara_cache",
            return_value=True,
        ) as fallback_banco:
            resultado = cache_unidade.unidade_esta_ativa("123456")

        self.assertTrue(resultado)
        fallback_banco.assert_called_once_with(
            "123456",
            reparar_cache_se_ausente=False,
        )

    def test_redis_indisponivel_usa_banco_para_unidade_e_bloqueio(self):
        with patch.object(
            cache_unidade,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_unidade,
            "_unidade_esta_ativa_banco_e_repara_cache",
            return_value=True,
        ) as unidade_banco:
            self.assertTrue(cache_unidade.unidade_esta_ativa("123456"))

        unidade_banco.assert_called_once_with(
            "123456",
            reparar_cache_se_ausente=True,
        )

        with patch.object(
            cache_conversas_bloqueadas,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ), patch.object(
            cache_conversas_bloqueadas,
            "_conversa_esta_bloqueada_banco_e_repara_cache",
            return_value=True,
        ) as bloqueio_banco:
            resultado = (
                cache_conversas_bloqueadas
                .conversa_esta_bloqueada_cache(
                    "5571999999999",
                    "123456",
                )
            )

        self.assertTrue(resultado)
        bloqueio_banco.assert_called_once_with(
            "5571999999999",
            "123456",
        )


if __name__ == "__main__":
    unittest.main()
