import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    etapa4_worker as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_IDADE_VALIDA,
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
        "id_etapa_atual": 4,
        "id_etapa_cliente": 4,
        "id_etapa_origem_transicao": 4,
        "transicoes_permitidas": {EVENTO_IDADE_VALIDA: 5},
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "status_dependente": status_dependente,
        "nome_cliente": "Edcarlos",
        "nome_dependente": "Alice" if status_dependente else None,
        "numero_comercial_unidade": "557536321234",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 40,
            "cliente_telefone": "5575999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno_etapa4(**extra):
    resultado = {
        "enviou": True,
        "id_hash_msg_bot": "wamid.etapa4",
        "id_etapa_resultante": 4,
    }
    resultado.update(extra)
    return resultado


class Etapa4WorkerTests(unittest.TestCase):
    def test_idade_invalida_cliente_trata_sem_avancar(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_cliente_contexto_idade_invalida",
            return_value=retorno_etapa4(tratamento=True),
        ) as sender:
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("não sei")
            )

        sender.assert_called_once_with("5575999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertNotIn("evento_transicao", resultado)

    def test_idade_invalida_dependente_usa_mensagem_especifica(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_dependente_contexto_idade_invalida",
            return_value=retorno_etapa4(tratamento=True),
        ) as sender:
            resultado = etapa_module.resolve_etapa4(
                contexto_historico(
                    "39 e 7",
                    status_dependente=True,
                )
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "Alice",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertNotIn("evento_transicao", resultado)

    def test_cliente_menor_de_18_encerra(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_cliente_menor_18",
            return_value=retorno_etapa4(),
        ):
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("17")
            )

        self.assertTrue(resultado["encerrar_atendimento"])
        self.assertEqual(
            resultado["motivo_encerramento"],
            etapa_module.MOTIVO_CLIENTE_MENOR_18,
        )
        self.assertFalse(resultado["excluir_dependente"])

    def test_dependente_menor_de_5_encerra_e_exclui_dependente(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_dependente_menor_5",
            return_value=retorno_etapa4(),
        ):
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("4", status_dependente=True)
            )

        self.assertTrue(resultado["encerrar_atendimento"])
        self.assertTrue(resultado["excluir_dependente"])

    def test_idade_acima_de_99_usa_numero_comercial_e_encerra(self):
        with patch.object(
            etapa_module,
            "enviar_etapa4_idade_acima_99",
            return_value=retorno_etapa4(),
        ) as sender:
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("100")
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "557536321234",
        )
        self.assertTrue(resultado["encerrar_atendimento"])

    def test_cliente_18_avanca_para_etapa5(self):
        with patch.object(
            etapa_module,
            "enviar_etapa5_cliente",
            return_value={
                "enviou": True,
                "id_hash_msg_bot": "wamid.etapa5",
                "id_etapa_resultante": 5,
            },
        ) as sender:
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("18")
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "Edcarlos",
        )
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(resultado["id_etapa_resultante"], 5)
        self.assertEqual(resultado["evento_transicao"], EVENTO_IDADE_VALIDA)
        self.assertEqual(resultado["idade_aluno"], 18)

    def test_dependente_5_avanca_para_etapa5(self):
        with patch.object(
            etapa_module,
            "enviar_etapa5_dependente",
            return_value={
                "enviou": True,
                "id_hash_msg_bot": "wamid.etapa5",
                "id_etapa_resultante": 5,
            },
        ) as sender:
            resultado = etapa_module.resolve_etapa4(
                contexto_historico("5", status_dependente=True)
            )

        sender.assert_called_once_with(
            "5575999999999",
            "123456",
            "Alice",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 5)
        self.assertEqual(resultado["idade_aluno"], 5)


if __name__ == "__main__":
    unittest.main()
