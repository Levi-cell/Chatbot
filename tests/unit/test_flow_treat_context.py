import unittest

from workers.worker_flow.response_flow.flow_treat_context import flow_treat_context
from workers.worker_flow.valida_resposta_cliente import (
    RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
)


def contexto_historico_base(resposta_bot=None):
    return {
        "id_conversa": 10,
        "retry_count": 2,
        "id_etapa_cliente": 1,
        "mensagem_cliente_atual": {
            "id_mensagem_fila": 20,
            "id_hash_msg": "wamid.cliente",
        },
        "resposta_bot_para_mensagem_atual": resposta_bot,
    }


def contexto_validacao_base():
    return {
        "resultado": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
        "tipo_tratamento": RESULTADO_MENSAGEM_FORA_DE_CONTEXTO,
    }


class FlowTreatContextTests(unittest.TestCase):
    def test_idempotente_nao_envia_meta_quando_resposta_ja_existe(self):
        resultado = flow_treat_context(
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
        self.assertFalse(resultado["atualizar_conversa"])

    def test_sem_resposta_existente_ainda_nao_implementado(self):
        with self.assertRaises(NotImplementedError):
            flow_treat_context(
                contexto_historico_base(),
                contexto_validacao_base(),
            )


if __name__ == "__main__":
    unittest.main()
