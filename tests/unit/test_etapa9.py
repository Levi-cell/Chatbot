import unittest

from workers.worker_flow.response_flow.etapas import (
    resolver_etapa9 as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_TRIAGEM_INICIADA,
)


def contexto_historico(
    *,
    tipo_mensagem="text",
    texto="qualquer interação",
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": 9,
        "id_etapa_cliente": 9,
        "id_etapa_origem_transicao": 9,
        "transicoes_permitidas": {
            EVENTO_TRIAGEM_INICIADA: 10,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 90,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        },
    }


class Etapa9ResolverTests(unittest.TestCase):
    def test_botao_inicia_triagem(self):
        resultado = etapa_module.resolve_etapa9(
            contexto_historico(
                tipo_mensagem="interactive",
                texto="Iniciar triagem",
            )
        )

        self.assertTrue(resultado["envio_simulado"])
        self.assertEqual(resultado["id_etapa_resultante"], 10)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_TRIAGEM_INICIADA,
        )

    def test_qualquer_interacao_inicia_triagem(self):
        for tipo_mensagem in (
            "text",
            "image",
            "audio",
            "document",
        ):
            with self.subTest(tipo_mensagem=tipo_mensagem):
                resultado = etapa_module.resolve_etapa9(
                    contexto_historico(
                        tipo_mensagem=tipo_mensagem,
                        texto="quanto custa?",
                    )
                )

                self.assertEqual(
                    resultado["id_etapa_resultante"],
                    10,
                )
                self.assertNotIn("tratamento", resultado)


if __name__ == "__main__":
    unittest.main()
