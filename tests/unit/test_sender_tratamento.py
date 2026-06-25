import unittest
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.tratamentos import (
    MENSAGEM_MIDIA_ETAPA_1,
    MENSAGEM_MIDIA_INICIO,
)
from core.integrations.whatsapp.pywa_functions import (
    tratamentos_type as sender_tratamento_module,
)


class SenderTratamentoTests(unittest.TestCase):
    def test_sender_tipo_nao_suportado_retorna_contexto_sem_avancar_conversa(self):
        chamadas = []

        def fake_enviar_mensagem_texto(**kwargs):
            chamadas.append(kwargs)
            return "wamid.bot.tratamento"

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto",
            fake_enviar_mensagem_texto,
        ):
            resultado = sender_tratamento_module.sender_tratamento_tipo_nao_suportado(
                cliente_telefone="5571999999999",
                phone_id_unidade="123456",
                id_etapa=1,
                tipo_mensagem="image",
                conversa_nova=False,
            )

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["to"], "5571999999999")
        self.assertEqual(chamadas[0]["phone_id_unidade"], "123456")
        self.assertEqual(chamadas[0]["text"], MENSAGEM_MIDIA_ETAPA_1)
        self.assertIsNone(chamadas[0].get("botoes"))
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertFalse(resultado["atualizar_conversa"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.tratamento")
        self.assertEqual(resultado["id_etapa_resultante"], 1)
        self.assertEqual(resultado["tipo_mensagem"], "text")

    def test_sender_tipo_nao_suportado_em_conversa_nova_usa_mensagem_inicial(self):
        chamadas = []

        def fake_enviar(**kwargs):
            chamadas.append(kwargs["text"])
            return "wamid.bot.inicio"

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto",
            fake_enviar,
        ), patch.object(
            sender_tratamento_module,
            "obter_saudacao_por_horario",
            return_value="Boa noite",
        ):
            resultado = sender_tratamento_module.sender_tratamento_tipo_nao_suportado(
                cliente_telefone="5571999999999",
                phone_id_unidade="123456",
                id_etapa=1,
                tipo_mensagem="image",
                conversa_nova=True,
            )

        mensagem_esperada = MENSAGEM_MIDIA_INICIO.format(saudacao="Boa noite")

        self.assertEqual(chamadas, [mensagem_esperada])
        self.assertEqual(resultado["mensagem_bot"], mensagem_esperada)
        self.assertTrue(resultado["atualizar_conversa"])

    def test_sender_tipo_nao_suportado_falha_meta_levanta_exception_controlada(self):
        def fake_falha(**_kwargs):
            raise RuntimeError("meta indisponivel")

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto",
            fake_falha,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_tratamento_module.sender_tratamento_tipo_nao_suportado(
                    cliente_telefone="5571999999999",
                    phone_id_unidade="123456",
                    id_etapa=1,
                    tipo_mensagem="image",
                    conversa_nova=False,
                )

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
