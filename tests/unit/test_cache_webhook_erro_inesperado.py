import unittest
from unittest.mock import patch

from core.cache.runtime import (
    cache_webhook_erro_inesperado as cache_erro,
)


class FakeRedis:
    def __init__(self):
        self.valores = {}
        self.expiracoes = {}

    def pipeline(self, transaction=True):
        return FakePipeline(self, transaction)


class FakePipeline:
    def __init__(self, redis, transaction):
        self.redis = redis
        self.transaction = transaction
        self.operacoes = []

    def incr(self, key):
        self.operacoes.append(("incr", key))
        return self

    def expire(self, key, ttl):
        self.operacoes.append(
            ("expire", key, ttl)
        )
        return self

    def execute(self):
        resultados = []

        for nome, key, *argumentos in self.operacoes:
            if nome == "incr":
                total = int(
                    self.redis.valores.get(key, 0)
                ) + 1
                self.redis.valores[key] = total
                resultados.append(total)

            elif nome == "expire":
                self.redis.expiracoes[key] = int(
                    argumentos[0]
                )
                resultados.append(True)

        return resultados


class CacheWebhookErroInesperadoTests(unittest.TestCase):
    def setUp(self):
        self.redis = FakeRedis()
        self.redis_patch = patch.object(
            cache_erro,
            "get_redis_safe",
            return_value=self.redis,
        )
        self.redis_patch.start()

    def tearDown(self):
        self.redis_patch.stop()

    def registrar(self, wamid="wamid.test.1"):
        return (
            cache_erro
            .registrar_tentativa_erro_inesperado(
                wamid,
            )
        )

    def test_primeiras_tres_tentativas_pedem_503(self):
        resultados = [
            self.registrar()
            for _ in range(3)
        ]

        self.assertEqual(
            [
                resultado["tentativa"]
                for resultado in resultados
            ],
            [1, 2, 3],
        )
        self.assertTrue(
            all(
                resultado["retornar_503"]
                for resultado in resultados
            )
        )

    def test_quarta_e_posteriores_pedem_200(self):
        resultados = [
            self.registrar()
            for _ in range(5)
        ]

        self.assertFalse(
            resultados[3]["retornar_503"]
        )
        self.assertFalse(
            resultados[4]["retornar_503"]
        )
        self.assertEqual(
            resultados[3]["tentativa"],
            4,
        )

    def test_wamids_diferentes_nao_compartilham_contagem(self):
        primeiro = self.registrar("wamid.a")
        segundo = self.registrar("wamid.b")

        self.assertEqual(primeiro["tentativa"], 1)
        self.assertEqual(segundo["tentativa"], 1)
        self.assertEqual(len(self.redis.valores), 2)

    def test_chave_recebe_ttl(self):
        self.registrar()

        self.assertEqual(
            list(self.redis.expiracoes.values()),
            [7 * 24 * 60 * 60],
        )

    def test_wamid_ausente_retorna_200_sem_redis(self):
        with patch.object(
            cache_erro,
            "get_redis_safe",
        ) as get_redis:
            resultado = (
                cache_erro
                .registrar_tentativa_erro_inesperado(
                    None,
                )
            )

        self.assertFalse(resultado["retornar_503"])
        self.assertEqual(
            resultado["motivo"],
            "wamid_ausente",
        )
        get_redis.assert_not_called()

    def test_redis_indisponivel_retorna_200(self):
        with patch.object(
            cache_erro,
            "get_redis_safe",
            side_effect=ConnectionError("redis caiu"),
        ):
            resultado = self.registrar()

        self.assertFalse(resultado["retornar_503"])
        self.assertEqual(
            resultado["motivo"],
            "redis_indisponivel",
        )


if __name__ == "__main__":
    unittest.main()
