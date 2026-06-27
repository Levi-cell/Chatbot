import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.flow_sender as flow_sender_module


def contexto_historico_base(
    resposta_bot=None,
    etapa_atual=None,
    etapa_resposta=1,
    retry=1,
):
    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": 1,
        "id_etapa_resposta": etapa_resposta,
        "retry_count": retry,
        "texto_cliente_atual": "Ola",
        "tipo_mensagem_atual": "text",
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
            "cliente_telefone": "5571999999999",
            "id_phone_unidade": "123456",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


class FlowSenderTests(unittest.TestCase):
    def test_idempotente_nao_chama_primeira_etapa_quando_resposta_ja_existe(self):
        def falhar_se_chamar(*_args, **_kwargs):
            raise AssertionError("primeira etapa nao deveria ser chamada")

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            falhar_se_chamar,
        ):
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

    def test_conversa_sem_etapa_vai_para_primeira_etapa(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=None)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_um_vai_para_primeira_etapa(self):
        esperado = {
            "enviou": True,
            "resposta_ja_existia": False,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 1,
        }

        with patch.object(
            flow_sender_module,
            "resolve_primeira_etapa",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=1, etapa_resposta=2)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_etapa_nao_implementada_nao_finge_sucesso(self):
        with self.assertRaises(NotImplementedError):
            flow_sender_module.flow_sender(
                contexto_historico_base(etapa_atual=2, etapa_resposta=3)
            )


if __name__ == "__main__":
    unittest.main()
