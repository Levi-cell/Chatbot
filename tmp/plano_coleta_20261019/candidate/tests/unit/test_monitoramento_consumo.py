"""Consumo: autorização real, contrato da apresentação e PDFs privados."""

import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.db import OperationalError

from monitoramento.consumo_services import apresentar_mes, carregar_consumo
from tests.fixtures.consumo_meta import instante, registro
from tests.unit import test_monitoramento_login as login_fixture


class ApresentacaoConsumoTests(unittest.TestCase):
    def carregar(self, registros, *, mes=None, fuso="America/Sao_Paulo", erro=None,
                 agora="2026-12-15T12:00:00"):
        with patch("monitoramento.consumo_services.connection"), patch(
            "monitoramento.consumo_services.repositorio.buscar_unidade",
            return_value={"nome_unidade":"Unidade A","nome_fuso":fuso,"erro_conta":erro}), patch(
            "monitoramento.consumo_services.repositorio.listar_meses", return_value=registros), patch(
            "monitoramento.consumo_services.repositorio.buscar_falha_periodo", return_value=None):
            return carregar_consumo(SimpleNamespace(id_unidade=10), mes, agora=instante(agora))

    def test_mes_atual_sem_dados_nao_reutiliza_mes_anterior(self):
        dados = self.carregar([registro()])
        self.assertIsNone(dados["selecionado"])
        self.assertEqual(dados["meses"][0], {"chave":"2026-12","rotulo":"Dez · 2026","atual":True})
        self.assertEqual(len(dados["historico"]), 1)

    def test_sem_fuso_calendario_inicial_nao_inventa_saldo(self):
        dados = self.carregar([], fuso=None)
        self.assertEqual(dados["mes_atual"], "2026-12")
        self.assertEqual([mes["chave"] for mes in dados["meses"]], ["2026-12"])
        self.assertIsNone(dados["selecionado"])
        self.assertNotIn("nome_fuso", dados["unidade"])

    def test_setembro_oferece_somente_outubro_com_aviso_e_sem_dados(self):
        for fuso in (None, "America/Bahia"):
            for mes in (None, "2026-10"):
                with self.subTest(fuso=fuso, mes=mes):
                    dados = self.carregar([registro()], fuso=fuso, mes=mes,
                                          agora="2026-09-29T12:00:00")
                    self.assertTrue(dados["pre_lancamento"])
                    self.assertEqual(dados["mes_selecionado"], "2026-10")
                    self.assertEqual(dados["meses"], [
                        {"chave": "2026-10", "rotulo": "Out · 2026", "atual": False},
                    ])
                    self.assertEqual(dados["aviso"], "Disponível apenas dia primeiro de outubro.")
                    self.assertIsNone(dados["selecionado"])
                    self.assertEqual(dados["historico"], [])

    def test_previa_nao_libera_setembro_nem_outros_meses_futuros(self):
        for mes in ("2026-09", "2026-11", "2027-10"):
            with self.subTest(mes=mes), self.assertRaises(ValueError):
                self.carregar([], mes=mes, fuso=None, agora="2026-09-29T12:00:00")

    def test_abertura_respeita_meia_noite_no_fuso_da_unidade(self):
        for fuso, horario_abertura in (("America/Bahia", "03:00:00"),
                                      ("America/Porto_Velho", "04:00:00")):
            with self.subTest(fuso=fuso):
                antes = self.carregar([], fuso=fuso, agora="2026-10-01T02:59:59")
                depois = self.carregar([], fuso=fuso, agora=f"2026-10-01T{horario_abertura}")
                self.assertTrue(antes["pre_lancamento"])
                self.assertFalse(depois["pre_lancamento"])
                self.assertEqual(depois["meses"][0]["chave"], "2026-10")
                self.assertTrue(depois["meses"][0]["atual"])
                self.assertIsNone(depois["selecionado"])
                self.assertIn("primeira coleta", depois["aviso"])

    def test_futuros_e_pre_vigencia_nao_entram_em_lista_historico_ou_pdf(self):
        base = registro()
        dados = self.carregar([
            base | {"mes_referencia": date(2027, 1, 1)},
            base | {"mes_referencia": date(2026, 9, 1)}, base,
        ])
        self.assertEqual([mes["chave"] for mes in dados["meses"]], ["2026-12", "2026-10"])
        self.assertEqual([mes["mes"] for mes in dados["historico"]], ["2026-10"])

    def test_sem_fuso_tambem_rejeita_mes_futuro(self):
        with self.assertRaises(ValueError):
            self.carregar([], mes="2027-01", fuso=None)

    def test_nao_cria_opcao_para_mes_historico_sem_registro_da_unidade(self):
        with self.assertRaises(ValueError):
            self.carregar([registro()], mes="2026-11")

    def test_historico_de_varios_anos_fica_completo_do_mais_recente_ao_antigo(self):
        registros = [registro(f"{ano}-{mes:02}")
                     for ano in range(2027, 2030) for mes in range(1, 13)]
        dados = self.carregar(registros + [registro()], agora="2030-01-15T12:00:00")
        chaves = [mes["chave"] for mes in dados["meses"]]
        self.assertEqual(len(chaves), 38)
        self.assertEqual(chaves, sorted(chaves, reverse=True))
        self.assertEqual((chaves[0], chaves[-1]), ("2030-01", "2026-10"))
        self.assertEqual(sum(mes["atual"] for mes in dados["meses"]), 1)

    def test_mes_futuro_e_pre_vigencia_sao_rejeitados(self):
        for mes in ("2026-09", "2027-01", "inválido"):
            with self.subTest(mes=mes), self.assertRaises(ValueError):
                self.carregar([],mes=mes)

    def test_coleta_mostra_horario_worker_sem_transformar_erro_em_zero(self):
        dados = self.carregar([registro()], mes="2026-10", erro="falha")
        self.assertTrue(dados["coleta_com_falha"])
        self.assertEqual(dados["selecionado"]["ultimo_sucesso_em"], "2026-11-24T09:00:00-03:00")
        self.assertEqual(dados["selecionado"]["franquia_restante"], 250)


class EndpointsConsumoTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        login_fixture.LoginMonitoramentoTests.setUpClass()

    def setUp(self):
        self.fixture = login_fixture.LoginMonitoramentoTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.cliente = self.fixture.cliente

    def dados(self):
        item = apresentar_mes(registro(), instante("2026-12-15T12:00:00"))
        return {"unidade":{"nome":"Unidade A"}, "historico":[item], "selecionado":item}

    def test_sem_login_nao_consulta_banco_de_consumo(self):
        with patch("monitoramento.consumo_views.carregar_consumo") as carregar:
            for url in ("/dados/consumo/", "/consumo.pdf"):
                self.assertEqual(self.cliente.get(url).status_code, 401)
            carregar.assert_not_called()

    def test_id_adulterado_nao_muda_unidade_autenticada(self):
        self.fixture.entrar()
        with patch("monitoramento.consumo_views.carregar_consumo", return_value=self.dados()) as carregar:
            resposta = self.cliente.get("/dados/consumo/?id_unidade=20&mes=2026-10")
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(carregar.call_args.args[0].id_unidade, 10)
        self.assertIn("no-store", resposta.headers["Cache-Control"])

    def test_banco_indisponivel_retorna503_sem_falso_zero(self):
        self.fixture.entrar()
        with patch("monitoramento.consumo_views.carregar_consumo", side_effect=OperationalError("segredo")):
            resposta = self.cliente.get("/dados/consumo/")
        self.assertEqual(resposta.status_code, 503)
        self.assertNotIn("segredo", resposta.content.decode())

    def test_download_pdf_da_unidade_tem_conteudo_e_headers_privados(self):
        self.fixture.entrar()
        with patch("monitoramento.consumo_views.carregar_consumo", return_value=self.dados()) as carregar:
            for escopo in ("mes", "todos"):
                resposta = self.cliente.get(f"/consumo.pdf?escopo={escopo}&mes=2026-10&id_unidade=20")
                self.assertEqual(resposta.status_code, 200)
                self.assertTrue(resposta.content.startswith(b"%PDF-"))
                self.assertGreater(len(resposta.content), 10000)
                self.assertIn("no-store", resposta.headers["Cache-Control"])
                self.assertEqual(carregar.call_args.args[0].id_unidade, 10)

    def test_sem_coleta_pdf_nao_exporta_saldo_ficticio(self):
        self.fixture.entrar()
        with patch("monitoramento.consumo_views.carregar_consumo", return_value={"historico":[],"selecionado":None}):
            self.assertEqual(self.cliente.get("/consumo.pdf").status_code, 404)

    def test_acesso_removido_e_verificado_em_cada_download(self):
        self.fixture.entrar()
        with self.fixture.banco.cursor() as cursor:
            cursor.execute("UPDATE unidade SET id_usuario_monitoramento=NULL WHERE id_unidade=10")
        with patch("monitoramento.consumo_views.carregar_consumo") as carregar:
            self.assertEqual(self.cliente.get("/consumo.pdf").status_code, 403)
            carregar.assert_not_called()
