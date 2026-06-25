import unittest
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.tratamentos import (
    MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1,
)
from core.integrations.whatsapp.pywa_functions import (
    tratamentos_context as sender_tratamento_module,
)


class SenderTratamentoContextTests(unittest.TestCase):
    def test_sender_nome_invalido_reapresenta_pergunta_nome(self):
        chamadas = []

        def fake_enviar_mensagem_texto(**kwargs):
            chamadas.append(kwargs)
            return "wamid.bot.contexto"

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto",
            fake_enviar_mensagem_texto,
        ):
            resultado = (
                sender_tratamento_module.sender_tratamento_contexto_nome_invalido(
                    cliente_telefone="5571999999999",
                    phone_id_unidade="123456",
                    id_etapa=1,
                )
            )

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["to"], "5571999999999")
        self.assertEqual(chamadas[0]["phone_id_unidade"], "123456")
        self.assertEqual(chamadas[0]["text"], MENSAGEM_CONTEXTO_NOME_INVALIDO_ETAPA_1)
        self.assertIsNone(chamadas[0].get("botoes"))
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertTrue(resultado["atualizar_conversa"])
        self.assertEqual(resultado["tipo_tratamento"], "nome_invalido")
        self.assertEqual(resultado["tipo_mensagem"], "text")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_sender_nome_invalido_falha_meta_levanta_exception_controlada(self):
        def fake_falha(**_kwargs):
            raise RuntimeError("meta indisponivel")

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto",
            fake_falha,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_tratamento_module.sender_tratamento_contexto_nome_invalido(
                    cliente_telefone="5571999999999",
                    phone_id_unidade="123456",
                    id_etapa=1,
                )

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
