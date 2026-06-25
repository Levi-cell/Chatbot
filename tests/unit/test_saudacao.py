import unittest
from datetime import datetime

from core.integrations.whatsapp.pywa_functions.saudacao import (
    FUSO_HORARIO_ATENDIMENTO,
    obter_saudacao_por_horario,
)


class SaudacaoTests(unittest.TestCase):
    def test_saudacao_por_faixa_de_horario(self):
        casos = (
            (datetime(2026, 6, 24, 8, tzinfo=FUSO_HORARIO_ATENDIMENTO), "Bom dia"),
            (datetime(2026, 6, 24, 14, tzinfo=FUSO_HORARIO_ATENDIMENTO), "Boa tarde"),
            (datetime(2026, 6, 24, 21, tzinfo=FUSO_HORARIO_ATENDIMENTO), "Boa noite"),
        )

        for agora, esperado in casos:
            with self.subTest(agora=agora):
                self.assertEqual(obter_saudacao_por_horario(agora), esperado)


if __name__ == "__main__":
    unittest.main()
