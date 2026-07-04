import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa5 import (
    validar_etapa5,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)


class ValidaEtapa5Tests(unittest.TestCase):
    def test_respostas_positivas_produzem_oferta_aceita(self):
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
                    EVENTO_OFERTA_ACEITA,
                )

    def test_talvez_mais_tarde_exato_produz_oferta_adiada(self):
        respostas = (
            "Talvez mais tarde",
            "  talvez   mais tarde  ",
            "TALVEZ MAIS TARDE!",
        )

        for resposta in respostas:
            with self.subTest(resposta=resposta):
                self.assertEqual(
                    validar_etapa5(resposta),
                    EVENTO_OFERTA_ADIADA,
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
                self.assertIsNone(validar_etapa5(resposta))


if __name__ == "__main__":
    unittest.main()
