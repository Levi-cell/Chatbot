import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa8_messages import (
    montar_mensagem_contexto_email_invalido_etapa8,
    montar_mensagem_email_etapa8,
    montar_mensagem_email_etapa8_financeiro,
    montar_mensagem_email_etapa8_midia,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa8 as sender_module,
)


class FakeClienteWa:
    def __init__(self, erro=None):
        self.calls = []
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return SimpleNamespace(id="wamid.bot.8")


class PywaSenderEtapa8Tests(unittest.TestCase):
    def _executar(self, funcao):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = funcao(
                "5571999999999",
                "123456",
            )

        return cliente_wa.calls[0], resultado

    def test_quatro_senders_usam_mensagem_e_contexto_corretos(self):
        casos = (
            (
                sender_module.enviar_etapa8,
                montar_mensagem_email_etapa8(),
                None,
            ),
            (
                sender_module.enviar_etapa8_midia,
                montar_mensagem_email_etapa8_midia(),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa8_financeiro,
                montar_mensagem_email_etapa8_financeiro(),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa8_contexto_email_invalido,
                montar_mensagem_contexto_email_invalido_etapa8(),
                sender_module.TIPO_TRATAMENTO_EMAIL_INVALIDO,
            ),
        )

        for funcao, mensagem, tratamento in casos:
            with self.subTest(funcao=funcao.__name__):
                chamada, resultado = self._executar(funcao)

                self.assertEqual(chamada["text"], mensagem)
                self.assertNotIn("buttons", chamada)
                self.assertEqual(resultado["id_etapa_resultante"], 8)
                self.assertEqual(resultado["tipo_mensagem"], "text")

                if tratamento:
                    self.assertTrue(resultado["tratamento"])
                    self.assertEqual(
                        resultado["tipo_tratamento"],
                        tratamento,
                    )
                else:
                    self.assertNotIn("tratamento", resultado)

    def test_meta_falhou_levanta_exception_controlada(self):
        cliente_wa = FakeClienteWa(
            erro=RuntimeError("meta indisponivel")
        )

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as contexto:
                sender_module.enviar_etapa8(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(contexto.exception.id_etapa, 8)


if __name__ == "__main__":
    unittest.main()
