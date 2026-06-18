import unittest
from unittest.mock import patch

from core.integrations.whatsapp import sender_tratamento as sender_tratamento_module
from core.integrations.whatsapp.exceptions import ErroEnvioMeta


class SenderTratamentoTests(unittest.TestCase):
    def test_sender_tipo_nao_suportado_retorna_contexto_sem_avancar_conversa(self):
        chamadas = []

        def fake_enviar_mensagem_texto_com_botao(
            to,
            text,
            titulo_botao,
            phone_id_unidade,
            callback_data=None,
        ):
            chamadas.append((to, text, titulo_botao, phone_id_unidade, callback_data))
            return "wamid.bot.tratamento"

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto_com_botao",
            fake_enviar_mensagem_texto_com_botao,
        ):
            resultado = sender_tratamento_module.sender_tratamento_tipo_nao_suportado(
                cliente_telefone="5571999999999",
                phone_id_unidade="123456",
                id_etapa=1,
                tipo_mensagem="image",
                mensagem_bot="Recebi uma midia. Envie texto para continuarmos.",
            )

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0][0], "5571999999999")
        self.assertEqual(chamadas[0][2], "Continuar")
        self.assertLessEqual(len(chamadas[0][2]), 20)
        self.assertEqual(chamadas[0][3], "123456")
        self.assertEqual(chamadas[0][4], "retornar_atendimento")
        self.assertEqual(chamadas[0][1], "Recebi uma midia. Envie texto para continuarmos.")
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.tratamento")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_sender_tipo_nao_suportado_falha_meta_levanta_exception_controlada(self):
        def fake_falha(*_args, **_kwargs):
            raise RuntimeError("meta indisponivel")

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto_com_botao",
            fake_falha,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_tratamento_module.sender_tratamento_tipo_nao_suportado(
                    cliente_telefone="5571999999999",
                    phone_id_unidade="123456",
                    id_etapa=1,
                    tipo_mensagem="image",
                    mensagem_bot="Recebi uma midia. Envie texto para continuarmos.",
                )

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
