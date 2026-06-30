import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    segunda_etapa as etapa_module,
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
        "id_etapa_resposta": 3,
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


class SegundaEtapaTests(unittest.TestCase):
    def test_etapa_dois_com_midia_reenvia_etapa_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_segunda_etapa_midia",
            return_value=retorno("midia_etapa_2"),
        ) as sender:
            resultado = etapa_module.resolve_segunda_etapa(
                contexto_historico(tipo_mensagem="image", texto="")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "midia_etapa_2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_etapa_dois_com_financeiro_reenvia_etapa_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_segunda_etapa_financeiro",
            return_value=retorno("financeiro_etapa_2"),
        ) as sender:
            resultado = etapa_module.resolve_segunda_etapa(
                contexto_historico(texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["nome"], "financeiro_etapa_2")
        self.assertEqual(resultado["id_etapa_resultante"], 2)

    def test_midia_tem_prioridade_sobre_texto_financeiro(self):
        with (
            patch.object(
                etapa_module,
                "enviar_segunda_etapa_midia",
                return_value=retorno("midia_etapa_2"),
            ) as sender_midia,
            patch.object(
                etapa_module,
                "enviar_segunda_etapa_financeiro",
            ) as sender_financeiro,
        ):
            etapa_module.resolve_segunda_etapa(
                contexto_historico(
                    tipo_mensagem="image",
                    texto="quanto custa?",
                )
            )

        sender_midia.assert_called_once_with("5571999999999", "123456")
        sender_financeiro.assert_not_called()

    def test_contexto_da_etapa_dois_permanece_pendente(self):
        with self.assertRaisesRegex(
            NotImplementedError,
            "Validacao das opcoes da etapa 2",
        ):
            etapa_module.resolve_segunda_etapa(
                contexto_historico(texto="Para mim")
            )


if __name__ == "__main__":
    unittest.main()
