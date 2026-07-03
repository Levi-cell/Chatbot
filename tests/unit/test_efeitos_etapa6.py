import unittest

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_CLIENTE_RETORNOU,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos


class EfeitosEtapa6Tests(unittest.TestCase):
    def test_retorno_confirma_transicao_seis_para_sete(self):
        resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
            {
                "id_conversa": 10,
                "id_etapa_origem_transicao": 6,
            },
            {
                "id_etapa_resultante": 7,
                "evento_transicao": EVENTO_CLIENTE_RETORNOU,
            },
            object(),
        )

        self.assertTrue(resultado["retorno_cliente_persistido"])
        self.assertEqual(
            resultado["evento_retorno"],
            EVENTO_CLIENTE_RETORNOU,
        )

    def test_destino_incompativel_falha(self):
        with self.assertRaises(ValueError):
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                {
                    "id_conversa": 10,
                    "id_etapa_origem_transicao": 6,
                },
                {
                    "id_etapa_resultante": 8,
                    "evento_transicao": EVENTO_CLIENTE_RETORNOU,
                },
                object(),
            )


if __name__ == "__main__":
    unittest.main()
