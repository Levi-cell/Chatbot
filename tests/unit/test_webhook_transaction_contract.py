import inspect
import unittest
from pathlib import Path

from callback.webhook.services import flood_guard, post_flow
from callback.webhook.services import populating_fila_mensagens as fila


class WebhookTransactionContractTests(unittest.TestCase):
    def test_post_flow_controla_transacao_da_fila(self):
        source = inspect.getsource(post_flow._executar_transacao_fila)

        self.assertIn("conn_webhook.commit()", source)
        self.assertIn("conn_webhook.rollback()", source)
        self.assertIn("conn_webhook.close()", source)

    def test_flood_guard_mantem_transacoes_independentes(self):
        source = inspect.getsource(flood_guard)

        self.assertIn("conn.commit()", source)
        self.assertIn("conn.rollback()", source)
        self.assertIn("conn.close()", source)

    def test_modulo_de_fila_nao_controla_conexao_ou_transacao(self):
        source = inspect.getsource(fila)

        self.assertNotIn("get_conn", source)
        self.assertNotIn(".commit(", source)
        self.assertNotIn(".rollback(", source)
        self.assertNotIn(".close(", source)

    def test_transacoes_dos_servicos_webhook_ficam_nos_dois_orquestradores(self):
        services_dir = Path(inspect.getfile(post_flow)).parent
        arquivos_com_transacao = set()

        for arquivo in services_dir.glob("*.py"):
            source = arquivo.read_text(encoding="utf-8")

            if any(
                token in source
                for token in (".commit(", ".rollback(", ".close(")
            ):
                arquivos_com_transacao.add(arquivo.name)

        self.assertEqual(
            arquivos_com_transacao,
            {"post_flow.py", "flood_guard.py"},
        )


if __name__ == "__main__":
    unittest.main()
