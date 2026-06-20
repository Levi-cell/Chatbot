import unittest

from workers.worker_flow.valida_historico import _resolver_etapa_resposta


class FluxoInicioMidiaTests(unittest.TestCase):
    def test_interacao_apos_midia_inicial_solicita_etapa_um(self):
        contexto_conversa = {
            "id_etapa_atual": None,
        }

        etapa_resposta = _resolver_etapa_resposta(contexto_conversa)

        self.assertEqual(etapa_resposta, 1)

    def test_interacao_apos_midia_em_etapa_persistida_solicita_proxima(self):
        for etapa_atual in range(1, 7):
            with self.subTest(etapa_atual=etapa_atual):
                contexto_conversa = {
                    "id_etapa_atual": etapa_atual,
                }

                etapa_resposta = _resolver_etapa_resposta(contexto_conversa)

                self.assertEqual(etapa_resposta, etapa_atual + 1)

    def test_etapa_final_nao_ultrapassa_limite(self):
        contexto_conversa = {
            "id_etapa_atual": 7,
        }

        etapa_resposta = _resolver_etapa_resposta(contexto_conversa)

        self.assertEqual(etapa_resposta, 7)


if __name__ == "__main__":
    unittest.main()
