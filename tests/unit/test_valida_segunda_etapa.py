import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_segunda_etapa import (
    OPCAO_PARA_MIM,
    OPCAO_PARA_OUTRA_PESSOA,
    validar_segunda_etapa,
)


class ValidaSegundaEtapaTests(unittest.TestCase):
    def test_aceita_somente_as_duas_opcoes_normalizadas(self):
        casos = [
            ("Para mim", OPCAO_PARA_MIM),
            (" para mim ", OPCAO_PARA_MIM),
            ("PARA MIM", OPCAO_PARA_MIM),
            ("Para outra pessoa", OPCAO_PARA_OUTRA_PESSOA),
            ("  para   outra pessoa  ", OPCAO_PARA_OUTRA_PESSOA),
        ]

        for texto, esperado in casos:
            with self.subTest(texto=texto):
                self.assertEqual(
                    validar_segunda_etapa(texto),
                    esperado,
                )

    def test_rejeita_variacoes_fora_das_opcoes(self):
        casos = [
            None,
            "",
            "eu quero para meu primo",
            "para meu filho",
            "outra pessoa",
            "para mim.",
            "para outra pessoa!",
        ]

        for texto in casos:
            with self.subTest(texto=texto):
                self.assertIsNone(validar_segunda_etapa(texto))


if __name__ == "__main__":
    unittest.main()
