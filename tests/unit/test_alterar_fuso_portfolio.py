import io
import unittest
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

from utilitarios.consultas_franquia.alterar_fuso_portfolio import alterar_fuso_portfolio


def resposta(dados, status=200):
    retorno = Mock(status_code=status)
    retorno.json.return_value = dados
    return retorno


class AlterarFusoPortfolioTestCase(unittest.TestCase):
    def setUp(self):
        config = SimpleNamespace(
            construir_url_graph_api=lambda alvo: f"https://graph.facebook.com/v26.0/{alvo}",
            get_token_usuario_meta=lambda: "token_simulado",
            get_meta_http_timeout=lambda: (1, 2),
        )
        patches = [
            patch.dict("sys.modules", {"core.integrations.whatsapp.tools.config": config}),
            patch("utilitarios.bootstrap.configurar_ambiente_utilitario"),
        ]
        for ajuste in patches:
            ajuste.start()
            self.addCleanup(ajuste.stop)
        self.session = Mock()
        self.session.get.side_effect = [
            resposta({"id": "123", "timezone_id": 0}),
            resposta({"id": "123", "timezone_id": "206"}),
        ]
        self.session.post.return_value = resposta({"success": True})

    def executar(self, id_portfolio=123, id_timezone=206):
        with redirect_stdout(io.StringIO()):
            return alterar_fuso_portfolio(
                id_portfolio, id_timezone, session=self.session,
            )

    def test_altera_somente_fuso_e_confirma_por_leitura(self):
        resultado = self.executar()
        self.assertEqual(resultado["timezone_id_anterior"], 0)
        self.assertEqual(resultado["timezone_id_atual"], 206)
        self.assertTrue(resultado["confirmado"])
        self.session.post.assert_called_once_with(
            "https://graph.facebook.com/v26.0/123",
            headers={"Authorization": "Bearer token_simulado"},
            timeout=(1, 2), allow_redirects=False, data={"timezone_id": 206},
        )
        self.assertEqual(self.session.get.call_count, 2)

    def test_nao_altera_quando_fuso_ja_esta_correto(self):
        self.session.get.side_effect = [resposta({"id": "123", "timezone_id": 206})]
        self.assertFalse(self.executar()["alterado"])
        self.session.post.assert_not_called()

    def test_ids_invalidos_nao_fazem_requisicao(self):
        for portfolio, fuso in [(True, 206), (123, 0), (123, -3), (123, "America/Bahia")]:
            with self.subTest(portfolio=portfolio, fuso=fuso):
                with self.assertRaises(ValueError):
                    self.executar(portfolio, fuso)
        self.session.get.assert_not_called()
        self.session.post.assert_not_called()

    def test_recusa_da_meta_nao_expoe_mensagem_arbitraria(self):
        self.session.post.return_value = resposta(
            {"error": {"code": 200, "message": "token_simulado"}}, status=403,
        )
        with self.assertRaisesRegex(RuntimeError, "HTTP 403") as erro:
            self.executar()
        self.assertNotIn("token_simulado", str(erro.exception))
        self.assertEqual(self.session.get.call_count, 1)

    def test_timeout_nao_repete_post_nem_confirma_sucesso(self):
        self.session.post.side_effect = requests.Timeout("token_simulado")
        with self.assertRaisesRegex(RuntimeError, "Resultado não confirmado"):
            self.executar()
        self.session.post.assert_called_once()

    def test_3910_explica_permissao_do_portfolio_sem_repetir_post(self):
        self.session.post.return_value = resposta(
            {"error": {"code": 3910, "message": "token_simulado"}}, status=400,
        )
        with self.assertRaisesRegex(RuntimeError, "sem permissão para editar") as erro:
            self.executar()
        self.assertIn("identidade vinculada ao token", str(erro.exception))
        self.assertNotIn("token_simulado", str(erro.exception))
        self.session.post.assert_called_once()
        self.assertEqual(self.session.get.call_count, 1)

    def test_get_divergente_nao_confirma_alteracao(self):
        self.session.get.side_effect = [
            resposta({"id": "123", "timezone_id": 0}),
            resposta({"id": "123", "timezone_id": 25}),
        ]
        with self.assertRaisesRegex(RuntimeError, "Alteração ainda não confirmada"):
            self.executar()


if __name__ == "__main__":
    unittest.main()
