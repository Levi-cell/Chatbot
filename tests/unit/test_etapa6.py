import unittest

from workers.worker_flow.response_flow.etapas import (
    etapa6_worker as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_CLIENTE_RETORNOU,
)


def contexto_historico(tipo_mensagem, texto):
    return {
        "id_conversa": 10,
        "id_etapa_atual": 6,
        "id_etapa_cliente": 6,
        "id_etapa_origem_transicao": 6,
        "transicoes_permitidas": {
            EVENTO_CLIENTE_RETORNOU: 7,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 60,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        },
    }


class Etapa6WorkerTests(unittest.TestCase):
    def test_qualquer_tipo_de_mensagem_avanca_para_etapa7(self):
        casos = (
            ("text", "oi"),
            ("text", "quanto custa?"),
            ("image", ""),
            ("audio", ""),
            ("interactive", "qualquer botão"),
        )

        for tipo_mensagem, texto in casos:
            with self.subTest(tipo_mensagem=tipo_mensagem):
                resultado = etapa_module.resolve_etapa6(
                    contexto_historico(tipo_mensagem, texto)
                )

                self.assertTrue(resultado["envio_simulado"])
                self.assertEqual(resultado["id_etapa_resultante"], 7)
                self.assertEqual(
                    resultado["evento_transicao"],
                    EVENTO_CLIENTE_RETORNOU,
                )
                self.assertNotIn("tratamento", resultado)


if __name__ == "__main__":
    unittest.main()
