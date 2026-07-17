import importlib.util
import runpy
import unittest
from pathlib import Path
from unittest.mock import patch


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
ENTRYPOINT_FLOW = RAIZ_PROJETO / "workers" / "worker_flow" / "iniciar_flow_worker.py"
ENTRYPOINT_FUNIL = (
    RAIZ_PROJETO / "workers" / "worker_funil" / "iniciar_worker_funil.py"
)


class PararEntrypoint(BaseException):
    """Interrompe supervisores infinitos depois da primeira chamada do teste."""


def importar_arquivo_com_nome(arquivo, nome_modulo):
    spec = importlib.util.spec_from_file_location(nome_modulo, arquivo)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Nao foi possivel carregar o entrypoint: {arquivo}")

    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class WorkerEntrypointsTests(unittest.TestCase):
    def test_importar_entrypoint_flow_nao_inicia_worker(self):
        with patch(
            "workers.worker_flow.response_flow.flow_worker.worker_flow"
        ) as worker_mock:
            importar_arquivo_com_nome(
                ENTRYPOINT_FLOW,
                "workers.worker_flow._entrypoint_import_test",
            )

        worker_mock.assert_not_called()

    def test_executar_entrypoint_flow_como_script_inicia_worker(self):
        with patch(
            "workers.worker_flow.response_flow.flow_worker.worker_flow",
            side_effect=PararEntrypoint,
        ) as worker_mock:
            with self.assertRaises(PararEntrypoint):
                runpy.run_path(str(ENTRYPOINT_FLOW), run_name="__main__")

        worker_mock.assert_called_once_with()

    def test_importar_entrypoint_funil_nao_inicia_worker(self):
        with (
            patch("workers.worker_funil.config.FUNIL_WORKER_ENABLED", True),
            patch(
                "workers.worker_funil.config.validar_configuracao_funil"
            ) as validar_mock,
            patch(
                "workers.worker_funil.funil_worker.funil_worker"
            ) as worker_mock,
        ):
            importar_arquivo_com_nome(
                ENTRYPOINT_FUNIL,
                "workers.worker_funil._entrypoint_import_test",
            )

        validar_mock.assert_not_called()
        worker_mock.assert_not_called()

    def test_executar_entrypoint_funil_como_script_inicia_worker(self):
        with (
            patch("workers.worker_funil.config.FUNIL_WORKER_ENABLED", True),
            patch(
                "workers.worker_funil.config.validar_configuracao_funil"
            ) as validar_mock,
            patch(
                "workers.worker_funil.funil_worker.funil_worker",
                side_effect=PararEntrypoint,
            ) as worker_mock,
        ):
            with self.assertRaises(PararEntrypoint):
                runpy.run_path(str(ENTRYPOINT_FUNIL), run_name="__main__")

        validar_mock.assert_called_once_with()
        worker_mock.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
