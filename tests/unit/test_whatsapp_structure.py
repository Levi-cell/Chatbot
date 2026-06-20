import ast
import unittest
from pathlib import Path

from core.integrations.whatsapp.messages.etapas import (
    MENSAGEM_ETAPA_1,
    TITULO_BOTAO_ETAPA_1,
)
from core.integrations.whatsapp.messages.tratamentos import (
    CALLBACK_RETORNAR_ATENDIMENTO,
    MENSAGEM_MIDIA_ETAPA,
    MENSAGEM_MIDIA_INICIO,
    TITULO_BOTAO_CONTINUAR,
)


RAIZ_PROJETO = Path(__file__).resolve().parents[2]
RAIZ_WHATSAPP = RAIZ_PROJETO / "core" / "integrations" / "whatsapp"
RAIZ_PYWA = RAIZ_WHATSAPP / "pywa_functions"

RAIZES_PRODUCAO = (
    RAIZ_PROJETO / "core",
    RAIZ_PROJETO / "workers",
    RAIZ_PROJETO / "callback",
)

METODOS_PYWA = {
    "send_message",
    "block_users",
    "unblock_users",
    "get_blocked_users",
}

CONTEUDOS_WHATSAPP = (
    MENSAGEM_ETAPA_1,
    TITULO_BOTAO_ETAPA_1,
    MENSAGEM_MIDIA_INICIO,
    MENSAGEM_MIDIA_ETAPA,
    TITULO_BOTAO_CONTINUAR,
    CALLBACK_RETORNAR_ATENDIMENTO,
)


def arquivos_python_producao():
    for raiz in RAIZES_PRODUCAO:
        yield from raiz.rglob("*.py")


def esta_em_pywa_functions(arquivo):
    try:
        arquivo.relative_to(RAIZ_PYWA)
        return True
    except ValueError:
        return False


class WhatsappStructureTests(unittest.TestCase):
    def test_imports_e_chamadas_pywa_ficam_em_pywa_functions(self):
        violacoes = []

        for arquivo in arquivos_python_producao():
            if esta_em_pywa_functions(arquivo):
                continue

            arvore = ast.parse(arquivo.read_text(encoding="utf-8"))

            for no in ast.walk(arvore):
                if isinstance(no, ast.Import):
                    if any(
                        alias.name == "pywa" or alias.name.startswith("pywa.")
                        for alias in no.names
                    ):
                        violacoes.append(f"{arquivo}:{no.lineno}: import pywa")

                if isinstance(no, ast.ImportFrom):
                    modulo = no.module or ""
                    if modulo == "pywa" or modulo.startswith("pywa."):
                        violacoes.append(f"{arquivo}:{no.lineno}: from pywa")

                if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute):
                    if no.func.attr in METODOS_PYWA:
                        violacoes.append(
                            f"{arquivo}:{no.lineno}: chamada {no.func.attr}"
                        )

        self.assertEqual(violacoes, [])

    def test_textos_de_saida_ficam_em_messages(self):
        violacoes = []

        for arquivo in arquivos_python_producao():
            if arquivo.is_relative_to(RAIZ_WHATSAPP / "messages"):
                continue

            conteudo = arquivo.read_text(encoding="utf-8")
            for conteudo_whatsapp in CONTEUDOS_WHATSAPP:
                if conteudo_whatsapp in conteudo:
                    violacoes.append(f"{arquivo}: {conteudo_whatsapp}")

        self.assertEqual(violacoes, [])

    def test_titulos_de_botao_respeitam_limite_da_meta(self):
        for titulo in (TITULO_BOTAO_ETAPA_1, TITULO_BOTAO_CONTINUAR):
            with self.subTest(titulo=titulo):
                self.assertGreaterEqual(len(titulo), 1)
                self.assertLessEqual(len(titulo), 20)


if __name__ == "__main__":
    unittest.main()
