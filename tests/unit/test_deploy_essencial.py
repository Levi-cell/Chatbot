import inspect
import logging
import unittest
from unittest.mock import patch

from core.database.deploy import (
    bank_script,
    etapa_transicao_script,
    povoar_etapas,
    transacao_deploy as transacao_deploy_module,
)
from tests.helpers import FakeConn
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_COMENTARIO_SATISFACAO_RECEBIDO,
    EVENTO_EMAIL_VALIDO,
    EVENTO_NOME_CLIENTE_VALIDO,
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
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

        etapa_16 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 16)
        etapa_17 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 17)
        etapa_18 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 18)
        etapa_19 = next(etapa for etapa in povoar_etapas.ETAPAS if etapa[0] == 19)
        self.assertTrue(etapa_16[4])
        self.assertTrue(etapa_17[4])
        self.assertTrue(etapa_18[4])
        self.assertEqual(etapa_19[2:], (True, 30, True))

    def test_etapas_e_transicoes_formam_um_mapa_valido_e_contiguo(self):
        ids_etapa = [etapa[0] for etapa in povoar_etapas.ETAPAS]
        transicoes = etapa_transicao_script.TRANSICOES_INICIAIS

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
            (2, EVENTO_PARA_MIM, 4),
            (2, EVENTO_PARA_OUTRA_PESSOA, 3),
            (5, EVENTO_OFERTA_ACEITA, 8),
            (5, EVENTO_OFERTA_ADIADA, 6),
            (8, EVENTO_EMAIL_VALIDO, 9),
            (15, EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA, 16),
            (16, "agendamento_confirmado", 17),
            (17, EVENTO_SATISFACAO_AVALIADA, 18),
            (18, EVENTO_COMENTARIO_SATISFACAO_RECEBIDO, 19),
        }
        self.assertTrue(arestas_criticas.issubset(set(transicoes)))

    def test_executor_transacional_confirma_ou_reverte_e_propaga(self):
        conn_sucesso = FakeConn()

        with patch.object(
            transacao_deploy_module,
            "get_conn",
            return_value=conn_sucesso,
        ):
            with transacao_deploy_module.transacao_deploy(
                "teste_sucesso",
                logging.getLogger("tests.deploy"),
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
                    logging.getLogger("tests.deploy"),
                ):
                    raise RuntimeError("falha controlada")

        self.assertEqual(conn_falha.commits, 0)
        self.assertEqual(conn_falha.rollbacks, 1)
        self.assertTrue(conn_falha.closed)


if __name__ == "__main__":
    unittest.main()
