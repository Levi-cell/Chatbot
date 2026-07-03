import unittest

from workers.worker_flow.response_flow.transicoes.contexto_transicao import (
    prever_etapa_resposta,
)


class FluxoInicioMidiaTests(unittest.TestCase):
    def test_conversa_nova_sem_etapa_preve_etapa1(self):
        contexto_conversa = {
            "id_etapa_atual": None,
        }

        etapa_resposta = prever_etapa_resposta(
            contexto_conversa["id_etapa_atual"],
            {},
            etapa_inicial=1,
        )

        self.assertEqual(etapa_resposta, 1)

    def test_origem_com_destino_unico_preve_destino_do_mapa(self):
        contexto_conversa = {
            "id_etapa_atual": 1,
        }

        etapa_resposta = prever_etapa_resposta(
            contexto_conversa["id_etapa_atual"],
            {"nome_cliente_valido": 2},
            etapa_inicial=1,
        )

        self.assertEqual(etapa_resposta, 2)

    def test_origem_com_ramificacao_nao_inventa_destino(self):
        contexto_conversa = {
            "id_etapa_atual": 2,
        }

        etapa_resposta = prever_etapa_resposta(
            contexto_conversa["id_etapa_atual"],
            {
                "para_mim": 4,
                "para_outra_pessoa": 3,
            },
            etapa_inicial=1,
        )

        self.assertIsNone(etapa_resposta)

    def test_origem_sem_transicao_nao_usa_soma(self):
        contexto_conversa = {
            "id_etapa_atual": 10,
        }

        etapa_resposta = prever_etapa_resposta(
            contexto_conversa["id_etapa_atual"],
            {},
            etapa_inicial=1,
        )

        self.assertIsNone(etapa_resposta)


if __name__ == "__main__":
    unittest.main()
