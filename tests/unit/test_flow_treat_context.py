import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow import flow_treat_context as flow_treat_context_module
from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    TIPO_TRATAMENTO_NOME_INVALIDO,
)


def contexto_historico_base(resposta_bot=None):
    return {
        "id_conversa": 10,
        "retry_count": 2,
        "id_etapa_atual": 1,
        "id_etapa_cliente": 1,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


def contexto_validacao_base():
    return {
        "resultado": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
        "tipo_tratamento": TIPO_TRATAMENTO_NOME_INVALIDO,
    }


class FlowTreatContextTests(unittest.TestCase):
    def test_idempotente_nao_envia_meta_quando_resposta_ja_existe(self):
        resultado = flow_treat_context_module.flow_treat_context(
            contexto_historico_base(
                resposta_bot={
                    "id_mensagem": 99,
                    "id_hash_msg": "wamid.bot.existente",
                    "id_etapa": 1,
                }
            ),
            contexto_validacao_base(),
        )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.existente")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertTrue(resultado["tratamento"])
        self.assertTrue(resultado["atualizar_conversa"])

    def test_nome_invalido_chama_sender_de_contexto(self):
        chamadas = []

        def fake_sender(
            cliente_telefone,
            phone_id_unidade,
            id_etapa,
        ):
            chamadas.append((
                cliente_telefone,
                phone_id_unidade,
                id_etapa,
            ))
            return {
                "enviou": True,
                "resposta_ja_existia": False,
                "mensagem_bot": "mensagem de contexto",
                "id_hash_msg_bot": "wamid.bot.contexto",
                "id_etapa_resultante": id_etapa,
                "tipo_mensagem": "text",
                "tratamento": True,
                "tipo_tratamento": TIPO_TRATAMENTO_NOME_INVALIDO,
                "atualizar_conversa": True,
            }

        with patch.object(
            flow_treat_context_module,
            "sender_tratamento_contexto_nome_invalido",
            fake_sender,
        ):
            resultado = flow_treat_context_module.flow_treat_context(
                contexto_historico_base(),
                contexto_validacao_base(),
            )

        self.assertEqual(chamadas, [("5571999999999", "123456", 1)])
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertTrue(resultado["atualizar_conversa"])

    def test_tratamento_nao_implementado_falha_explicitamente(self):
        with self.assertRaises(NotImplementedError):
            flow_treat_context_module.flow_treat_context(
                contexto_historico_base(),
                {
                    "resultado": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
                    "tipo_tratamento": "outro_contexto",
                },
            )


if __name__ == "__main__":
    unittest.main()
