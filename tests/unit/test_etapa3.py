import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow.etapas import (
    resolver_etapa3 as etapa_module,
)
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_NOME_DEPENDENTE_VALIDO,
)
from workers.worker_flow.response_flow.transicoes.resolver_transicao import (
    TransicaoEtapaInvalida,
)


def contexto_historico(
    *,
    tipo_mensagem="text",
    texto="Alice",
    transicoes=None,
):
    if transicoes is None:
        transicoes = {
            EVENTO_NOME_DEPENDENTE_VALIDO: 4,
        }

    return {
        "id_conversa": 10,
        "id_etapa_atual": 3,
        "id_etapa_cliente": 3,
        "id_etapa_resposta": 4,
        "id_etapa_origem_transicao": 3,
        "transicoes_permitidas": transicoes,
        "tipo_mensagem_atual": tipo_mensagem,
        "texto_cliente_atual": texto,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
    }


def retorno_tratamento(nome):
    return {
        "nome": nome,
        "enviou": True,
        "resposta_ja_existia": False,
        "id_hash_msg_bot": f"wamid.{nome}",
        "id_etapa_resultante": 3,
        "tratamento": True,
    }


class Etapa3WorkerTests(unittest.TestCase):
    def test_midia_reenvia_etapa3_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa3_midia",
            return_value=retorno_tratamento("midia_etapa3"),
        ) as sender:
            resultado = etapa_module.resolve_etapa3(
                contexto_historico(tipo_mensagem="image", texto="")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertTrue(resultado["tratamento"])

    def test_financeiro_reenvia_etapa3_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa3_financeiro",
            return_value=retorno_tratamento("financeiro_etapa3"),
        ) as sender:
            resultado = etapa_module.resolve_etapa3(
                contexto_historico(texto="quanto custa?")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertTrue(resultado["tratamento"])

    def test_midia_tem_prioridade_sobre_financeiro(self):
        with (
            patch.object(
                etapa_module,
                "enviar_etapa3_midia",
                return_value=retorno_tratamento("midia_etapa3"),
            ) as sender_midia,
            patch.object(
                etapa_module,
                "enviar_etapa3_financeiro",
            ) as sender_financeiro,
        ):
            etapa_module.resolve_etapa3(
                contexto_historico(
                    tipo_mensagem="image",
                    texto="quanto custa?",
                )
            )

        sender_midia.assert_called_once_with("5571999999999", "123456")
        sender_financeiro.assert_not_called()

    def test_nome_invalido_reenvia_etapa3_com_tratamento(self):
        with patch.object(
            etapa_module,
            "enviar_etapa3_contexto_nome_invalido",
            return_value=retorno_tratamento("nome_invalido_etapa3"),
        ) as sender:
            resultado = etapa_module.resolve_etapa3(
                contexto_historico(texto="Alice99")
            )

        sender.assert_called_once_with("5571999999999", "123456")
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertTrue(resultado["tratamento"])

    def test_nome_valido_transiciona_para_etapa4(self):
        contexto_sender = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.etapa4",
            "id_etapa_resultante": 4,
        }

        with patch.object(
            etapa_module,
            "enviar_etapa4_dependente",
            return_value=contexto_sender,
        ) as sender:
            resultado = etapa_module.resolve_etapa3(
                contexto_historico(
                    texto="O nome da minha filha é Aline Braga"
                )
            )

        sender.assert_called_once_with(
            "5571999999999",
            "123456",
            "Aline",
        )
        self.assertNotIn("envio_simulado", resultado)
        self.assertEqual(resultado["id_etapa_resultante"], 4)
        self.assertEqual(
            resultado["evento_transicao"],
            EVENTO_NOME_DEPENDENTE_VALIDO,
        )
        self.assertEqual(resultado["primeiro_nome_dependente"], "Aline")

    def test_mapa_sem_aresta_recusa_avanco(self):
        with self.assertRaises(TransicaoEtapaInvalida):
            etapa_module.resolve_etapa3(
                contexto_historico(
                    texto="Alice",
                    transicoes={},
                )
            )


if __name__ == "__main__":
    unittest.main()
