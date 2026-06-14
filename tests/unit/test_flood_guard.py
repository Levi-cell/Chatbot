import unittest
from unittest.mock import patch

from callback.webhook.services import flood_guard


class FloodGuardTests(unittest.TestCase):
    def test_dados_invalidos_nao_bloqueiam(self):
        resultado = flood_guard.bloquear_cliente_se_flood(None, "123456", "wamid")

        self.assertFalse(resultado["bloqueado"])
        self.assertEqual(resultado["motivo"], "dados_invalidos")

    def test_redis_abaixo_limite_nao_usa_banco(self):
        def banco_nao_deveria_ser_usado(*_args, **_kwargs):
            raise AssertionError("banco nao deveria ser usado")

        with patch.object(
            flood_guard,
            "avaliar_flood_redis",
            return_value={
                "redis_ok": True,
                "flood": False,
                "total": 3,
                "regra": None,
            },
        ), patch.object(
            flood_guard,
            "_avaliar_flood_banco",
            banco_nao_deveria_ser_usado,
        ):
            resultado = flood_guard.bloquear_cliente_se_flood(
                "5571999999999",
                "123456",
                "wamid",
            )

        self.assertFalse(resultado["bloqueado"])
        self.assertEqual(resultado["motivo"], "abaixo_limite_redis")

    def test_redis_detecta_flood_e_bloqueia(self):
        chamadas = []

        def fake_bloquear(wa, phone, origem, total, regra):
            chamadas.append((wa, phone, origem, total, regra))
            return {
                "bloqueado": True,
                "motivo": "flood_redis",
                "total": total,
                "regra": regra,
                "meta_ok": True,
            }

        with patch.object(
            flood_guard,
            "avaliar_flood_redis",
            return_value={
                "redis_ok": True,
                "flood": True,
                "total": 15,
                "regra": "rajada_curta",
            },
        ), patch.object(flood_guard, "_bloquear_e_registrar", fake_bloquear):
            resultado = flood_guard.bloquear_cliente_se_flood(
                "5571999999999",
                "123456",
                "wamid",
            )

        self.assertTrue(resultado["bloqueado"])
        self.assertEqual(
            chamadas,
            [("5571999999999", "123456", "redis", 15, "rajada_curta")],
        )

    def test_redis_e_banco_falham_memoria_detecta(self):
        with patch.object(
            flood_guard,
            "avaliar_flood_redis",
            return_value={"redis_ok": False, "flood": False, "total": 0, "regra": None},
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
            return_value={"flood": True, "total": 15, "regra": "rajada_curta"},
        ), patch.object(
            flood_guard,
            "_bloquear_via_memoria_e_alertar",
            return_value={
                "bloqueado": True,
                "motivo": "flood_memoria",
                "total": 15,
                "regra": "rajada_curta",
                "meta_ok": True,
            },
        ):
            resultado = flood_guard.bloquear_cliente_se_flood(
                "5571999999999",
                "123456",
                "wamid",
            )

        self.assertTrue(resultado["bloqueado"])
        self.assertEqual(resultado["motivo"], "flood_memoria")

    def test_meta_falha_nao_registra_banco(self):
        def banco_nao_deveria_registrar(*_args, **_kwargs):
            raise AssertionError("nao deve registrar banco se Meta falhar")

        with patch.object(
            flood_guard,
            "_buscar_dados_bloqueio",
            return_value={
                "id_cliente": 1,
                "id_unidade": 2,
                "phone_id_unidade": "123456",
                "motivo": "ok",
            },
        ), patch.object(
            flood_guard,
            "bloquear_usuario_meta",
            side_effect=RuntimeError("meta caiu"),
        ), patch.object(
            flood_guard,
            "_registrar_bloqueio_banco_apos_meta",
            banco_nao_deveria_registrar,
        ):
            resultado = flood_guard._bloquear_e_registrar(
                "5571999999999",
                "123456",
                origem="redis",
                total=15,
                regra="rajada_curta",
            )

        self.assertTrue(resultado["bloqueado"])
        self.assertFalse(resultado["meta_ok"])
        self.assertEqual(resultado["motivo"], "flood_redis_meta_falhou")


if __name__ == "__main__":
    unittest.main()
