import unittest
from unittest.mock import ANY, patch

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA,
    EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos


CASOS_TRIAGEM = (
    (12, 13, EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA),
    (13, 14, EVENTO_TRIAGEM_PERGUNTA_2_RESPONDIDA),
    (14, 15, EVENTO_TRIAGEM_PERGUNTA_3_RESPONDIDA),
    (15, 16, EVENTO_TRIAGEM_PERGUNTA_4_RESPONDIDA),
    (16, 17, EVENTO_TRIAGEM_PERGUNTA_5_RESPONDIDA),
    (17, 18, EVENTO_TRIAGEM_PERGUNTA_6_RESPONDIDA),
)


def contexto_historico(etapa, texto="Às vezes"):
    return {
        "id_conversa": 10,
        "id_etapa_origem_transicao": etapa,
        "texto_cliente_atual": texto,
        "tipo_mensagem_atual": "interactive",
        "mensagem_cliente_atual": {
            "id_mensagem": 900 + etapa,
        },
    }


class EfeitosTriagemTests(unittest.TestCase):
    def test_seis_respostas_sao_persistidas_na_etapa_de_origem(self):
        for etapa, destino, evento in CASOS_TRIAGEM:
            with self.subTest(etapa=etapa):
                with patch.object(
                    efeitos,
                    "registrar_resposta_triagem",
                    return_value={
                        "id_resposta_desafio": 30,
                        "resposta": "às vezes",
                        "id_historico_mensagem_cliente": 900 + etapa,
                        "inserido": True,
                    },
                ) as repositorio:
                    resultado = (
                        efeitos.atualizar_banco_conforme_transicao_de_etapa(
                            contexto_historico(etapa),
                            {
                                "id_etapa_resultante": destino,
                                "evento_transicao": evento,
                                "resposta_triagem": "às vezes",
                            },
                            object(),
                        )
                    )

                repositorio.assert_called_once_with(
                    10,
                    etapa,
                    "às vezes",
                    900 + etapa,
                    ANY,
                )
                self.assertTrue(
                    resultado["resposta_triagem_persistida"]
                )
                self.assertEqual(resultado["resposta"], "às vezes")

    def test_retry_reconstroi_resposta_pela_mensagem_original(self):
        with patch.object(
            efeitos,
            "registrar_resposta_triagem",
            return_value={
                "id_resposta_desafio": 30,
                "resposta": "frequentemente",
                "id_historico_mensagem_cliente": 910,
                "inserido": False,
            },
        ) as repositorio:
            resultado = efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico(12, texto="Frequentemente"),
                {
                    "id_etapa_resultante": 13,
                    "evento_transicao": (
                        EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA
                    ),
                },
                object(),
            )

        repositorio.assert_called_once_with(
            10,
            12,
            "frequentemente",
            912,
            ANY,
        )
        self.assertFalse(resultado["inserido"])

    def test_destino_incompativel_falha_antes_de_persistir(self):
        with patch.object(
            efeitos,
            "registrar_resposta_triagem",
        ) as repositorio:
            with self.assertRaises(ValueError):
                efeitos.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico(12),
                    {
                        "id_etapa_resultante": 14,
                        "evento_transicao": (
                            EVENTO_TRIAGEM_PERGUNTA_1_RESPONDIDA
                        ),
                        "resposta_triagem": "nunca",
                    },
                    object(),
                )

        repositorio.assert_not_called()


if __name__ == "__main__":
    unittest.main()
