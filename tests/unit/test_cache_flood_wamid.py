import unittest
from unittest.mock import patch

from callback.webhook.services import flood_guard
from core.cache import cache_flood_memoria
from core.cache.runtime import cache_flood_redis


REGRAS = (
    {
        "nome": "rajada_curta",
        "limite": 15,
        "janela_segundos": 5,
    },
)


class FakeRedis:
    def __init__(self, agora):
        self.agora = agora
        self.valores = {}
        self.expiracoes = {}
        self.expira_em = {}

    def eval(self, _script, numero_chaves, *chaves_e_argumentos):
        self._expirar_chaves()
        chaves = list(chaves_e_argumentos[:numero_chaves])
        argumentos = list(chaves_e_argumentos[numero_chaves:])
        dedupe_key = chaves[0]
        evento_novo = dedupe_key not in self.valores

        if evento_novo:
            self.valores[dedupe_key] = "1"
            self.expiracoes[dedupe_key] = int(argumentos[0])
            self.expira_em[dedupe_key] = (
                self.agora() + int(argumentos[0])
            )

        resultados = [1 if evento_novo else 0]

        for indice, contador_key in enumerate(
            chaves[1:],
            start=1,
        ):
            if evento_novo:
                total = int(
                    self.valores.get(contador_key, 0)
                ) + 1
                self.valores[contador_key] = total

                if total == 1:
                    self.expiracoes[contador_key] = int(
                        argumentos[indice]
                    )
                    self.expira_em[contador_key] = (
                        self.agora()
                        + int(argumentos[indice])
                    )

            else:
                total = int(
                    self.valores.get(contador_key, 0)
                )

            resultados.append(total)

        return resultados

    def _expirar_chaves(self):
        agora = self.agora()
        expiradas = [
            key
            for key, instante in self.expira_em.items()
            if instante <= agora
        ]

        for key in expiradas:
            self.valores.pop(key, None)
            self.expiracoes.pop(key, None)
            self.expira_em.pop(key, None)


class CacheFloodRedisWamidTests(unittest.TestCase):
    def setUp(self):
        self.agora = 1000.0
        self.redis = FakeRedis(
            agora=lambda: self.agora,
        )
        self.redis_patch = patch.object(
            cache_flood_redis,
            "get_redis_safe",
            return_value=self.redis,
        )
        self.redis_patch.start()
        self.time_patch = patch.object(
            cache_flood_redis.time,
            "time",
            side_effect=lambda: self.agora,
        )
        self.time_patch.start()

    def tearDown(self):
        self.time_patch.stop()
        self.redis_patch.stop()

    def avaliar(self, wamid, phone="phone-a", wa="cliente-a"):
        return cache_flood_redis.avaliar_flood_redis(
            wa,
            phone,
            wamid,
            REGRAS,
        )

    def test_mesmo_wamid_repetido_quinze_vezes_conta_um(self):
        resultado = None

        for _ in range(15):
            resultado = self.avaliar("wamid.unico")

        self.assertEqual(resultado["total"], 1)
        self.assertFalse(resultado["flood"])

    def test_decimo_quinto_wamid_distinto_detecta_flood(self):
        resultado = None

        for indice in range(15):
            resultado = self.avaliar(
                f"wamid.{indice}"
            )

        self.assertEqual(resultado["total"], 15)
        self.assertTrue(resultado["flood"])

    def test_mesmo_wamid_fica_isolado_por_unidade(self):
        unidade_a = self.avaliar(
            "wamid.igual",
            phone="phone-a",
        )
        unidade_b = self.avaliar(
            "wamid.igual",
            phone="phone-b",
        )

        self.assertEqual(unidade_a["total"], 1)
        self.assertEqual(unidade_b["total"], 1)
        contador_keys = [
            key
            for key in self.redis.valores
            if ":contador:" in key
        ]
        self.assertEqual(len(contador_keys), 2)

    def test_reentrega_em_outra_janela_nao_incrementa(self):
        primeiro = self.avaliar("wamid.1")
        self.agora += 10
        reentrega = self.avaliar("wamid.1")

        self.assertEqual(primeiro["total"], 1)
        self.assertEqual(reentrega["total"], 0)
        self.assertFalse(reentrega["evento_novo"])

    def test_wamid_volta_a_contar_depois_do_ttl_dedupe(self):
        primeiro = self.avaliar("wamid.1")
        self.agora += (
            cache_flood_redis
            .DEDUPLICACAO_TTL_SEGUNDOS
            + 1
        )
        depois_do_ttl = self.avaliar("wamid.1")

        self.assertTrue(primeiro["evento_novo"])
        self.assertTrue(depois_do_ttl["evento_novo"])
        self.assertEqual(depois_do_ttl["total"], 1)

    def test_chaves_tem_ttl_e_prefixo_operacional(self):
        self.avaliar("wamid.1")

        self.assertEqual(len(self.redis.expiracoes), 2)
        dedupe_key = next(
            key
            for key in self.redis.expiracoes
            if ":wamid:" in key
        )
        contador_key = next(
            key
            for key in self.redis.expiracoes
            if ":contador:" in key
        )
        self.assertTrue(
            dedupe_key.startswith("webhook_flood_rate:{")
        )
        self.assertEqual(
            self.redis.expiracoes[dedupe_key],
            7200,
        )
        self.assertEqual(
            self.redis.expiracoes[contador_key],
            15,
        )

    def test_dado_invalido_nao_acessa_redis(self):
        with patch.object(
            cache_flood_redis,
            "get_redis_safe",
        ) as get_redis:
            resultado = cache_flood_redis.avaliar_flood_redis(
                "cliente-a",
                "phone-a",
                None,
                REGRAS,
            )

        self.assertFalse(resultado["flood"])
        get_redis.assert_not_called()


