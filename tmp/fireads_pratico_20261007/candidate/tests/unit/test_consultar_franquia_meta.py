import io
import json
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from utilitarios.consultas_franquia.consultar_franquia_meta import (
    consultar_faturas,
    consultar_faturas_meta,
    consultar_franquia,
    consultar_franquia_meta,
    main,
)


PHONE_A = {"id": "111", "display_phone_number": "+55 11 99999-1111", "verified_name": "Teste A"}
PHONE_B = {"id": "222", "display_phone_number": "+55 11 99999-2222", "verified_name": "Teste B"}
AGORA = datetime(2026, 10, 15, 12, tzinfo=timezone.utc)


def resposta(dados, status=200):
    retorno = Mock(status_code=status)
    retorno.json.return_value = dados
    return retorno


def metricas(telefone="5511999991111", gratuito=734, anuncio=2000, pago=0):
    return {"pricing_analytics": {"data": [{"data_points": [
        {"phone_number": telefone, "pricing_category": "SERVICE", "pricing_type": tipo, "volume": volume}
        for tipo, volume in (
            ("FREE_CUSTOMER_SERVICE", gratuito),
            ("FREE_ENTRY_POINT", anuncio),
            ("REGULAR", pago),
        )
    ]}]}}


class ConsultarFranquiaMetaTestCase(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(
            construir_url_graph_api=lambda caminho: f"https://graph.facebook.com/v26.0/{caminho}",
            get_meta_http_timeout=lambda: (1, 2),
            get_token_usuario_meta=lambda: "token_ficticio_nunca_imprimir",
        )
        self.config = patch.dict(
            "sys.modules", {"core.integrations.whatsapp.tools.config": config}
        )
        self.config.start()
        self.addCleanup(self.config.stop)
        self.session = Mock()

    def consultar(self, **kwargs):
        args = {"fuso_horario": "America/Sao_Paulo", "agora": AGORA, "session": self.session}
        args.update(kwargs)
        return consultar_franquia_meta("999", **args)

    def preparar(self, dados=None):
        self.session.get.side_effect = [
            resposta({"id": "999", "timezone_id": "25"}),
            resposta({"data": [PHONE_A]}),
            resposta(metricas() if dados is None else dados),
        ]

    def test_anuncios_nao_consumem_franquia_e_consulta_so_faz_get(self):
        self.preparar()
        resultado = self.consultar(phone_number_id="111")
        numero = resultado["numeros"][0]
        self.assertEqual(numero["consumidas_na_franquia"], 734)
        self.assertEqual(numero["restantes_estimadas"], 266)
        self.assertEqual(numero["volumes_por_tipo"]["FREE_ENTRY_POINT"], 2000)
        self.assertTrue(all(c[0] == "get" for c in self.session.method_calls))
        chamada = self.session.get.call_args
        self.assertEqual(chamada.args[0], "https://graph.facebook.com/v26.0/999")
        fields = chamada.kwargs["params"]["fields"]
        self.assertIn('.phone_numbers(["5511999991111"])', fields)
        self.assertIn(".pricing_categories(SERVICE)", fields)
        self.assertNotIn("access_token", chamada.kwargs["params"])
        self.assertFalse(chamada.kwargs["allow_redirects"])

    def test_waba_com_dois_numeros_preserva_franquias_independentes(self):
        self.session.get.side_effect = [
            resposta({"id": "999", "timezone_id": "25"}),
            resposta({"data": [PHONE_A, PHONE_B]}),
            resposta(metricas()),
            resposta(metricas("5511999992222", gratuito=1000, pago=30)),
        ]
        numeros = self.consultar()["numeros"]
        self.assertEqual([n["restantes_estimadas"] for n in numeros], [266, 0])
        self.assertEqual(numeros[1]["volumes_por_tipo"]["REGULAR"], 30)

    def test_setembro_nao_aplica_nova_franquia_a_metricas_antigas(self):
        self.preparar(metricas(gratuito=2500))
        resultado = self.consultar(mes="2026-09")
        self.assertFalse(resultado["franquia_vigente_no_periodo"])
        numero = resultado["numeros"][0]
        self.assertIsNone(numero["restantes_estimadas"])
        self.assertIsNone(numero["consumidas_na_franquia"])
        self.assertIsNone(numero["franquia_mensal"])
        self.assertEqual(resultado["fim_exclusivo"], "2026-10-01T00:00:00-03:00")

    def test_mes_atual_consulta_desde_dia_um_no_fuso_escolhido(self):
        self.preparar()
        resultado = self.consultar()
        self.assertEqual(resultado["inicio_inclusivo"], "2026-10-01T00:00:00-03:00")
        self.assertEqual(resultado["fim_exclusivo"], "2026-10-15T09:00:00-03:00")

    def test_virada_de_ano_respeita_fim_exclusivo(self):
        self.preparar()
        resultado = self.consultar(mes="2026-12", agora=datetime(2027, 1, 2, tzinfo=timezone.utc))
        self.assertEqual(resultado["fim_exclusivo"], "2027-01-01T00:00:00-03:00")

    def test_volume_acima_da_franquia_nao_gera_saldo_negativo(self):
        self.preparar(metricas(gratuito=1001))
        self.assertEqual(self.consultar()["numeros"][0]["restantes_estimadas"], 0)

    def test_ausencia_de_dados_e_falha_da_api_nao_sao_a_mesma_coisa(self):
        self.preparar({"pricing_analytics": {"data": []}})
        self.assertEqual(self.consultar()["numeros"][0]["restantes_estimadas"], 1000)
        for dados in ({}, {"pricing_analytics": {}}, {"pricing_analytics": {"data": [{}]}}):
            with self.subTest(dados=dados):
                self.preparar(dados)
                with self.assertRaises(RuntimeError):
                    self.consultar()

    def test_numero_precisa_pertencer_a_waba(self):
        self.preparar()
        with self.assertRaisesRegex(ValueError, "não pertence"):
            self.consultar(phone_number_id="333")
        self.assertEqual(self.session.get.call_count, 2)

    def test_paginacao_de_numeros_usa_cursor_no_endpoint_original(self):
        self.session.get.side_effect = [
            resposta({"id": "999", "timezone_id": "25"}),
            resposta({"data": [PHONE_A], "paging": {
                "next": "https://outro.example/?access_token=NAO_SEGUIR",
                "cursors": {"after": "cursor-segunda-pagina"},
            }}),
            resposta({"data": [PHONE_B]}),
            resposta(metricas("5511999992222", gratuito=12)),
        ]
        resultado = self.consultar(phone_number_id="222")
        self.assertEqual(resultado["numeros"][0]["restantes_estimadas"], 988)
        chamada = self.session.get.call_args_list[2]
        self.assertEqual(chamada.args[0], "https://graph.facebook.com/v26.0/999/phone_numbers")
        self.assertEqual(chamada.kwargs["params"]["after"], "cursor-segunda-pagina")

    def test_recusa_saldo_parcial_se_metricas_vierem_paginadas(self):
        dados = metricas()
        dados["pricing_analytics"]["paging"] = {"next": "https://graph.facebook.com/proxima"}
        self.preparar(dados)
        with self.assertRaisesRegex(RuntimeError, "saldo parcial"):
            self.consultar()

    def test_recusa_metricas_de_outro_numero(self):
        self.preparar(metricas("5511999992222"))
        with self.assertRaisesRegex(RuntimeError, "outro telefone"):
            self.consultar()

    def test_recusa_volume_ausente_ou_invalido(self):
        for volume in (None, -1, True, "734"):
            with self.subTest(volume=volume):
                self.preparar(metricas(gratuito=volume))
                with self.assertRaises(RuntimeError):
                    self.consultar()

    def test_erro_de_permissao_nao_expoe_token_nem_retorna_saldo(self):
        self.session.get.return_value = resposta({"error": {
            "code": 190, "message": "token_ficticio_nunca_imprimir",
        }}, status=400)
        with self.assertRaises(RuntimeError) as erro:
            self.consultar()
        self.assertIn("190", str(erro.exception))
        self.assertNotIn("token_ficticio", str(erro.exception))

    def test_timeout_nao_vira_franquia_disponivel(self):
        self.session.get.side_effect = requests.Timeout("URL com token fictício")
        with self.assertRaisesRegex(RuntimeError, "Falha de conexão"):
            self.consultar()

    def test_parametros_invalidos_falham_antes_da_api(self):
        for kwargs in (
            {"phone_number_id": "111/../222"},
            {"mes": "2026-11"},
            {"mes": "2026-13"},
            {"mes": "outubro"},
            {"fuso_horario": "inexistente"},
            {"agora": datetime(2026, 10, 15)},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                self.consultar(**kwargs)
        self.session.get.assert_not_called()

    def test_faturas_paginadas_preservam_moedas_sem_seguir_url_da_resposta(self):
        primeira = {
            "id": "10101", "invoice_id": "INV-2026-09",
            "amount": "12.34", "currency": "USD", "billing_period": "2026-09",
            "ad_account_ids": ["123456789"],
            "download_uri": "https://nao-seguir.example/?access_token=segredo",
        }
        segunda = {"id": "20202", "amount": "56.78", "currency": "BRL"}
        self.session.get.side_effect = [
            resposta({"data": [primeira], "paging": {
                "next": "https://nao-seguir.example/?access_token=segredo",
                "cursors": {"after": "proxima-pagina"},
            }}),
            resposta({"data": [primeira, segunda]}),
        ]
        resultado = consultar_faturas_meta("999", session=self.session)
        self.assertEqual(resultado["quantidade_faturas"], 2)
        self.assertEqual(resultado["quantidade_faturas_com_contas_anuncio"], 1)
        self.assertEqual(resultado["faturas"][0]["ad_account_ids"], ["123456789"])
        self.assertEqual(resultado["faturas"][1]["ad_account_ids"], [])
        self.assertEqual(
            [(f["amount"], f["currency"]) for f in resultado["faturas"]],
            [("12.34", "USD"), ("56.78", "BRL")],
        )
        self.assertNotIn("download_uri", resultado["faturas"][0])
        chamadas = self.session.get.call_args_list
        self.assertEqual(chamadas[1].kwargs["params"]["after"], "proxima-pagina")
        self.assertNotIn("after", chamadas[0].kwargs["params"])
        self.assertEqual(
            chamadas[0].kwargs["params"]["issue_start_date"],
            chamadas[1].kwargs["params"]["issue_start_date"],
        )
        self.assertTrue(all(
            c.args[0] == "https://graph.facebook.com/v26.0/999/business_invoices"
            for c in chamadas
        ))
        self.assertTrue(all(c[0] == "get" for c in self.session.method_calls))

    def test_faturas_vazias_nao_sao_apresentadas_como_ausencia_de_cobrancas(self):
        self.session.get.return_value = resposta({"data": []})
        resultado = consultar_faturas_meta("999", session=self.session)
        self.assertEqual(resultado["faturas"], [])
        self.assertEqual(resultado["status_consulta"], "sem_faturas_retornadas")
        self.assertTrue(any("não significa ausência de cobranças" in a for a in resultado["avisos"]))

    def test_faturas_quatro_meses_por_emissao_incluem_o_dia_atual(self):
        self.session.get.return_value = resposta({"data": []})
        resultado = consultar_faturas_meta(
            "999", meses=4, session=self.session,
            agora=datetime(2026, 9, 28, 18, tzinfo=timezone.utc),
        )
        periodo = resultado["periodo"]
        self.assertEqual(periodo["inicio_inclusivo"], "2026-06-01")
        self.assertEqual(periodo["fim_exclusivo"], "2026-09-29")
        params = self.session.get.call_args.kwargs["params"]
        self.assertEqual(params["issue_start_date"], "2026-06-01")
        self.assertEqual(params["issue_end_date"], "2026-09-29")
        self.assertIn("ad_account_ids", params["fields"].split(","))
        self.assertNotIn("start_date", params)
        self.assertNotIn("end_date", params)

    def test_faturas_virada_de_ano_e_data_local(self):
        self.session.get.return_value = resposta({"data": []})
        for instante, inicio, fim in (
            (datetime(2027, 1, 1, 2, tzinfo=timezone.utc), "2026-09-01", "2027-01-01"),
            (datetime(2027, 1, 1, 4, tzinfo=timezone.utc), "2026-10-01", "2027-01-02"),
        ):
            with self.subTest(instante=instante):
                resultado = consultar_faturas_meta("999", session=self.session, agora=instante)
                self.assertEqual(resultado["periodo"]["inicio_inclusivo"], inicio)
                self.assertEqual(resultado["periodo"]["fim_exclusivo"], fim)

    def test_faturas_recusam_periodo_invalido_antes_da_api(self):
        for parametros in (
            {"meses": 0}, {"meses": True}, {"meses": "4"}, {"meses": -1},
            {"meses": 999999}, {"fuso_horario": "inexistente"},
            {"agora": datetime(2026, 9, 28)},
        ):
            with self.subTest(parametros=parametros), self.assertRaises(ValueError):
                consultar_faturas_meta("999", session=self.session, **parametros)
        self.session.get.assert_not_called()

    def test_faturas_erro_de_permissao_nao_vira_zero(self):
        self.session.get.return_value = resposta({"error": {
            "code": 200, "message": "token_ficticio_nunca_imprimir",
        }}, 403)
        with self.assertRaisesRegex(RuntimeError, "HTTP 403, código Meta 200"):
            consultar_faturas_meta("999", session=self.session)

    def test_faturas_recusam_resposta_incompleta_e_cursor_repetido(self):
        for dados in ({}, {"data": {}}, {"data": [{}]}, {
            "data": [], "paging": {"next": "https://nao-seguir.example/"},
        }, {
            "data": [{"id": "123"}], "paging": {
                "next": "https://nao-seguir.example/", "cursors": {"after": "repetido"},
            },
        }):
            with self.subTest(dados=dados):
                self.session.get.return_value = resposta(dados)
                with self.assertRaises(RuntimeError):
                    consultar_faturas_meta("999", session=self.session)

    def test_falha_na_segunda_pagina_nao_retorna_faturas_parciais(self):
        self.session.get.side_effect = [
            resposta({"data": [{"id": "123"}], "paging": {
                "next": "https://nao-seguir.example/", "cursors": {"after": "pagina-2"},
            }}),
            resposta({"error": {"code": 10, "message": "token_ficticio_nunca_imprimir"}}, 403),
        ]
        with self.assertRaisesRegex(RuntimeError, "HTTP 403, código Meta 10") as erro:
            consultar_faturas_meta("999", session=self.session)
        self.assertNotIn("token_ficticio", str(erro.exception))

    def test_atalho_ide_configura_ambiente_imprime_e_preserva_retorno(self):
        dados = {"waba_id": "123456", "numeros": [{
            "phone_number_id": "987654", "telefone": "5511999991111",
        }]}
        saida = io.StringIO()
        with patch("utilitarios.bootstrap.configurar_ambiente_utilitario") as ambiente, patch(
            "utilitarios.consultas_franquia.consultar_franquia_meta.consultar_franquia_meta", return_value=dados
        ) as consulta, redirect_stdout(saida):
            resultado = consultar_franquia("123456", "987654", mes="2026-09")
        ambiente.assert_called_once_with(None)
        consulta.assert_called_once_with(
            "123456", phone_number_id="987654", fuso_horario=None, mes="2026-09",
        )
        self.assertIs(resultado, dados)
        self.assertEqual(resultado["numeros"][0]["telefone"], "5511999991111")
        self.assertEqual(json.loads(saida.getvalue())["numeros"][0]["telefone"], "...1111")

    def test_atalho_faturas_recebe_id_portfolio_e_cli_anterior_continua_valido(self):
        saida = io.StringIO()
        with patch("utilitarios.bootstrap.configurar_ambiente_utilitario") as ambiente, patch(
            "utilitarios.consultas_franquia.consultar_franquia_meta.consultar_faturas_meta",
            return_value={"id_portfolio": "987654", "faturas": [
                {"id": "123456", "ad_account_ids": ["123456789"]},
            ]},
        ) as consulta, redirect_stdout(saida):
            resultado = consultar_faturas("987654", env_file="ambiente.env")
        ambiente.assert_called_once_with("ambiente.env")
        consulta.assert_called_once_with("987654", meses=4, fuso_horario="America/Sao_Paulo")
        self.assertEqual(resultado["id_portfolio"], "987654")
        self.assertEqual(json.loads(saida.getvalue())["id_portfolio"], "...7654")
        self.assertEqual(
            json.loads(saida.getvalue())["faturas"][0]["ad_account_ids"], ["...6789"],
        )
        self.assertEqual(resultado["faturas"][0]["ad_account_ids"], ["123456789"])
        with patch("utilitarios.consultas_franquia.consultar_franquia_meta.consultar_franquia") as atalho:
            self.assertEqual(main([
                "--waba-id", "999", "--fuso-horario", "UTC", "--env-file", "ambiente.env",
            ]), 0)
        atalho.assert_called_once_with(
            "999", None, fuso_horario="UTC", mes=None, env_file="ambiente.env",
            mostrar_identificadores=False,
        )

    def test_exemplo_3750_entregas_e_250_restantes_sem_bootstrap_ou_impressao(self):
        self.preparar(metricas(gratuito=750, anuncio=3000, pago=0))
        saida = io.StringIO()
        with patch("utilitarios.bootstrap.configurar_ambiente_utilitario") as ambiente, redirect_stdout(saida):
            resultado = self.consultar(phone_number_id="111")
        numero = resultado["numeros"][0]
        self.assertEqual(numero["total_mensagens"], 3750)
        self.assertEqual(numero["restantes_estimadas"], 250)
        self.assertEqual(numero["mensagens_cobradas_meta"], 0)
        self.assertEqual(numero["mensagens_assumidas_esl"], 0)
        self.assertEqual(numero["mensagens_excedentes_unidade"], 0)
        ambiente.assert_not_called()
        self.assertEqual(saida.getvalue(), "")

    def test_cobradas_esl_e_unidade_nao_duplicam_o_total(self):
        self.preparar(metricas(gratuito=1000, anuncio=3000, pago=1300))
        numero = self.consultar()["numeros"][0]
        self.assertEqual(numero["total_mensagens"], 5300)
        self.assertEqual(numero["restantes_estimadas"], 0)
        self.assertEqual(numero["mensagens_assumidas_esl"], 1000)
        self.assertEqual(numero["mensagens_excedentes_unidade"], 300)

    def test_periodo_do_banco_fica_fixo_e_recorte_da_consulta_avanca(self):
        self.preparar()
        resultado = self.consultar()
        self.assertEqual(resultado["data_hora_inicio"], "2026-10-01T00:00:00-03:00")
        self.assertEqual(resultado["data_hora_fim"], "2026-11-01T00:00:00-03:00")
        self.assertEqual(resultado["fim_exclusivo"], "2026-10-15T09:00:00-03:00")
        self.assertTrue(resultado["mes_em_andamento"])
        self.preparar()
        anterior = self.consultar(mes="2026-09")
        self.assertEqual(anterior["data_hora_fim"], anterior["fim_exclusivo"])
        self.assertFalse(anterior["mes_em_andamento"])

    def test_fuso_bahia_automatico_consultado_na_waba(self):
        self.session.get.side_effect = [
            resposta({"id": "999", "timezone_id": "206"}),
            resposta({"data": [PHONE_A]}), resposta(metricas()),
        ]
        resultado = self.consultar(fuso_horario=None)
        self.assertEqual(resultado["fuso_horario"], "America/Bahia")
        self.assertEqual(resultado["timezone_id"], "206")
        self.assertEqual(self.session.get.call_args_list[0].kwargs["params"], {"fields": "id,timezone_id"})

    def test_fuso_desconhecido_ou_outra_waba_nao_vira_fuso_do_servidor(self):
        for dados in (
            {"id": "999", "timezone_id": 0}, {"id": "999"},
            {"id": "999", "timezone_id": "99999"}, {"id": "123", "timezone_id": "25"},
        ):
            with self.subTest(dados=dados), self.assertRaises(RuntimeError):
                self.session.get.return_value = resposta(dados)
                self.consultar(fuso_horario=None)

    def test_fuso_manual_divergente_nao_sobrescreve_configuracao_meta(self):
        self.session.get.return_value = resposta({"id": "999", "timezone_id": "270"})
        with self.assertRaisesRegex(ValueError, "diverge da WABA"):
            self.consultar(fuso_horario="America/Sao_Paulo")
        self.assertEqual(self.session.get.call_count, 1)

    def test_porto_velho_ainda_esta_em_setembro_quando_brasilia_virou_outubro(self):
        self.session.get.side_effect = [
            resposta({"id": "999", "timezone_id": "270"}),
            resposta({"data": [PHONE_A]}), resposta(metricas()),
        ]
        resultado = self.consultar(
            fuso_horario=None, agora=datetime(2026, 10, 1, 3, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(resultado["mes"], "2026-09")
        self.assertEqual(resultado["data_hora_fim"], "2026-10-01T00:00:00-04:00")
        self.assertIsNone(resultado["numeros"][0]["mensagens_assumidas_esl"])

    def test_meia_noite_exata_nao_consulta_intervalo_vazio_como_sucesso(self):
        self.session.get.return_value = resposta({"id": "999", "timezone_id": "25"})
        with self.assertRaisesRegex(ValueError, "período consultável"):
            self.consultar(fuso_horario=None, agora=datetime(2026, 10, 1, 3, tzinfo=timezone.utc))
        self.assertEqual(self.session.get.call_count, 1)

    def test_cli_aceita_consulta_com_fuso_automatico(self):
        with patch("utilitarios.consultas_franquia.consultar_franquia_meta.consultar_franquia") as atalho:
            self.assertEqual(main(["--waba-id", "999", "--phone-number-id", "111"]), 0)
        self.assertIsNone(atalho.call_args.kwargs["fuso_horario"])

    def test_fim_reportado_coincide_com_segundo_inteiro_enviado_a_meta(self):
        self.preparar()
        instante = datetime(2026, 10, 15, 12, 0, 0, 123456, tzinfo=timezone.utc)
        resultado = self.consultar(agora=instante)
        fim = datetime.fromisoformat(resultado["fim_exclusivo"])
        self.assertEqual(fim.microsecond, 0)
        fields = self.session.get.call_args.kwargs["params"]["fields"]
        self.assertIn(f".end({int(fim.timestamp())})", fields)


if __name__ == "__main__":
    unittest.main()
