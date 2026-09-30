"""Migração e worker em PostgreSQL descartável, com respostas Meta simuladas."""

import os
from datetime import date, timedelta
from pathlib import Path
import unittest
from unittest.mock import patch

import psycopg
from psycopg.conninfo import conninfo_to_dict

from core.repositories.consumo_meta import coletas
from core.repositories.monitoramento import consumo as consulta_painel
from tests.fixtures.consumo_meta import instante, resultado
from workers.worker_consumo_meta.consumo_worker import executar_ciclo_consumo, LOCK_CONSUMO_META
from workers.worker_consumo_meta.processamento import salvar_coleta, registrar_falha

DSN = os.environ.get("CONSUMO_META_TEST_DSN")
MIGRACAO = Path(__file__).resolve().parents[2] / "deploy/migrations/20260929_consumo_mensal_meta.sql"


@unittest.skipUnless(DSN, "Exige CONSUMO_META_TEST_DSN local em test_chatbot_consumo vazio")
class ConsumoPostgresTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        parametros = conninfo_to_dict(DSN)
        locais = {"localhost", "127.0.0.1", "::1"}
        if (parametros.get("host") not in locais or parametros.get("dbname") != "test_chatbot_consumo"
                or parametros.get("service") or (parametros.get("hostaddr") and parametros["hostaddr"] not in locais)):
            raise RuntimeError("Teste exige banco test_chatbot_consumo em loopback")
        cls.conn = psycopg.connect(DSN, autocommit=True, connect_timeout=5)
        if cls.conn.execute("SELECT to_regnamespace('chatbot')").fetchone()[0] is not None:
            cls.conn.close()
            raise RuntimeError("Teste exige schema chatbot ausente")

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def setUp(self):
        self.conn.execute("CREATE SCHEMA chatbot")
        self.addCleanup(self.limpar)
        self.conn.execute("""
            CREATE TABLE chatbot.unidade (id_unidade INTEGER PRIMARY KEY, nome_unidade TEXT,
                waba_id VARCHAR(100), phone_number_id VARCHAR(100));
            INSERT INTO chatbot.unidade VALUES (10,'Unidade A','999','111'),(20,'Unidade B','888','222');
            CREATE TABLE chatbot.conversa (id_conversa INTEGER, motivo_encerramento TEXT);
            INSERT INTO chatbot.conversa VALUES (1,'suporte_idoso_60');
            CREATE TABLE chatbot.fila_mensagens (id_mensagem INTEGER, status TEXT);
            INSERT INTO chatbot.fila_mensagens VALUES(1,'processing');
        """)
        self.conn.execute(MIGRACAO.read_text(encoding="utf-8"))

    def limpar(self):
        self.conn.execute("ROLLBACK")
        # Apenas o schema criado neste teste no banco local explicitamente validado.
        self.conn.execute("DROP SCHEMA chatbot CASCADE")

    def ler(self, unidade=10):
        with self.conn.cursor() as cursor:
            return coletas.listar_registros(cursor, unidade)

    def gravar(self, agora, volumes=(3000, 750, 0), mes="2026-10", unidade=10):
        return salvar_coleta(self.conn, unidade, resultado(mes, agora, volumes), agora, agora + timedelta(hours=1))

    def ciclo(self, agora, *, erro_unidade=None, volumes=(3000, 750, 0), fuso="America/Sao_Paulo", codigo=25):
        def conta(waba, **kwargs):
            return {"waba_id": waba, "timezone_id": str(codigo), "fuso_horario": fuso}
        def metricas(conta, *, phone_number_id, mes, **kwargs):
            if conta["waba_id"] == erro_unidade:
                raise RuntimeError("Falha simulada")
            return resultado(mes, agora, volumes, waba=conta["waba_id"], phone=phone_number_id, fuso=fuso, timezone_id=codigo)
        with patch("workers.worker_consumo_meta.consumo_worker.consultar_conta_consumo", side_effect=conta), patch(
            "workers.worker_consumo_meta.consumo_worker.consultar_metricas_conta", side_effect=metricas):
            return executar_ciclo_consumo(conectar=lambda: psycopg.connect(DSN), relogio=lambda: agora)

    def test_migracao_reexecutavel_sem_mudar_fluxo_e_fuso_inicial_nulo(self):
        self.conn.execute(MIGRACAO.read_text(encoding="utf-8"))
        self.assertEqual(self.conn.execute("SELECT id_fuso,nome_fuso FROM chatbot.unidade").fetchall(), [(None,None),(None,None)])
        self.assertEqual(self.conn.execute("SELECT * FROM chatbot.conversa").fetchall(), [(1,"suporte_idoso_60")])
        self.assertEqual(self.conn.execute("SELECT status FROM chatbot.fila_mensagens").fetchone()[0], "processing")
        with self.assertRaises(psycopg.errors.CheckViolation):
            self.conn.execute("UPDATE chatbot.unidade SET id_fuso=25 WHERE id_unidade=10")

    def test_upsert_nao_duplica_e_leitura_antiga_nao_sobrescreve(self):
        agora = instante("2026-10-15T12:00:00")
        self.gravar(agora)
        self.gravar(agora + timedelta(hours=1), volumes=(3500,800,0))
        self.assertFalse(self.gravar(agora, volumes=(0,0,0)))
        self.assertEqual(len(self.ler()), 1)
        self.assertEqual(self.ler()[0]["qtd_janela_gratuita"], 3500)

    def test_falha_preserva_totais_e_ultima_coleta(self):
        agora = instante("2026-10-15T12:00:00")
        self.gravar(agora)
        registrar_falha(self.conn,10,"2026-10",agora+timedelta(hours=1),agora+timedelta(hours=2),"Falha simulada")
        self.assertEqual(self.ler()[0]["ultimo_sucesso_em"], agora)
        self.assertEqual(self.ler()[0]["qtd_franquia_consumida"], 750)

    def test_falha_antes_primeira_coleta_nao_cria_zero_e_nao_para_outra_unidade(self):
        agora = instante("2026-10-15T12:00:00")
        self.assertEqual(self.ciclo(agora, erro_unidade="999"), {"coletados":1,"falhas":1,"ocupado":False})
        self.assertEqual(self.ler(), [])
        self.assertEqual(len(self.ler(20)), 1)
        self.assertIsNotNone(self.conn.execute("SELECT ultimo_erro FROM chatbot.consumo_meta_coletas WHERE id_unidade=10 AND periodo='2026-10'").fetchone()[0])
        self.assertEqual(self.ciclo(agora + timedelta(minutes=5))["coletados"], 0)
        self.assertEqual(self.ciclo(agora + timedelta(hours=1))["coletados"], 2)

    def test_concorrencia_worker_respeita_lock_exclusivo(self):
        self.conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_CONSUMO_META,))
        try:
            self.assertTrue(self.ciclo(instante("2026-10-15T12:00:00"))["ocupado"])
            self.assertEqual(self.ler(), [])
        finally:
            self.conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_CONSUMO_META,))

    def test_dois_meses_pendentes_consolidam_em_dezembro_atual_continua(self):
        self.ciclo(instante("2026-11-24T12:00:00"))
        self.ciclo(instante("2026-11-25T12:00:00"), volumes=(3001,750,0))
        outubro = next(r for r in self.ler() if r["mes_referencia"] == date(2026,10,1))
        self.assertEqual(outubro["data_proxima_consolidacao"], date(2026,12,25))
        self.ciclo(instante("2026-12-24T12:00:00"), volumes=(3001,750,0))
        self.ciclo(instante("2026-12-25T12:00:00"), volumes=(3001,750,0))
        self.assertEqual([r["status_apuracao"] for r in self.ler()], ["em_andamento","consolidado","consolidado"])
        self.assertEqual(self.ciclo(instante("2026-12-26T12:00:00"))["coletados"], 2)

    def test_falha_dia25_prorroga_mes_sem_aprovar_no_dia26(self):
        self.ciclo(instante("2026-11-24T12:00:00"))
        self.ciclo(instante("2026-11-25T12:00:00"), erro_unidade="999")
        self.ciclo(instante("2026-11-26T12:00:00"))
        outubro = self.ler()[-1]
        self.assertEqual(outubro["status_apuracao"], "em_conferencia")
        self.assertEqual(outubro["data_proxima_consolidacao"], date(2026,12,25))

    def test_mudanca_fuso_atualiza_cadastro_preserva_recorte_e_avisa(self):
        self.ciclo(instante("2026-10-15T12:00:00"))
        self.ciclo(instante("2026-10-16T12:00:00"), fuso="America/Bahia",codigo=206)
        self.assertEqual(self.conn.execute("SELECT id_fuso,nome_fuso FROM chatbot.unidade WHERE id_unidade=10").fetchone(), (206,"America/Bahia"))
        self.assertEqual(self.ler()[0]["fuso_horario"], "America/Sao_Paulo")
        self.assertEqual(self.ler()[0]["ultimo_sucesso_em"], instante("2026-10-15T12:00:00"))

    def test_consulta_painel_restringe_unidade(self):
        self.ciclo(instante("2026-10-15T12:00:00"), erro_unidade="999")
        with self.conn.cursor() as cursor:
            self.assertEqual(consulta_painel.listar_meses(cursor,10), [])
            self.assertEqual(len(consulta_painel.listar_meses(cursor,20)), 1)

    def test_transacao_reverte_volume_se_agenda_falhar(self):
        self.gravar(instante("2026-10-15T12:00:00"))
        with patch.object(coletas, "agendar", side_effect=RuntimeError("Falha simulada")), self.assertRaises(RuntimeError):
            self.gravar(instante("2026-10-15T13:00:00"), volumes=(5000,900,0))
        self.assertEqual(self.ler()[0]["qtd_janela_gratuita"], 3000)

    def test_troca_numero_durante_http_nao_cria_mes_com_cadastro_obsoleto(self):
        agora = instante("2026-10-15T12:00:00")
        coleta = resultado(agora=agora)
        self.conn.execute("UPDATE chatbot.unidade SET phone_number_id='333' WHERE id_unidade=10")
        with self.assertRaisesRegex(ValueError, "mudou durante a coleta"):
            salvar_coleta(self.conn, 10, coleta, agora, agora + timedelta(hours=1))
        self.assertEqual(self.ler(), [])
