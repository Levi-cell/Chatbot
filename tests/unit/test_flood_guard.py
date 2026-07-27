import unittest
from unittest.mock import MagicMock, patch

from callback.webhook.services import flood_guard
from core.repositories.seguranca import bloqueio_meta
from tests.payloads import payload_texto_meta


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

        def fake_bloquear(
            wa,
            phone,
            origem,
            total,
            regra,
            nome_cliente=None,
        ):
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

    def test_flood_sem_persistencia_local_retorna_503(self):
        payload = payload_texto_meta()

        with patch.object(
            flood_guard,
            "bloquear_cliente_se_flood",
            return_value={
                "bloqueado": True,
                "motivo": "flood_redis_persistencia_local_falhou",
                "total": 15,
                "regra": "rajada_curta",
                "persistencia_ok": False,
                "meta_ok": None,
                "reentregar": True,
            },
        ):
            resposta = flood_guard.responder_se_flood(payload)

        self.assertEqual(resposta.status_code, 503)

    def test_payload_repassa_nome_do_perfil_para_avaliacao_de_flood(self):
        with patch.object(
            flood_guard,
            "bloquear_cliente_se_flood",
            return_value={
                "bloqueado": False,
                "motivo": "abaixo_limite_redis",
                "total": 1,
                "regra": None,
                "meta_ok": None,
            },
        ) as avaliar_flood:
            resposta = flood_guard.responder_se_flood(
                payload_texto_meta()
            )

        self.assertIsNone(resposta)
        avaliar_flood.assert_called_once_with(
            "5571999999999",
            "123456",
            "wamid.test.1",
            nome_cliente="Cliente Teste",
        )

    def test_profile_nulo_nao_interrompe_avaliacao_de_flood(self):
        payload = payload_texto_meta()
        payload["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"] = None

        with patch.object(
            flood_guard,
            "bloquear_cliente_se_flood",
            return_value={
                "bloqueado": False,
                "motivo": "abaixo_limite_redis",
                "total": 1,
                "regra": None,
                "meta_ok": None,
            },
        ) as avaliar_flood:
            resposta = flood_guard.responder_se_flood(payload)

        self.assertIsNone(resposta)
        avaliar_flood.assert_called_once_with(
            "5571999999999",
            "123456",
            "wamid.test.1",
            nome_cliente=None,
        )

    def test_nome_cliente_e_normalizado_e_limitado_a_200_caracteres(self):
        payload = payload_texto_meta()
        payload["entry"][0]["changes"][0]["value"]["contacts"][0]["profile"] = {
            "name": f"  {'A' * 250}  ",
        }

        self.assertEqual(
            flood_guard._extrair_nome_cliente(payload),
            "A" * 200,
        )

    def test_nome_consolidado_no_banco_tem_preferencia_sobre_perfil(self):
        conexao = MagicMock()

        with patch.object(
            flood_guard,
            "get_conn",
            return_value=conexao,
        ), patch.object(
            flood_guard,
            "buscar_cliente_por_wa_id",
            return_value=(1, "Nome do Banco"),
        ), patch.object(
            flood_guard,
            "buscar_unidade_bloqueio_por_phone_id",
            return_value=(2, "123456"),
        ):
            resultado = flood_guard._buscar_dados_bloqueio(
                "5571999999999",
                "123456",
                nome_cliente="Nome do Perfil",
            )

        self.assertEqual(resultado["nome_cliente"], "Nome do Banco")
        conexao.close.assert_called_once_with()

    def test_upsert_bloqueio_inclui_nome_na_ordem_correta(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (10,)

        resultado = bloqueio_meta.registrar_cliente_bloqueado_meta_banco(
            1,
            "5571999999999",
            2,
            "123456",
            cursor,
            nome_cliente="Cliente Teste",
        )

        self.assertEqual(resultado, 10)
        parametros = cursor.execute.call_args.args[1]
        self.assertEqual(
            parametros,
            (1, "Cliente Teste", "5571999999999", 2, "123456"),
        )

    def test_meta_sucesso_registra_nome_cliente_no_banco(self):
        with patch.object(
            flood_guard,
            "_buscar_dados_bloqueio",
            return_value={
                "id_cliente": 1,
                "nome_cliente": "Cliente Teste",
                "id_unidade": 2,
                "phone_id_unidade": "123456",
                "motivo": "ok",
            },
        ), patch.object(
            flood_guard,
            "bloquear_usuario_meta",
        ), patch.object(
            flood_guard,
            "_registrar_intencao_bloqueio_banco",
            return_value=10,
        ) as registrar:
            resultado = flood_guard._bloquear_e_registrar(
                "5571999999999",
                "123456",
                origem="redis",
                total=15,
                regra="rajada_curta",
                nome_cliente="Cliente Teste",
            )

        self.assertTrue(resultado["bloqueado"])
        self.assertTrue(resultado["meta_ok"])
        self.assertEqual(resultado["id_bloqueio"], 10)
        registrar.assert_called_once_with(
            1,
            "Cliente Teste",
            "5571999999999",
            2,
            "123456",
        )

    def test_meta_falha_mantem_registro_local_para_retentativa(self):
        with patch.object(
            flood_guard,
            "_buscar_dados_bloqueio",
            return_value={
                "id_cliente": 1,
                "nome_cliente": "Cliente Teste",
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
            "_registrar_intencao_bloqueio_banco",
            return_value=10,
        ) as registrar:
            resultado = flood_guard._bloquear_e_registrar(
                "5571999999999",
                "123456",
                origem="redis",
                total=15,
                regra="rajada_curta",
            )

        self.assertTrue(resultado["bloqueado"])
        self.assertFalse(resultado["meta_ok"])
        self.assertEqual(resultado["id_bloqueio"], 10)
        self.assertEqual(resultado["motivo"], "flood_redis_meta_falhou")
        registrar.assert_called_once_with(
            1,
            "Cliente Teste",
            "5571999999999",
            2,
            "123456",
        )

    def test_falha_persistencia_local_nao_chama_meta_e_pede_reentrega(self):
        with patch.object(
            flood_guard,
            "_buscar_dados_bloqueio",
            return_value={
                "id_cliente": 1,
                "nome_cliente": "Cliente Teste",
                "id_unidade": 2,
                "phone_id_unidade": "123456",
                "motivo": "ok",
            },
        ), patch.object(
            flood_guard,
            "_registrar_intencao_bloqueio_banco",
            return_value=None,
        ), patch.object(
            flood_guard,
            "bloquear_usuario_meta",
        ) as bloquear_meta:
            resultado = flood_guard._bloquear_e_registrar(
                "5571999999999",
                "123456",
                origem="redis",
                total=15,
                regra="rajada_curta",
                nome_cliente="Cliente Teste",
            )

        self.assertTrue(resultado["bloqueado"])
        self.assertFalse(resultado["persistencia_ok"])
        self.assertTrue(resultado["reentregar"])
        self.assertIsNone(resultado["meta_ok"])
        bloquear_meta.assert_not_called()

    def test_fallback_memoria_reutiliza_bloqueio_persistente_e_nome(self):
        resultado_bloqueio = {
            "bloqueado": True,
            "motivo": "flood_memoria_meta_falhou",
            "total": 15,
            "regra": "rajada_curta",
            "id_bloqueio": 10,
            "id_cliente": 1,
            "id_unidade": 2,
            "persistencia_ok": True,
            "meta_ok": False,
            "erro_meta": "conta business",
            "reentregar": False,
        }

        with patch.object(
            flood_guard,
            "_bloquear_e_registrar",
            return_value=resultado_bloqueio,
        ) as bloquear, patch.object(
            flood_guard,
            "registrar_alerta_flood_memoria",
        ) as alertar:
            resultado = flood_guard._bloquear_via_memoria_e_alertar(
                "5571999999999",
                "123456",
                total=15,
                regra="rajada_curta",
                id_hash_msg="wamid.test.1",
                nome_cliente="Cliente Teste",
            )

        self.assertEqual(resultado, resultado_bloqueio)
        bloquear.assert_called_once_with(
            "5571999999999",
            "123456",
            origem="memoria",
            total=15,
            regra="rajada_curta",
            nome_cliente="Cliente Teste",
        )
        alertar.assert_called_once()

    def test_registro_local_acontece_antes_da_tentativa_meta(self):
        ordem = []

        with patch.object(
            flood_guard,
            "_buscar_dados_bloqueio",
            return_value={
                "id_cliente": 1,
                "nome_cliente": "Cliente Teste",
                "id_unidade": 2,
                "phone_id_unidade": "123456",
                "motivo": "ok",
            },
        ), patch.object(
            flood_guard,
            "_registrar_intencao_bloqueio_banco",
            side_effect=lambda *_args: ordem.append("banco") or 10,
        ), patch.object(
            flood_guard,
            "bloquear_usuario_meta",
            side_effect=lambda *_args: ordem.append("meta"),
        ):
            flood_guard._bloquear_e_registrar(
                "5571999999999",
                "123456",
                origem="redis",
                total=15,
                regra="rajada_curta",
                nome_cliente="Cliente Teste",
            )

        self.assertEqual(ordem, ["banco", "meta"])

    def test_lookup_unidade_para_bloqueio_nao_depende_de_pagamento(self):
        cursor = MagicMock()
        cursor.fetchone.return_value = (2, "123456")

        resultado = bloqueio_meta.buscar_unidade_bloqueio_por_phone_id(
            "123456",
            cursor,
        )

        self.assertEqual(resultado, (2, "123456"))
        sql = cursor.execute.call_args.args[0]
        self.assertNotIn("status_pagamento", sql)


if __name__ == "__main__":
    unittest.main()
