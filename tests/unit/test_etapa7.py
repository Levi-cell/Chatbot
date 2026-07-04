import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    resolver_etapa7 as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_RETORNO_ADIADO,
    EVENTO_RETORNO_CONFIRMADO,
)


def contexto_historico(
    texto,
    *,
    tipo_mensagem="text",
    status_dependente=False,
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": 7,
        "id_etapa_cliente": 7,
        "id_etapa_origem_transicao": 7,
        "transicoes_permitidas": {
            EVENTO_RETORNO_CONFIRMADO: 8,
            EVENTO_RETORNO_ADIADO: 6,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
        "nome_cliente": "Edcarlos",
        "nome_dependente": "Alice" if status_dependente else None,
        "link_instagram_unidade": "https://instagram.com/supera.saj/",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 70,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno_tratamento_etapa7(tipo_tratamento):
    return {
        "enviou": True,
        "id_hash_msg_bot": "wamid.etapa7",
        "id_etapa_resultante": 7,
        "tratamento": True,
        "tipo_tratamento": tipo_tratamento,
    }


class Etapa7WorkerTests(unittest.TestCase):
    def test_decisao_positiva_avanca_para_etapa8(self):
        with patch.object(
            etapa_module,
            "enviar_etapa8",
            return_value={
                "enviou": True,
                "id_hash_msg_bot": "wamid.etapa8",
                "id_etapa_resultante": 8,
            },
        ) as sender:
            resultado = etapa_module.resolve_etapa7(
                contexto_historico("bora agendar")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(resultado["id_etapa_resultante"], 8)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_RETORNO_CONFIRMADO,
        )

    def test_talvez_mais_tarde_volta_para_etapa6(self):
        with patch.object(
            etapa_module,
            "enviar_etapa6",
            return_value={
                "enviou": True,
                "id_hash_msg_bot": "wamid.etapa6",
                "id_etapa_resultante": 6,
            },
        ) as sender:
            resultado = etapa_module.resolve_etapa7(
                contexto_historico("Talvez mais tarde")
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "https://instagram.com/supera.saj/",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 6)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_RETORNO_ADIADO,
        )

    def test_negacao_trata_e_mantem_etapa7(self):
        with patch.object(
            etapa_module,
            "enviar_etapa7_cliente_contexto_invalido",
            return_value=retorno_tratamento_etapa7("opcao_invalida"),
        ) as sender:
            resultado = etapa_module.resolve_etapa7(
                contexto_historico("sim, mas não quero agora")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 7)
        self.assertNotIn("evento_transicao", resultado)

    def test_midia_dependente_usa_sender_especifico(self):
        with patch.object(
            etapa_module,
            "enviar_etapa7_dependente_midia",
            return_value=retorno_tratamento_etapa7(
                "tipo_mensagem_nao_suportado"
            ),
        ) as sender:
            resultado = etapa_module.resolve_etapa7(
                contexto_historico(
                    "",
                    tipo_mensagem="image",
                    status_dependente=True,
                )
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "Alice",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 7)

    def test_financeiro_dependente_tem_prioridade(self):
        with patch.object(
            etapa_module,
            "enviar_etapa7_dependente_financeiro",
            return_value=retorno_tratamento_etapa7(
                "pergunta_financeira"
            ),
        ) as sender:
            resultado = etapa_module.resolve_etapa7(
                contexto_historico(
                    "sim, mas quanto custa?",
                    status_dependente=True,
                )
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "Alice",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 7)
        self.assertNotIn("evento_transicao", resultado)


if __name__ == "__main__":
    unittest.main()
