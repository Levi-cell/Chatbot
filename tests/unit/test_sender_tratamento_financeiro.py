import unittest
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.tratamentos import (
    MENSAGEM_FINANCEIRO_ETAPA_1,
    MENSAGEM_FINANCEIRO_INICIO,
)
from core.integrations.whatsapp.pywa_functions import (
    tratamentos_financeiros as sender_tratamento_module,
)


class SenderTratamentoFinanceiroTests(unittest.TestCase):
    def test_sender_financeiro_em_conversa_nova_reapresenta_etapa_1(self):
        chamadas = []

        def fake_enviar_mensagem_texto(**kwargs):
            chamadas.append(kwargs)
            return "wamid.bot.financeiro"

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto",
            fake_enviar_mensagem_texto,
        ), patch.object(
            sender_tratamento_module,
            "obter_saudacao_por_horario",
            return_value="Bom dia",
        ):
            resultado = sender_tratamento_module.sender_tratamento_financeiro(
                cliente_telefone="5571999999999",
                phone_id_unidade="123456",
                id_etapa=1,
                conversa_nova=True,
            )

        mensagem_esperada = MENSAGEM_FINANCEIRO_INICIO.format(saudacao="Bom dia")

        self.assertEqual(len(chamadas), 1)
        self.assertEqual(chamadas[0]["to"], "5571999999999")
        self.assertEqual(chamadas[0]["phone_id_unidade"], "123456")
        self.assertEqual(chamadas[0]["text"], mensagem_esperada)
        self.assertIsNone(chamadas[0].get("botoes"))
        self.assertTrue(resultado["enviou"])
        self.assertTrue(resultado["tratamento"])
        self.assertTrue(resultado["atualizar_conversa"])
        self.assertEqual(resultado["tipo_tratamento"], "pergunta_financeira")
        self.assertEqual(resultado["tipo_mensagem"], "text")
        self.assertEqual(resultado["id_etapa_resultante"], 1)

    def test_sender_financeiro_em_etapa_1_reapresenta_pergunta_nome(self):
        chamadas = []

        def fake_enviar_mensagem_texto(**kwargs):
            chamadas.append(kwargs)
            return "wamid.bot.financeiro"

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto",
            fake_enviar_mensagem_texto,
        ):
            resultado = sender_tratamento_module.sender_tratamento_financeiro(
                cliente_telefone="5571999999999",
                phone_id_unidade="123456",
                id_etapa=1,
                conversa_nova=False,
            )

        self.assertEqual(chamadas[0]["text"], MENSAGEM_FINANCEIRO_ETAPA_1)
        self.assertTrue(resultado["atualizar_conversa"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.financeiro")

    def test_sender_financeiro_falha_meta_levanta_exception_controlada(self):
        def fake_falha(**_kwargs):
            raise RuntimeError("meta indisponivel")

        with patch.object(
            sender_tratamento_module,
            "enviar_mensagem_texto",
            fake_falha,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_tratamento_module.sender_tratamento_financeiro(
                    cliente_telefone="5571999999999",
                    phone_id_unidade="123456",
                    id_etapa=1,
                    conversa_nova=False,
                )

        self.assertEqual(ctx.exception.id_etapa, 1)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
