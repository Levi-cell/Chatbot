import unittest
from datetime import datetime
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapas import montar_mensagem_etapa_1
from core.integrations.whatsapp.pywa_functions import etapas as sender_module


class SenderEtapa1Tests(unittest.TestCase):
    def test_retorna_contexto_quando_meta_envia_botao_com_saudacao_por_horario(self):
        chamadas = []

        def fake_enviar_mensagem_texto(**kwargs):
            chamadas.append(kwargs)
            return "wamid.bot.1"

        with patch.object(
            sender_module,
            "enviar_mensagem_texto",
            fake_enviar_mensagem_texto,
        ), patch.object(
            sender_module,
            "obter_saudacao_por_horario",
            return_value="Boa tarde",
        ):
            resultado = sender_module.sender_etapa1("5571999999999", "123456")

        mensagem_esperada = montar_mensagem_etapa_1("Boa tarde")

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["to"], "5571999999999")
        self.assertEqual(chamadas[0]["phone_id_unidade"], "123456")
        self.assertEqual(chamadas[0]["text"], mensagem_esperada)
        self.assertEqual(
            chamadas[0]["botoes"],
            [
                {
                    "titulo": "Aperte em mim",
                    "callback_data": "Aperte em mim",
                }
            ],
        )
        self.assertTrue(resultado["enviou"])
        self.assertFalse(resultado["resposta_ja_existia"])
        self.assertEqual(resultado["mensagem_bot"], mensagem_esperada)
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.1")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertEqual(resultado["tipo_mensagem"], "interactive_button")

    def test_saudacao_por_horario(self):
        self.assertEqual(
            sender_module.obter_saudacao_por_horario(datetime(2026, 1, 1, 8)),
            "Bom dia",
        )
        self.assertEqual(
            sender_module.obter_saudacao_por_horario(datetime(2026, 1, 1, 14)),
            "Boa tarde",
        )
        self.assertEqual(
            sender_module.obter_saudacao_por_horario(datetime(2026, 1, 1, 22)),
            "Boa noite",
        )

    def test_meta_falhou_levanta_exception_controlada(self):
        def fake_falha(**_kwargs):
            raise RuntimeError("meta indisponivel")

        with patch.object(
            sender_module,
            "enviar_mensagem_texto",
            fake_falha,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.sender_etapa1("5571999999999", "123456")

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
