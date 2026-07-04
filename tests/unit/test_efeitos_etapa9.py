import unittest

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_TRIAGEM_INICIADA,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos


class EfeitosEtapa9Tests(unittest.TestCase):
    def test_confirma_inicio_da_triagem_sem_dado_adicional(self):
        resultado = (
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                {
                    "id_conversa": 10,
                    "id_etapa_origem_transicao": 9,
                },
                {
                    "id_etapa_resultante": 10,
                    "evento_transicao": EVENTO_TRIAGEM_INICIADA,
                },
                object(),
            )
        )

        self.assertEqual(
            resultado,
            {
                "inicio_triagem_persistido": True,
                "evento_triagem": EVENTO_TRIAGEM_INICIADA,
            },
        )

    def test_destino_incompativel_falha(self):
        with self.assertRaises(ValueError):
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                {
                    "id_conversa": 10,
                    "id_etapa_origem_transicao": 9,
                },
                {
                    "id_etapa_resultante": 9,
                    "evento_transicao": EVENTO_TRIAGEM_INICIADA,
                },
                object(),
            )


if __name__ == "__main__":
    unittest.main()
