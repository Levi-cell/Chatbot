import unittest
from unittest.mock import patch

import workers.worker_flow.response_flow.flow_sender as flow_sender_module
from workers.worker_flow.response_flow.transicoes.eventos import (
    EVENTO_PARA_MIM,
    EVENTO_PARA_OUTRA_PESSOA,
)


def contexto_base(
    *,
    etapa_atual=1,
    retry=1,
    resposta_bot=None,
    transicoes=None,
):
    etapa_origem = etapa_atual if etapa_atual is not None else 1
    return {
        "id_conversa": 10,
        "id_etapa_atual": etapa_atual,
        "id_etapa_cliente": etapa_origem,
        "id_etapa_resposta": None,
        "id_etapa_origem_transicao": etapa_origem,
        "transicoes_permitidas": transicoes or {"evento_teste": 2},
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


class RoteamentoEssencialTests(unittest.TestCase):
    def test_resposta_ja_existente_impede_novo_envio(self):
        with patch.object(flow_sender_module, "resolve_etapa4") as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_base(
                    etapa_atual=4,
                    retry=2,
                    resposta_bot={
                        "id_mensagem": 99,
                        "id_hash_msg": "wamid.bot.existente",
                        "id_etapa": 4,
                    },
                    transicoes={
                        EVENTO_PARA_MIM: 4,
                        EVENTO_PARA_OUTRA_PESSOA: 3,
                    },
                )
            )

        resolver.assert_not_called()
        self.assertFalse(resultado["enviou"])
        self.assertTrue(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["evento_transicao"], EVENTO_PARA_MIM)

    def test_retry_sem_resposta_existente_continua_no_resolver(self):
        esperado = {
            "enviou": True,
            "id_hash_msg_bot": "wamid.bot",
            "id_etapa_resultante": 2,
        }

        with patch.object(
            flow_sender_module,
            "resolve_etapa2",
            return_value=esperado,
        ) as resolver:
            resultado = flow_sender_module.flow_sender(
                contexto_base(etapa_atual=2, retry=2)
            )

        resolver.assert_called_once()
        self.assertEqual(resultado, esperado)

    def test_cada_etapa_implementada_chama_seu_resolver(self):
        for etapa_atual in (None, *range(1, 16)):
            etapa_resolver = 1 if etapa_atual is None else etapa_atual
            esperado = {
                "enviou": True,
                "id_hash_msg_bot": f"wamid.etapa{etapa_resolver}",
                "id_etapa_resultante": etapa_resolver,
            }

            with self.subTest(etapa=etapa_atual), patch.object(
                flow_sender_module,
                f"resolve_etapa{etapa_resolver}",
                return_value=esperado,
            ) as resolver:
                resultado = flow_sender_module.flow_sender(
                    contexto_base(etapa_atual=etapa_atual)
                )

            resolver.assert_called_once()
            self.assertEqual(resultado, esperado)


if __name__ == "__main__":
    unittest.main()
