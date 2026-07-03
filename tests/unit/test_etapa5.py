import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    etapa5_worker as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_OFERTA_ACEITA,
    EVENTO_OFERTA_ADIADA,
)


def contexto_historico(
    texto,
    *,
    tipo_mensagem="text",
    status_dependente=False,
):
    return {
        "id_conversa": 10,
        "id_cliente": 20,
        "id_unidade": 30,
        "id_etapa_atual": 5,
        "id_etapa_cliente": 5,
        "id_etapa_origem_transicao": 5,
        "transicoes_permitidas": {
            EVENTO_OFERTA_ACEITA: 8,
            EVENTO_OFERTA_ADIADA: 6,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
        "nome_cliente": "Edcarlos",
        "nome_dependente": "Alice" if status_dependente else None,
        "link_instagram_unidade": "https://instagram.com/supera.saj/",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 50,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno_tratamento_etapa5(tipo_tratamento):
    return {
        "enviou": True,
        "id_hash_msg_bot": "wamid.etapa5",
        "id_etapa_resultante": 5,
        "tratamento": True,
        "tipo_tratamento": tipo_tratamento,
    }


class Etapa5WorkerTests(unittest.TestCase):
    def test_quero_agendar_avanca_para_etapa8(self):
        resultado = etapa_module.resolve_etapa5(
            contexto_historico("quero muito")
        )

        self.assertTrue(resultado["envio_simulado"])
        self.assertEqual(resultado["id_etapa_resultante"], 8)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_OFERTA_ACEITA,
        )

    def test_talvez_mais_tarde_avanca_para_etapa6(self):
        with patch.object(
            etapa_module,
            "enviar_etapa6",
            return_value={
                "enviou": True,
                "id_hash_msg_bot": "wamid.etapa6",
                "id_etapa_resultante": 6,
            },
        ) as sender:
            resultado = etapa_module.resolve_etapa5(
                contexto_historico("Talvez mais tarde")
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "https://instagram.com/supera.saj/",
        )
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(resultado["id_etapa_resultante"], 6)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_OFERTA_ADIADA,
        )

    def test_negacao_trata_e_mantem_etapa5(self):
        with patch.object(
            etapa_module,
            "enviar_etapa5_cliente_contexto_invalido",
            return_value=retorno_tratamento_etapa5("opcao_invalida"),
        ) as sender:
            resultado = etapa_module.resolve_etapa5(
                contexto_historico("sim, mas não quero agora")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 5)
        self.assertNotIn("evento_transicao", resultado)

    def test_midia_dependente_usa_sender_especifico(self):
        with patch.object(
            etapa_module,
            "enviar_etapa5_dependente_midia",
            return_value=retorno_tratamento_etapa5(
                "tipo_mensagem_nao_suportado"
            ),
        ) as sender:
            resultado = etapa_module.resolve_etapa5(
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
        self.assertEqual(resultado["id_etapa_resultante"], 5)

    def test_financeiro_cliente_tem_prioridade_sobre_oferta(self):
        with patch.object(
            etapa_module,
            "enviar_etapa5_cliente_financeiro",
            return_value=retorno_tratamento_etapa5(
                "pergunta_financeira"
            ),
        ) as sender:
            resultado = etapa_module.resolve_etapa5(
                contexto_historico("sim, mas quanto custa?")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 5)
        self.assertNotIn("evento_transicao", resultado)


if __name__ == "__main__":
    unittest.main()
