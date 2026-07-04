import unittest

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos


class EfeitosEtapa7Tests(unittest.TestCase):
    def _executar(self, evento, destino):
        return efeitos.atualizar_banco_conforme_transicao_de_etapa(
            {
                "id_conversa": 10,
                "id_etapa_origem_transicao": 7,
            },
            {
                "id_etapa_resultante": destino,
                "evento_transicao": evento,
            },
            object(),
        )

    def test_confirmacao_persiste_transicao_sete_para_oito(self):
        resultado = self._executar(EVENTO_RETORNO_CONFIRMADO, 8)

        self.assertTrue(resultado["decisao_retorno_persistida"])
        self.assertEqual(
            resultado["decisao_retorno"],
            EVENTO_RETORNO_CONFIRMADO,
        )

    def test_adiamento_persiste_transicao_sete_para_seis(self):
        resultado = self._executar(EVENTO_RETORNO_ADIADO, 6)

        self.assertTrue(resultado["decisao_retorno_persistida"])
        self.assertEqual(
            resultado["decisao_retorno"],
            EVENTO_RETORNO_ADIADO,
        )

    def test_destino_incompativel_falha(self):
        with self.assertRaises(ValueError):
            self._executar(EVENTO_RETORNO_CONFIRMADO, 6)


if __name__ == "__main__":
    unittest.main()
