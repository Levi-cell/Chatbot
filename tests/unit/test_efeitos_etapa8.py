import unittest
from unittest.mock import ANY, patch

from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_EMAIL_VALIDO,
)
from workers.worker_flow.transacoes import efeitos_transicao as efeitos


def contexto_historico(texto="cliente@exemplo.com"):
    return {
        "id_conversa": 10,
        "id_cliente": 20,
        "id_etapa_origem_transicao": 8,
        "texto_cliente_atual": texto,
    }


class EfeitosEtapa8Tests(unittest.TestCase):
    def test_email_do_contexto_envio_e_persistido(self):
        with patch.object(
            efeitos,
            "atualizar_email_cliente",
        ) as atualizar:
            resultado = (
                efeitos.atualizar_banco_conforme_transicao_de_etapa(
                    contexto_historico(),
                    {
                        "id_etapa_resultante": 9,
                        "evento_transicao": EVENTO_EMAIL_VALIDO,
                        "email_cliente": "novo@exemplo.com",
                    },
                    object(),
                )
            )

        atualizar.assert_called_once_with(
            20,
            "novo@exemplo.com",
            ANY,
        )
        self.assertTrue(resultado["cliente_email_atualizado"])

    def test_retry_reconstroi_email_da_mensagem_original(self):
        cursor = object()

        with patch.object(
            efeitos,
            "atualizar_email_cliente",
        ) as atualizar:
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico(
                    "Meu email é retry@Exemplo.COM."
                ),
                {
                    "id_etapa_resultante": 9,
                    "evento_transicao": EVENTO_EMAIL_VALIDO,
                },
                cursor,
            )

        atualizar.assert_called_once_with(
            20,
            "retry@exemplo.com",
            cursor,
        )

    def test_retry_falha_se_email_nao_puder_ser_reconstruido(self):
        with self.assertRaisesRegex(
            ValueError,
            "Email nao reconstruido",
        ):
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico("email sem arroba"),
                {
                    "id_etapa_resultante": 9,
                    "evento_transicao": EVENTO_EMAIL_VALIDO,
                },
                object(),
            )

    def test_destino_incompativel_falha(self):
        with self.assertRaises(ValueError):
            efeitos.atualizar_banco_conforme_transicao_de_etapa(
                contexto_historico(),
                {
                    "id_etapa_resultante": 8,
                    "evento_transicao": EVENTO_EMAIL_VALIDO,
                },
                object(),
            )


if __name__ == "__main__":
    unittest.main()
