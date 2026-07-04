import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa7 import (
    validar_etapa7,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)


class ValidaEtapa7Tests(unittest.TestCase):
    def test_respostas_positivas_produzem_retorno_confirmado(self):
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
                    validar_etapa7(resposta),
                    EVENTO_RETORNO_CONFIRMADO,
                )

    def test_talvez_mais_tarde_exato_produz_retorno_adiado(self):
        respostas = (
            "Talvez mais tarde",
            "  talvez   mais tarde  ",
            "TALVEZ MAIS TARDE!",
        )

        for resposta in respostas:
            with self.subTest(resposta=resposta):
                self.assertEqual(
                    validar_etapa7(resposta),
                    EVENTO_RETORNO_ADIADO,
                )

    def test_negacao_ou_texto_desconhecido_nao_produz_evento(self):
        respostas = (
            None,
            "",
            "banana azul",
            "talvez amanhã",
            "talvez mais tarde eu veja",
            "não",
            "nao quero",
            "sim, mas não agora",
            "quero, mas não posso",
            "nunca",
            "jamais",
            "nem pensar",
            "de jeito nenhum",
        )

        for resposta in respostas:
            with self.subTest(resposta=resposta):
                self.assertIsNone(validar_etapa7(resposta))


if __name__ == "__main__":
    unittest.main()
