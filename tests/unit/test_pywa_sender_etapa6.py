import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa6_messages import (
    montar_mensagem_oferta_adiada_etapa6,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa6 as sender_module,
)


class FakeClienteWa:
    def __init__(self, resposta=None, erro=None):
        self.calls = []
        self.resposta = resposta or SimpleNamespace(id="wamid.bot.6")
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return self.resposta


class PywaSenderEtapa6Tests(unittest.TestCase):
    def test_enviar_etapa6_usa_link_e_retorna_contexto(self):
        cliente_wa = FakeClienteWa()
        link = "https://instagram.com/supera.saj/"

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = sender_module.enviar_etapa6(
                "5571999999999",
                "123456",
                link,
            )

        self.assertEqual(cliente_wa.calls[0]["to"], "5571999999999")
        self.assertEqual(
            cliente_wa.calls[0]["text"],
            montar_mensagem_oferta_adiada_etapa6(link),
        )
        self.assertNotIn("buttons", cliente_wa.calls[0])
        self.assertTrue(resultado["enviou"])
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.6")
        self.assertEqual(resultado["id_etapa_resultante"], 6)
        self.assertEqual(resultado["tipo_mensagem"], "text")
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
                sender_module.enviar_etapa6(
                    "5571999999999",
                    "123456",
                    "https://instagram.com/supera.saj/",
                )

        self.assertEqual(contexto.exception.id_etapa, 6)
        self.assertEqual(
            contexto.exception.cliente_telefone,
            "5571999999999",
        )


if __name__ == "__main__":
    unittest.main()
