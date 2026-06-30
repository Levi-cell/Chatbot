import unittest

from workers.worker_flow.response_flow.etapas.validadores_universais.validador_midia import (
    validar_midia,
)


class DetectorMidiaTests(unittest.TestCase):
    def test_texto_e_interactive_sao_suportados(self):
        self.assertFalse(validar_midia("text"))
        self.assertFalse(validar_midia("interactive"))

    def test_midia_e_tipos_desconhecidos_sao_barrados(self):
        for tipo in ("image", "video", "audio", "document", "sticker", None):
            with self.subTest(tipo=tipo):
                self.assertTrue(validar_midia(tipo))


if __name__ == "__main__":
    unittest.main()
