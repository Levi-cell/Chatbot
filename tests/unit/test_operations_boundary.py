import ast
import io
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

from operations.integrations import funil_probe
from operations.maintenance import message_partitions


ROOT = Path(__file__).resolve().parents[2]


class FakeCursor:
    def __init__(self, *, falhar=False):
        self.falhar = falhar
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        if self.falhar:
            raise RuntimeError("ddl indisponível")


class FakeConnection:
    def __init__(self, *, falhar=False):
        self.cursor_instance = FakeCursor(falhar=falhar)
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class OperationsBoundaryTests(unittest.TestCase):
    def test_servicos_e_admin_nao_importam_operations(self):
        arquivos = [
            *ROOT.joinpath("callback").rglob("*.py"),
            *ROOT.joinpath("workers").rglob("*.py"),
        ]
        violacoes = []
        for arquivo in arquivos:
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for node in ast.walk(arvore):
                modulos = []
                if isinstance(node, ast.Import):
                    modulos = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modulos = [node.module]
                if any(
                    modulo == "operations"
                    or modulo.startswith("operations.")
                    for modulo in modulos
                ):
                    violacoes.append(str(arquivo.relative_to(ROOT)))

        self.assertEqual(violacoes, [])

    def test_operations_nao_importa_orquestradores(self):
        violacoes = []
        for arquivo in ROOT.joinpath("operations").rglob("*.py"):
            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
            for node in ast.walk(arvore):
                modulos = []
                if isinstance(node, ast.Import):
                    modulos = [item.name for item in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    modulos = [node.module]
                if any(
                    modulo == "workers"
                    or modulo.startswith("workers.")
                    or modulo == "callback"
                    or modulo.startswith("callback.")
                    for modulo in modulos
                ):
                    violacoes.append(str(arquivo.relative_to(ROOT)))

        self.assertEqual(violacoes, [])

    def test_funil_payload_nao_executa_post(self):
        with (
            patch.object(funil_probe, "enviar_oportunidade") as enviar,
            patch.object(funil_probe, "_imprimir_resultado"),
        ):
            codigo = funil_probe.main(["payload"])

        self.assertEqual(codigo, 0)
        enviar.assert_not_called()

    def test_funil_envio_real_exige_confirmacao(self):
        with (
            redirect_stderr(io.StringIO()),
            patch.object(funil_probe, "enviar_oportunidade") as enviar,
            self.assertRaises(SystemExit) as erro,
        ):
            funil_probe.main(["send-test"])

        self.assertEqual(erro.exception.code, 2)
        enviar.assert_not_called()

    def test_particoes_commitam_quatro_meses(self):
        conn = FakeConnection()
        resultado = (
            message_partitions.criar_particoes_historico_mensagens(
                3,
                connection_factory=lambda **_kwargs: conn,
            )
        )

        self.assertEqual(len(resultado), 4)
        self.assertEqual(len(conn.cursor_instance.calls), 4)
        self.assertTrue(conn.committed)
        self.assertFalse(conn.rolled_back)
        self.assertTrue(conn.closed)

    def test_particoes_falham_depois_do_rollback(self):
        conn = FakeConnection(falhar=True)
        with self.assertRaisesRegex(RuntimeError, "ddl indisponível"):
            message_partitions.criar_particoes_historico_mensagens(
                1,
                connection_factory=lambda **_kwargs: conn,
            )

        self.assertFalse(conn.committed)
        self.assertTrue(conn.rolled_back)
        self.assertTrue(conn.closed)


if __name__ == "__main__":
    unittest.main()
