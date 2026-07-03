import unittest

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos


def contexto_historico():
    return {
        "id_conversa": 10,
        "id_etapa_origem_transicao": 5,
    }


class EfeitosEtapa5Tests(unittest.TestCase):
    def test_oferta_aceita_confirma_transicao_cinco_para_oito(self):
        resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
            contexto_historico(),
            {
                "id_etapa_resultante": 8,
                "evento_transicao": EVENTO_OFERTA_ACEITA,
            },
            object(),
        )

        self.assertTrue(resultado["decisao_oferta_persistida"])
        self.assertEqual(
            resultado["decisao_oferta"],
            EVENTO_OFERTA_ACEITA,
        )

    def test_oferta_adiada_confirma_transicao_cinco_para_seis(self):
        resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
            contexto_historico(),
            {
                "id_etapa_resultante": 6,
                "evento_transicao": EVENTO_OFERTA_ADIADA,
            },
            object(),
        )

        self.assertTrue(resultado["decisao_oferta_persistida"])
        self.assertEqual(
            resultado["decisao_oferta"],
            EVENTO_OFERTA_ADIADA,
        )

    def test_destino_incompativel_falha(self):
        with self.assertRaises(ValueError):
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico(),
                {
                    "id_etapa_resultante": 6,
                    "evento_transicao": EVENTO_OFERTA_ACEITA,
                },
                object(),
            )


if __name__ == "__main__":
    unittest.main()
