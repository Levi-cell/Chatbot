import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa5 import (
    OPCAO_QUERO_AGENDAR,
    OPCAO_TALVEZ_MAIS_TARDE,
    validar_etapa5,
)


class ValidaEtapa5Tests(unittest.TestCase):
    def test_respostas_positivas_aceitas(self):
        respostas = (
            "Quero agendar",
            "sim",
            "SIM!",
            "bora",
            "bora lá",
            "eu quero",
            "quero muito",
            "vamos sim",
            "vamos agendar",
            "com certeza",
            "pode marcar",
            "tenho interesse",
            "estou interessada",
            "marca pra mim",
            "fechado",
        )

        for resposta in respostas:
            with self.subTest(resposta=resposta):
                self.assertEqual(
                    validar_etapa5(resposta),
                    OPCAO_QUERO_AGENDAR,
                )

    def test_talvez_mais_tarde_exato_adia(self):
        respostas = (
            "Talvez mais tarde",
            "  talvez   mais tarde  ",
            "TALVEZ MAIS TARDE!",
        )

        for resposta in respostas:
            with self.subTest(resposta=resposta):
                self.assertEqual(
                    validar_etapa5(resposta),
                    OPCAO_TALVEZ_MAIS_TARDE,
                )

    def test_negacao_prevalece_sobre_palavra_positiva(self):
        respostas = (
            "não",
            "nao quero",
            "sim, mas não agora",
            "quero, mas não posso",
            "vamos não",
            "nunca",
            "jamais",
            "nem pensar",
            "de jeito nenhum",
        )

        for resposta in respostas:
            with self.subTest(resposta=resposta):
                self.assertIsNone(validar_etapa5(resposta))

    def test_texto_sem_intencao_positiva_e_invalido(self):
        for resposta in (None, "", "banana azul", "talvez amanhã"):
            with self.subTest(resposta=resposta):
                self.assertIsNone(validar_etapa5(resposta))


if __name__ == "__main__":
    unittest.main()
