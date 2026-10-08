"""Calendário, recortes e decisão de consolidação sem banco ou rede."""

import unittest
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from core.consumo_meta.apuracao import calcular_resumo, decidir_apuracao, quantidades, validar_identidade
from core.consumo_meta.periodos import fronteiras_mes, proxima_coleta_diaria, validar_mes
from tests.fixtures.consumo_meta import instante, registro, resultado


class ConsumoMensalTests(unittest.TestCase):
    def test_calendario_fevereiro_bissexto_e_virada_do_ano(self):
        for mes, dias in (("2028-02", 29), ("2027-02", 28), ("2026-10", 31), ("2026-11", 30), ("2026-12", 31)):
            with self.subTest(mes=mes):
                inicio, fim = fronteiras_mes(validar_mes(mes), "America/Bahia")
                self.assertEqual((fim - inicio).days, dias)
                self.assertEqual((inicio.hour, fim.hour, fim.day), (0, 0, 1))
                self.assertEqual(inicio.utcoffset(), timedelta(hours=-3))

    def test_mes_invalido(self):
        for mes in ("2026-1", "out-2026", "2026-13", "2026-10-01", "2026-00"):
            with self.subTest(mes=mes), self.assertRaises(ValueError):
                validar_mes(mes)

    def test_soma_sem_duplicar_beneficio_esl(self):
        dados = registro(volumes=(3000, 1000, 1300))
        soma = calcular_resumo(dados)
        self.assertEqual(soma, {"total_mensagens": 5300, "franquia_restante": 0,
            "assumidas_esl": 1000, "excedentes_unidade": 300, "valor_referencia_excedente": "10.50"})
        self.assertEqual(calcular_resumo(registro())["franquia_restante"], 250)

    def test_andamento_e_conferencia_sem_confirmacao_prematura(self):
        for data, estado in (("2026-10-31T23:00:00", "em_andamento"), ("2026-11-01T03:00:00", "em_conferencia"), ("2026-11-24T12:00:00", "em_conferencia")):
            agora = instante(data)
            decisao = decidir_apuracao(None, resultado(agora=agora), agora)
            self.assertEqual(decisao["status_apuracao"], estado)
            self.assertEqual(decisao["data_proxima_consolidacao"], date(2026, 11, 25))

    def test_dia25_igual_consolida(self):
        agora = instante("2026-11-25T12:00:00")
        decisao = decidir_apuracao(registro(), resultado(agora=agora), agora)
        self.assertEqual(decisao["status_apuracao"], "consolidado")
        self.assertIsNone(decisao["data_proxima_consolidacao"])

    def test_divergencia_no_dia25_prorroga_e_dia26_nao_confirma(self):
        agora = instante("2026-11-25T12:00:00")
        resposta = resultado(agora=agora, volumes=(3001, 750, 0))
        decisao = decidir_apuracao(registro(), resposta, agora)
        self.assertEqual(decisao["data_proxima_consolidacao"], date(2026, 12, 25))
        anterior = registro(agora=agora, volumes=(3001, 750, 0)) | decisao
        depois = agora + timedelta(days=1)
        self.assertEqual(decidir_apuracao(anterior, resultado(agora=depois, volumes=(3001, 750, 0)), depois)["status_apuracao"], "em_conferencia")

    def test_sem_anterior_completo_ou_anterior_do_mesmo_dia_nao_consolida(self):
        agora = instante("2026-11-25T12:00:00")
        for anterior in (None, registro(agora=instante("2026-10-31T12:00:00")), registro(agora=agora - timedelta(hours=1))):
            decisao = decidir_apuracao(anterior, resultado(agora=agora), agora)
            self.assertEqual(decisao["status_apuracao"], "em_conferencia")
            self.assertEqual(decisao["data_proxima_consolidacao"], date(2026, 12, 25))

    def test_dia25_perdido_usa_proximo25_futuro(self):
        for data, esperado in (("2026-11-26T12:00:00", date(2026, 12, 25)), ("2026-12-10T12:00:00", date(2026, 12, 25))):
            agora = instante(data)
            self.assertEqual(decidir_apuracao(registro(), resultado(agora=agora), agora)["data_proxima_consolidacao"], esperado)

    def test_mes_consolidado_nao_pode_ser_reaberto(self):
        with self.assertRaises(ValueError):
            decidir_apuracao(registro() | {"status_apuracao": "consolidado"}, resultado(), instante("2026-12-25T12:00:00"))

    def test_rejeita_mudanca_de_recorte_sem_alterar_historico(self):
        for alteracao in ({"waba": "123"}, {"phone": "222"}, {"fuso": "America/Bahia", "timezone_id": 206}):
            with self.subTest(alteracao=alteracao), self.assertRaises(ValueError):
                validar_identidade(registro(), resultado(**alteracao))

    def test_rejeita_volumes_incompativeis(self):
        for volumes in ((0, 1001, 0), (-1, 0, 0), (1.5, 0, 0), (True, 0, 0)):
            with self.subTest(volumes=volumes), self.assertRaises(ValueError):
                quantidades(resultado(volumes=volumes))

    def test_agenda_diaria_nao_repete_no_mesmo_dia(self):
        agora = instante("2026-11-01T03:01:00")
        proxima = proxima_coleta_diaria(agora, "America/Sao_Paulo", 9)
        self.assertEqual(proxima.date(), date(2026, 11, 2))
        self.assertEqual(proxima.astimezone(ZoneInfo("America/Sao_Paulo")).hour, 9)
