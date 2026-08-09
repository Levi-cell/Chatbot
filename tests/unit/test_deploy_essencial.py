import inspect
import logging
import unittest
from pathlib import Path
from unittest.mock import patch

from core.database.deploy_database import (
    bank_script,
    etapa_transicao_script,
    floodscript,
    povoar_etapas,
    transacao_deploy as transacao_deploy_module,
)
from tests.helpers import FakeConn
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_COMENTARIO_SATISFACAO_ACEITO,
    EVENTO_COMENTARIO_SATISFACAO_RECUSADO,
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_DESTINO_ATENDIMENTO_DEFINIDO,
    EVENTO_EMAIL_VALIDO,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_NOME_DEPENDENTE_VALIDO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PROFISSAO_DEPENDENTE_VALIDA,
    EVENTO_PROFISSAO_TITULAR_VALIDA,
    EVENTO_SATISFACAO_AVALIADA,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
)


class DeployEssencialTests(unittest.TestCase):
    def test_ddl_contem_os_contratos_que_nao_podem_desaparecer(self):
        source = inspect.getsource(bank_script.criar_tabelas)
        contratos = (
            "CREATE TABLE IF NOT EXISTS chatbot.fila_mensagens",
            "CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens",
            "CREATE TABLE IF NOT EXISTS chatbot.respostas_desafios",
            "CREATE TABLE IF NOT EXISTS chatbot.pesquisa_satisfacao",
            "CREATE TABLE IF NOT EXISTS chatbot.integracao_funil_unidade",
            "CREATE TABLE IF NOT EXISTS chatbot.funil_envios",
            "UNIQUE (id_conversa, id_etapa)",
            "UNIQUE,\n            nota SMALLINT",
            "CHECK (nota IS NULL OR nota BETWEEN 1 AND 5)",
            "waba_id VARCHAR(100)",
            "link_instagram VARCHAR(400)",
            "numero_comercial",
            "bpa_ativo BOOLEAN NOT NULL DEFAULT FALSE",
            "motivo_encerramento VARCHAR(30)",
            "profissao VARCHAR(100) NULL",
            "encerra_automaticamente BOOLEAN",
            "bloqueio_dias INTEGER",
            "elegivel_funil BOOLEAN",
            "CHECK (status IN ('pending', 'processing', 'sent'))",
        )

        for contrato in contratos:
            with self.subTest(contrato=contrato):
                self.assertIn(contrato, source)

        self.assertNotIn("ALTER TABLE", source)
        self.assertNotIn("Supera - Santo Antônio de Jesus", source)
        self.assertNotIn("https://www.instagram.com/supera.saj/", source)
        self.assertLess(
            source.index("CREATE TABLE IF NOT EXISTS chatbot.conversa"),
            source.index("CREATE TABLE IF NOT EXISTS chatbot.dependente"),
        )
        self.assertLess(
            source.index("CREATE TABLE IF NOT EXISTS chatbot.fila_mensagens"),
            source.index("CREATE TABLE IF NOT EXISTS chatbot.historico_mensagens"),
        )

        flood_source = inspect.getsource(
            floodscript.criar_tabelas_bloqueio_flood
        )
        self.assertIn(
            "CREATE TABLE IF NOT EXISTS chatbot.cliente_bloqueado_meta",
            flood_source,
        )
        self.assertIn("nome VARCHAR(200) NULL", flood_source)
        self.assertNotIn("ALTER TABLE", flood_source)

        etapa_18 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 18)
        etapa_19 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 19)
        etapa_20 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 20)
        etapa_21 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 21)
        etapa_22 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 22)
        self.assertFalse(
            next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 17)[4]
        )
        self.assertTrue(etapa_18[4])
        self.assertTrue(etapa_19[4])
        self.assertTrue(etapa_20[4])
        self.assertTrue(etapa_21[4])
        self.assertEqual(etapa_22[2:], (True, 30, True))

    def test_etapas_e_transicoes_formam_um_mapa_valido_e_contiguo(self):
        ids_etapa = [etapa[0] for etapa in povoar_etapas.ETAPAS]
        transicoes = etapa_transicao_script.TRANSICOES_INICIAIS

        self.assertEqual(len(ids_etapa), 22)
        self.assertEqual(len(transicoes), 26)
        self.assertEqual(ids_etapa, list(range(1, len(ids_etapa) + 1)))
        self.assertEqual(
            len({(origem, evento) for origem, evento, _ in transicoes}),
            len(transicoes),
        )

        for origem, _evento, destino in transicoes:
            with self.subTest(origem=origem, destino=destino):
                self.assertIn(origem, ids_etapa)
                self.assertIn(destino, ids_etapa)
                self.assertNotEqual(origem, destino)

        arestas_criticas = {
            (1, EVENTO_NOME_CLIENTE_VALIDO, 2),
            (2, EVENTO_DESTINO_ATENDIMENTO_DEFINIDO, 3),
            (3, "destino_atendimento_confirmado_titular", 4),
            (3, "destino_atendimento_confirmado_dependente", 5),
            (4, EVENTO_PROFISSAO_DEPENDENTE_VALIDA, 5),
            (4, EVENTO_PROFISSAO_TITULAR_VALIDA, 6),
            (5, EVENTO_NOME_DEPENDENTE_VALIDO, 6),
            (7, EVENTO_OFERTA_ACEITA, 10),
            (7, EVENTO_OFERTA_ADIADA, 8),
            (10, EVENTO_EMAIL_VALIDO, 11),
            (17, EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA, 18),
            (18, "agendamento_confirmado", 19),
            (19, EVENTO_SATISFACAO_AVALIADA, 20),
            (20, EVENTO_COMENTARIO_SATISFACAO_ACEITO, 21),
            (20, EVENTO_COMENTARIO_SATISFACAO_RECUSADO, 22),
            (21, EVENTO_COMENTARIO_SATISFACAO_RECEBIDO, 22),
        }
        self.assertTrue(arestas_criticas.issubset(set(transicoes)))

    def test_migracao_etapa3_remapeia_referencias_e_valida_politicas(self):
        caminho = (
            Path(__file__).resolve().parents[2]
            / "deploy"
            / "migrations"
            / "20260809_adicionar_confirmacao_etapa3.sql"
        )
        sql = caminho.read_text(encoding="utf-8")

        contratos = (
            "BEGIN;",
            "LOCK TABLE",
            "FOR v_id_origem IN REVERSE 21..3 LOOP",
            "UPDATE chatbot.conversa",
            "UPDATE chatbot.historico_mensagens",
            "UPDATE chatbot.respostas_desafios",
            "(id_etapa BETWEEN 18 AND 22)",
            "CASE WHEN id_etapa = 22 THEN 30 ELSE 0 END",
            "destino_atendimento_confirmado_titular",
            "destino_atendimento_confirmado_dependente",
            "COMMIT;",
        )

        for contrato in contratos:
            with self.subTest(contrato=contrato):
                self.assertIn(contrato, sql)

        self.assertNotIn("CASCADE", sql.upper())
        self.assertNotIn("TRUNCATE", sql.upper())
        self.assertNotIn("DROP TABLE", sql.upper())

    def test_executor_transacional_confirma_ou_reverte_e_propaga(self):
        conn_sucesso = FakeConn()

        with patch.object(
            transacao_deploy_module,
            "get_conn",
            return_value=conn_sucesso,
        ):
            with transacao_deploy_module.transacao_deploy(
                "teste_sucesso",
                logging.getLogger("tests.deploy_database"),
            ):
                pass

        self.assertEqual(conn_sucesso.commits, 1)
        self.assertEqual(conn_sucesso.rollbacks, 0)
        self.assertTrue(conn_sucesso.closed)

        conn_falha = FakeConn()

        with patch.object(
            transacao_deploy_module,
            "get_conn",
            return_value=conn_falha,
        ):
            with self.assertRaisesRegex(RuntimeError, "falha controlada"):
                with transacao_deploy_module.transacao_deploy(
                    "teste_falha",
                    logging.getLogger("tests.deploy_database"),
                ):
                    raise RuntimeError("falha controlada")

        self.assertEqual(conn_falha.commits, 0)
        self.assertEqual(conn_falha.rollbacks, 1)
        self.assertTrue(conn_falha.closed)


if __name__ == "__main__":
    unittest.main()
