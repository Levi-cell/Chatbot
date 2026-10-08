from __future__ import annotations

import unittest

from workers.worker_flow.response_flow.etapas.validadores_contexto.valida_etapa7 import (
    validar_etapa7,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)


class ValidarEtapa7Tests(unittest.TestCase):
    def test_confirmacoes_curtas_e_acoes_claras_continuam_aceitas(self) -> None:
        confirmacoes = (
            "Sim, quero",
            "quero",
            "Quero sim",
            "Sim, gostaria",
            "quero agendar",
            "sim, quero agendar",
            "pode agendar",
            "vamos agendar",
            "aceito",
            "topo",
            "  SIM,   QUERO! ",
        )

        for resposta in confirmacoes:
            with self.subTest(resposta=resposta):
                self.assertEqual(
                    validar_etapa7(resposta),
                    EVENTO_OFERTA_ACEITA,
                )

    def test_pedidos_de_informacao_nao_sao_confundidos_com_aceite(self) -> None:
        pedidos = (
            "quero mais informações",
            "Quero mais informacoes",
            "sim, quero mais informações",
            "gostaria de mais informações",
            "gostaria de receber mais informações",
            "quero saber mais",
            "sim quero saber mais?",
            "quero saber quais são os horários",
            "gostaria de saber como funciona",
            "gostaria de entender melhor",
            "quero entender como funciona",
            "quero tirar uma dúvida",
            "gostaria de tirar uma duvida",
            "quero fazer uma pergunta",
            "gostaria de perguntar uma coisa",
        )

        for resposta in pedidos:
            with self.subTest(resposta=resposta):
                self.assertIsNone(validar_etapa7(resposta))

    def test_respostas_negativas_ou_ambiguas_continuam_invalidas(self) -> None:
        respostas = (
            "não quero",
            "não tenho interesse",
            "quero não",
            "talvez",
            "pode me explicar?",
            "como funciona?",
            "",
            None,
            123,
        )

        for resposta in respostas:
            with self.subTest(resposta=resposta):
                self.assertIsNone(validar_etapa7(resposta))

    def test_botao_de_adiamento_mantem_evento_proprio(self) -> None:
        self.assertEqual(
            validar_etapa7("Talvez mais tarde"),
            EVENTO_OFERTA_ADIADA,
        )


if __name__ == "__main__":
    unittest.main()
