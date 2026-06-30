import ast
import inspect
import textwrap
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib import admin as django_admin
from django.urls import NoReverseMatch

from core.cache import cache_unidade
from core.repositories import inserts
from webhook import admin as webhook_admin
from webhook.models import ClienteBloqueadoMeta, Conversa
from workers.worker_flow.response_flow import flow_worker


class CursorComFalha:
    def execute(self, *_args, **_kwargs):
        raise RuntimeError("banco falhou")


class RedisComFalha:
    def get(self, _key):
        raise ConnectionError("redis caiu")


class TryExceptContractTests(unittest.TestCase):
    def test_inserts_nao_capturam_excecao_do_orquestrador(self):
        for funcao in (
            inserts.inserindo_em_cliente_caso_seja_novo,
            inserts.inserindo_em_conversa_caso_seja_nova,
        ):
            arvore = ast.parse(textwrap.dedent(inspect.getsource(funcao)))
            self.assertFalse(
                any(isinstance(no, ast.Try) for no in ast.walk(arvore)),
                msg=funcao.__name__,
            )

    def test_inserts_continuam_propagando_a_mesma_excecao(self):
        with self.assertRaisesRegex(RuntimeError, "banco falhou"):
            inserts.inserindo_em_cliente_caso_seja_novo(
                "5571999999999",
                CursorComFalha(),
            )

        with self.assertRaisesRegex(RuntimeError, "banco falhou"):
            inserts.inserindo_em_conversa_caso_seja_nova(
                1,
                1,
                CursorComFalha(),
            )

    def test_cache_invalido_mantem_false_e_sinaliza_erro(self):
        with patch.object(cache_unidade.logger, "warning") as warning:
            resultado = cache_unidade._cache_valido(RedisComFalha())

        self.assertFalse(resultado)
        warning.assert_called_once()

    def test_links_admin_fazem_fallback_apenas_para_rota_ausente(self):
        cliente = SimpleNamespace(
            id_cliente=10,
            nome="Cliente Teste",
            waid_telefone="5571999999999",
        )
        obj = SimpleNamespace(id_cliente=cliente)

        admins = (
            webhook_admin.ConversaAdmin(Conversa, django_admin.site),
            webhook_admin.ClienteBloqueadoMetaAdmin(
                ClienteBloqueadoMeta,
                django_admin.site,
            ),
        )

        for model_admin in admins:
            with self.subTest(admin=model_admin.__class__.__name__), patch.object(
                webhook_admin,
                "reverse",
                side_effect=NoReverseMatch("rota ausente"),
            ), patch.object(webhook_admin.logger, "exception") as logger_exception:
                self.assertEqual(model_admin.cliente_link(obj), "Cliente Teste")
                logger_exception.assert_called_once()

    def test_links_admin_propagam_erro_inesperado(self):
        cliente = SimpleNamespace(
            id_cliente=10,
            nome="Cliente Teste",
            waid_telefone="5571999999999",
        )
        obj = SimpleNamespace(id_cliente=cliente)
        model_admin = webhook_admin.ConversaAdmin(
            Conversa,
            django_admin.site,
        )

        with patch.object(
            webhook_admin,
            "reverse",
            side_effect=RuntimeError("falha inesperada"),
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "falha inesperada",
            ):
                model_admin.cliente_link(obj)

    def test_worker_preserva_barreira_generica_e_retry(self):
        source = inspect.getsource(flow_worker.worker_flow)

        self.assertIn("except Exception as erro:", source)
        self.assertIn("handle_erro_generico(", source)
        self.assertIn("reparar_cache_cliente_stale_se_fk_invalida", source)
        self.assertIn("reparar_cache_unidade_stale_se_fk_invalida", source)

    def test_worker_fecha_conexao_em_finally_independente(self):
        source = inspect.getsource(flow_worker.worker_flow)

        self.assertIn(
            "finally:\n                    try:\n                        conn_ciclo.close()",
            source,
        )
        self.assertIn("conexao_ciclo_close_falhou", source)


if __name__ == "__main__":
    unittest.main()
