import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    etapa2_worker as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


def contexto_historico(
    *,
    tipo_mensagem="text",
    texto="Para mim",
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": 2,
        "id_etapa_cliente": 2,
        "id_etapa_resposta": None,
        "id_etapa_origem_transicao": 2,
        "transicoes_permitidas": {
            EVENTO_PARA_MIM: 4,
            EVENTO_PARA_OUTRA_PESSOA: 3,
        },
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno(nome):
    return {
        "nome": nome,
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.{nome}",
        "id_etapa_resultante": 2,
        "tratamento": True,
    }


class Etapa2WorkerTests(unittest.TestCase):
    def test_etapa2_com_midia_reenvia_etapa_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2_midia",
            return_value=retorno("midia_etapa2"),
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(tipo_mensagem="image", texto="")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_etapa2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_etapa2_com_financeiro_reenvia_etapa_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2_financeiro",
            return_value=retorno("financeiro_etapa2"),
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_etapa2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_midia_tem_prioridade_sobre_texto_financeiro(self):
        with (
            patch.object(
                etapa_module,
                "enviar_etapa2_midia",
                return_value=retorno("midia_etapa2"),
            ) as sender_midia,
            patch.object(
                etapa_module,
                "enviar_etapa2_financeiro",
            ) as sender_financeiro,
        ):
            etapa_module.resolve_etapa2(
                contexto_historico(
                    tipo_mensagem="image",
                    texto="quanto custa?",
                )
            )

        sender_midia.assert_called_once_with("5571999999999", "123456")
        sender_financeiro.assert_not_called()

    def test_opcao_para_mim_envia_etapa4_sem_dependente(self):
        contexto_sender = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.etapa4",
            "id_etapa_resultante": 4,
        }

        with patch.object(
            etapa_module,
            "enviar_etapa4_cliente",
            return_value=contexto_sender,
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(texto="Para mim")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertEqual(resultado["opcao_atendimento"], "para_mim")
        self.assertEqual(resultado["evento_transicao"], EVENTO_PARA_MIM)
        self.assertFalse(resultado["status_dependente"])

    def test_opcao_para_outra_pessoa_interativa_envia_etapa3(self):
        contexto_sender = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.etapa3",
            "id_etapa_resultante": 3,
        }

        with patch.object(
            etapa_module,
            "enviar_etapa3",
            return_value=contexto_sender,
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(
                    tipo_mensagem="interactive",
                    texto="Para outra pessoa",
                )
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(
            resultado["opcao_atendimento"],
            "para_outra_pessoa",
        )
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_PARA_OUTRA_PESSOA,
        )
        self.assertTrue(resultado["status_dependente"])

    def test_opcao_invalida_reenvia_etapa2_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa2_contexto_opcao_invalida",
            return_value=retorno("contexto_etapa2"),
        ) as sender:
            resultado = etapa_module.resolve_etapa2(
                contexto_historico(texto="eu quero para meu primo")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "contexto_etapa2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)


if __name__ == "__main__":
    unittest.main()
