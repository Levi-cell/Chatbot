import unittest
from unittest.mock import patch

from core.integrations.whatsapp import sender as sender_module
from core.integrations.whatsapp.exceptions import ErroEnvioMeta


class SenderEtapa1Tests(unittest.TestCase):
    def test_retorna_contexto_quando_meta_envia_botao(self):
        chamadas = []

        def fake_enviar_mensagem_texto_com_botao(
            to,
            text,
            titulo_botao,
            phone_id_unidade,
        ):
            chamadas.append((to, text, titulo_botao, phone_id_unidade))
            return "wamid.bot.1"

        with patch.object(
            sender_module,
            "enviar_mensagem_texto_com_botao",
            fake_enviar_mensagem_texto_com_botao,
        ):
            resultado = sender_module.sender_etapa1("5571999999999", "123456")

        self.assertEqual(
            chamadas,
            [("5571999999999", "Ola!", "Aperte em mim", "123456")],
        )
        self.assertTrue(resultado["enviou"])
        self.assertFalse(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["mensagem_bot"], "Ola!")
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.1")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertEqual(resultado["tipo_mensagem"], "interactive_button")

    def test_meta_falhou_levanta_exception_controlada(self):
        def fake_falha(*_args, **_kwargs):
            raise RuntimeError("meta indisponivel")

        with patch.object(
            sender_module,
            "enviar_mensagem_texto_com_botao",
            fake_falha,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.sender_etapa1("5571999999999", "123456")

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