class CacheFloodMemoriaWamidTests(unittest.TestCase):
    def setUp(self):
        with cache_flood_memoria._lock:
            cache_flood_memoria._eventos_por_chave.clear()
            cache_flood_memoria._ultima_limpeza = 0.0

        self.agora = 1000.0
        self.time_patch = patch.object(
            cache_flood_memoria.time,
            "monotonic",
            side_effect=lambda: self.agora,
        )
        self.time_patch.start()

    def tearDown(self):
        self.time_patch.stop()

    def avaliar(self, wamid):
        return cache_flood_memoria.avaliar_flood_memoria(
            "cliente-a",
            "phone-a",
            wamid,
            REGRAS,
        )

    def test_memoria_nao_duplica_o_mesmo_wamid(self):
        resultado = None

        for _ in range(15):
            resultado = self.avaliar("wamid.unico")

        self.assertEqual(resultado["total"], 1)
        self.assertFalse(resultado["flood"])

    def test_memoria_deduplica_em_outra_janela(self):
        primeiro = self.avaliar("wamid.unico")
        self.agora += 10
        reentrega = self.avaliar("wamid.unico")

        self.assertEqual(primeiro["total"], 1)
        self.assertEqual(reentrega["total"], 0)
        self.assertFalse(reentrega["evento_novo"])

    def test_memoria_bloqueia_quinze_wamids_distintos(self):
        resultado = None

        for indice in range(15):
            resultado = self.avaliar(
                f"wamid.{indice}"
            )

        self.assertEqual(resultado["total"], 15)
        self.assertTrue(resultado["flood"])

    def test_memoria_wamid_expirado_volta_a_contar(self):
        primeiro = self.avaliar("wamid.unico")
        self.agora += (
            cache_flood_memoria
            .DEDUPLICACAO_TTL_SEGUNDOS
            + 1
        )
        depois_do_ttl = self.avaliar("wamid.unico")

        self.assertTrue(primeiro["evento_novo"])
        self.assertTrue(depois_do_ttl["evento_novo"])
        self.assertEqual(depois_do_ttl["total"], 1)

    def test_memoria_limita_wamids_por_par(self):
        with patch.object(
            cache_flood_memoria,
            "MAX_WAMIDS_POR_PAR_MEMORIA",
            3,
        ):
            for indice in range(5):
                self.avaliar(f"wamid.{indice}")

        chave = cache_flood_memoria._cache_key(
            "cliente-a",
            "phone-a",
        )
        eventos = (
            cache_flood_memoria
            ._eventos_por_chave[chave]
        )
        self.assertEqual(len(eventos), 3)
        self.assertNotIn(
            cache_flood_memoria._digest_wamid(
                "wamid.0"
            ),
            eventos,
        )

    def test_memoria_limita_pares_antes_de_retorno_flood(
        self,
    ):
        regra_flood_imediato = (
            {
                "nome": "teste",
                "limite": 1,
                "janela_segundos": 5,
            },
        )

        with patch.object(
            cache_flood_memoria,
            "MAX_CHAVES_MEMORIA",
            1,
        ):
            cache_flood_memoria.avaliar_flood_memoria(
                "cliente-a",
                "phone-a",
                "wamid.a",
                regra_flood_imediato,
            )
            resultado = (
                cache_flood_memoria
                .avaliar_flood_memoria(
                    "cliente-b",
                    "phone-b",
                    "wamid.b",
                    regra_flood_imediato,
                )
            )

        self.assertTrue(resultado["flood"])
        self.assertEqual(
            len(
                cache_flood_memoria
                ._eventos_por_chave
            ),
            1,
        )
        self.assertIn(
            cache_flood_memoria._cache_key(
                "cliente-b",
                "phone-b",
            ),
            cache_flood_memoria._eventos_por_chave,
        )


class FloodGuardPropagacaoWamidTests(unittest.TestCase):
    def test_repassa_wamid_ao_redis(self):
        with patch.object(
            flood_guard,
            "avaliar_flood_redis",
            return_value={
                "redis_ok": True,
                "flood": False,
                "total": 1,
                "regra": None,
            },
        ) as avaliar_redis:
            resultado = flood_guard.bloquear_cliente_se_flood(
                "cliente-a",
                "phone-a",
                "wamid.1",
            )

        self.assertFalse(resultado["bloqueado"])
        avaliar_redis.assert_called_once_with(
            "cliente-a",
            "phone-a",
            "wamid.1",
            regras=flood_guard.REGRAS_FLOOD,
        )

    def test_repassa_wamid_ao_fallback_de_memoria(self):
        with patch.object(
            flood_guard,
            "avaliar_flood_redis",
            return_value={
                "redis_ok": False,
                "flood": False,
                "total": 0,
                "regra": None,
            },
        ), patch.object(
            flood_guard,
            "_avaliar_flood_banco",
            return_value={
                "banco_ok": False,
                "flood": False,
                "total": 0,
                "regra": None,
                "motivo": "banco_indisponivel",
            },
        ), patch.object(
            flood_guard,
            "avaliar_flood_memoria",
            return_value={
                "memoria_ok": True,
                "flood": False,
                "total": 1,
                "regra": None,
                "motivo": "memoria",
            },
        ) as avaliar_memoria:
            resultado = flood_guard.bloquear_cliente_se_flood(
                "cliente-a",
                "phone-a",
                "wamid.1",
            )

        self.assertFalse(resultado["bloqueado"])
        avaliar_memoria.assert_called_once_with(
            "cliente-a",
            "phone-a",
            "wamid.1",
            regras=flood_guard.REGRAS_FLOOD,
        )


if __name__ == "__main__":
    unittest.main()
