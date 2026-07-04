import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    resolver_etapa8 as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_EMAIL_VALIDO,
)


def contexto_historico(
    texto,
    *,
    tipo_mensagem="text",
):
    return {
        "id_conversa": 10,
        "id_cliente": 20,
        "id_unidade": 30,
        "id_etapa_atual": 8,
        "id_etapa_cliente": 8,
        "id_etapa_origem_transicao": 8,
        "transicoes_permitidas": {
            EVENTO_EMAIL_VALIDO: 9,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 80,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno_tratamento_etapa8(tipo_tratamento):
    return {
        "enviou": True,
        "id_hash_msg_bot": "wamid.etapa8",
        "id_etapa_resultante": 8,
        "tratamento": True,
        "tipo_tratamento": tipo_tratamento,
    }


class Etapa8ResolverTests(unittest.TestCase):
    def test_email_valido_e_extraido_antes_de_avancar(self):
        resultado = etapa_module.resolve_etapa8(
            contexto_historico(
                "Meu email é cliente+agenda@Exemplo.COM.br."
            )
        )

        self.assertTrue(resultado["envio_simulado"])
        self.assertEqual(resultado["id_etapa_resultante"], 9)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_EMAIL_VALIDO,
        )
        self.assertEqual(
            resultado["email_cliente"],
            "cliente+agenda@exemplo.com.br",
        )

    def test_email_invalido_trata_e_mantem_etapa8(self):
        with patch.object(
            etapa_module,
            "enviar_etapa8_contexto_email_invalido",
            return_value=retorno_tratamento_etapa8(
                "email_invalido"
            ),
        ) as sender:
            resultado = etapa_module.resolve_etapa8(
                contexto_historico("esqueci o arroba gmail.com")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 8)
        self.assertNotIn("evento_transicao", resultado)

    def test_midia_trata_e_mantem_etapa8(self):
        with patch.object(
            etapa_module,
            "enviar_etapa8_midia",
            return_value=retorno_tratamento_etapa8(
                "tipo_mensagem_nao_suportado"
            ),
        ) as sender:
            resultado = etapa_module.resolve_etapa8(
                contexto_historico("", tipo_mensagem="image")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 8)
        self.assertNotIn("evento_transicao", resultado)

    def test_financeiro_trata_e_mantem_etapa8(self):
        with patch.object(
            etapa_module,
            "enviar_etapa8_financeiro",
            return_value=retorno_tratamento_etapa8(
                "pergunta_financeira"
            ),
        ) as sender:
            resultado = etapa_module.resolve_etapa8(
                contexto_historico("quanto custa?")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 8)
        self.assertNotIn("evento_transicao", resultado)


if __name__ == "__main__":
    unittest.main()
