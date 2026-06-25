import unittest
from unittest.mock import patch

from workers.worker_flow.response_flow import flow_treat_unsupported_type as flow_treat_unsupported_type_module


def contexto_historico_base(resposta_bot=None, id_etapa_atual=1):
    return {
        "id_conversa": 10,
        "retry_count": 1,
        "id_etapa_atual": id_etapa_atual,
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
        "resultado": "tipo_mensagem_nao_suportado",
        "tipo_tratamento": "tipo_mensagem_nao_suportado",
        "tipo_mensagem": "image",
    }


class FlowTreatUnsupportedTypeTests(unittest.TestCase):
    def test_idempotente_nao_envia_meta_quando_resposta_ja_existe(self):
        def falhar_se_chamar(*_args, **_kwargs):
            raise AssertionError("sender_tratamento nao deveria ser chamado")

        with patch.object(
            flow_treat_unsupported_type_module,
            "sender_tratamento_tipo_nao_suportado",
            falhar_se_chamar,
        ):
            resultado = flow_treat_unsupported_type_module.flow_treat_unsupported_type(
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
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])

    def test_tipo_nao_suportado_chama_sender_de_tratamento(self):
        chamadas = []

        def fake_sender(
            cliente_telefone,
            phone_id_unidade,
            id_etapa,
            tipo_mensagem,
            conversa_nova,
        ):
            chamadas.append((
                cliente_telefone,
                phone_id_unidade,
                id_etapa,
                tipo_mensagem,
                conversa_nova,
            ))
            return {
                "enviou": True,
                "resposta_ja_existia": False,
                "mensagem_bot": "mensagem de tratamento",
                "id_hash_msg_bot": "wamid.bot.tratamento",
                "id_etapa_resultante": id_etapa,
                "tipo_mensagem": "text",
                "tratamento": True,
                "tipo_tratamento": "tipo_mensagem_nao_suportado",
                "atualizar_conversa": conversa_nova,
            }

        with patch.object(
            flow_treat_unsupported_type_module,
            "sender_tratamento_tipo_nao_suportado",
            fake_sender,
        ):
            resultado = flow_treat_unsupported_type_module.flow_treat_unsupported_type(
                contexto_historico_base(),
                contexto_validacao_base(),
            )

        self.assertEqual(
            chamadas,
            [("5571999999999", "123456", 1, "image", False)],
        )
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])

    def test_tipo_nao_suportado_em_conversa_nova_usa_mensagem_de_inicio(self):
        chamadas = []

        def fake_sender(
            cliente_telefone,
            phone_id_unidade,
            id_etapa,
            tipo_mensagem,
            conversa_nova,
        ):
            chamadas.append(conversa_nova)
            return {
                "enviou": True,
                "resposta_ja_existia": False,
                "mensagem_bot": "mensagem inicial",
                "id_hash_msg_bot": "wamid.bot.tratamento",
                "id_etapa_resultante": id_etapa,
                "tipo_mensagem": "text",
                "tratamento": True,
                "tipo_tratamento": "tipo_mensagem_nao_suportado",
                "atualizar_conversa": conversa_nova,
            }

        with patch.object(
            flow_treat_unsupported_type_module,
            "sender_tratamento_tipo_nao_suportado",
            fake_sender,
        ):
            resultado = flow_treat_unsupported_type_module.flow_treat_unsupported_type(
                contexto_historico_base(id_etapa_atual=None),
                contexto_validacao_base(),
            )

        self.assertEqual(chamadas, [True])
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertTrue(resultado["atualizar_conversa"])


if __name__ == "__main__":
    unittest.main()
