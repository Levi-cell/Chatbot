import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.flow_sender as flow_sender_module


def contexto_historico_base(resposta_bot=None, etapa=1, retry=1):
    return {
        "id_conversa": 10,
        "id_etapa_resposta": etapa,
        "retry_count": retry,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


class FlowSenderTests(unittest.TestCase):
    def test_idempotente_nao_envia_meta_quando_resposta_ja_existe(self):
        def falhar_se_chamar(*_args, **_kwargs):
            raise AssertionError("sender_etapa1 nao deveria ser chamado")

        with patch.object(flow_sender_module, "sender_etapa1", falhar_se_chamar):
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(
                    resposta_bot={
                        "id_mensagem": 99,
                        "id_hash_msg": "wamid.bot.existente",
                        "id_etapa": 1,
                    }
                )
            )

        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.existente")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_etapa_1_repassa_retorno_do_sender_etapa1(self):
        chamadas = []

        def fake_sender_etapa1(cliente_telefone, phone_id_unidade):
            chamadas.append((cliente_telefone, phone_id_unidade))
            return {
                "enviou": True,
                "resposta_ja_existia": False,
                "mensagem_bot": "Ola!",
                "id_hash_msg_bot": "wamid.bot",
                "id_etapa_resultante": 1,
                "tipo_mensagem": "interactive_button",
            }

        with patch.object(flow_sender_module, "sender_etapa1", fake_sender_etapa1):
            resultado = flow_sender_module.flow_sender(contexto_historico_base())

        self.assertEqual(chamadas, [("5571999999999", "123456")])
        self.assertTrue(resultado["enviou"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot")
        self.assertEqual(resultado["tipo_mensagem"], "interactive_button")

    def test_etapa_nao_implementada_nao_finge_sucesso(self):
        with self.assertRaises(NotImplementedError):
            flow_sender_module.flow_sender(contexto_historico_base(etapa=2))


if __name__ == "__main__":
    unittest.main()
