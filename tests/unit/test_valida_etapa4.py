import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa4 import (
    MOTIVO_FORMATO_INVALIDO,
    MOTIVO_FORA_INTERVALO,
    MOTIVO_MULTIPLAS_IDADES,
    MOTIVO_SEM_IDADE,
    STATUS_IDADE_ACIMA_LIMITE,
    STATUS_IDADE_INVALIDA,
    STATUS_IDADE_VALIDA,
    validar_idade,
)


class ValidaEtapa4Tests(unittest.TestCase):
    def test_extrai_uma_idade_numerica(self):
        casos = {
            "25": 25,
            "Eu tenho 25 anos de idade": 25,
            "Minha idade é 25 anos": 25,
            "Eu tenho 25": 25,
            "Ela tem 7": 7,
            "Alice tem 7 anos": 7,
        }

        for texto, idade in casos.items():
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertEqual(resultado.status, STATUS_IDADE_VALIDA)
                self.assertEqual(resultado.idade, idade)

    def test_extrai_uma_idade_por_extenso(self):
        casos = {
            "um ano de idade": 1,
            "dezoito": 18,
            "eu tenho trinta e nove anos": 39,
            "noventa e nove": 99,
        }

        for texto, idade in casos.items():
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertTrue(resultado.valida)
                self.assertEqual(resultado.idade, idade)

    def test_idade_acima_de_99_recebe_classificacao_propria(self):
        casos = {
            "100": 100,
            "105 anos": 105,
            "cem anos": 100,
            "cento e cinco": 105,
        }

        for texto, idade in casos.items():
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertEqual(
                    resultado.status,
                    STATUS_IDADE_ACIMA_LIMITE,
                )
                self.assertEqual(resultado.idade, idade)

    def test_duas_idades_sao_invalidas(self):
        casos = (
            "eu tenho 39 anos e meu filho tem 7",
            "trinta e nove e onze",
            "39 e onze",
            "39 e trinta e nove",
        )

        for texto in casos:
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertEqual(resultado.status, STATUS_IDADE_INVALIDA)
                self.assertEqual(
                    resultado.motivo,
                    MOTIVO_MULTIPLAS_IDADES,
                )

    def test_ausente_zero_negativa_e_decimal_sao_invalidas(self):
        casos = {
            "": MOTIVO_SEM_IDADE,
            "não sei": MOTIVO_SEM_IDADE,
            "0": MOTIVO_FORA_INTERVALO,
            "-1": MOTIVO_FORMATO_INVALIDO,
            "menos de 18": MOTIVO_FORMATO_INVALIDO,
            "menos cinco": MOTIVO_FORMATO_INVALIDO,
            "18,5": MOTIVO_FORMATO_INVALIDO,
            "dezoito vírgula cinco": MOTIVO_FORMATO_INVALIDO,
            "dezoito anos e meio": MOTIVO_FORMATO_INVALIDO,
        }

        for texto, motivo in casos.items():
            with self.subTest(texto=texto):
                resultado = validar_idade(texto)
                self.assertEqual(resultado.status, STATUS_IDADE_INVALIDA)
                self.assertEqual(resultado.motivo, motivo)


if __name__ == "__main__":
    unittest.main()
