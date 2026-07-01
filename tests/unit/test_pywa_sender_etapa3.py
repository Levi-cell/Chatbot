import unittest
from types import SimpleNamespace
from unittest.mock import patch

from core.integrations.whatsapp.exceptions import ErroEnvioMeta
from core.integrations.whatsapp.messages.etapa3_messages import (
    montar_mensagem_contexto_nome_invalido_etapa3,
    montar_mensagem_etapa3,
    montar_mensagem_financeiro_etapa3,
    montar_mensagem_midia_etapa3,
)
from core.integrations.whatsapp.pywa_functions.pywa_senders import (
    etapa3 as sender_module,
)


class FakeClienteWa:
    def __init__(self, erro=None):
        self.calls = []
        self.erro = erro

    def send_message(self, **kwargs):
        self.calls.append(kwargs)
        if self.erro:
            raise self.erro
        return SimpleNamespace(id="wamid.bot.3")


class PywaSenderEtapa3Tests(unittest.TestCase):
    def test_enviar_etapa3_pergunta_nome_do_dependente(self):
        cliente_wa = FakeClienteWa()

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            resultado = sender_module.enviar_etapa3(
                "5571999999999",
                "123456",
            )

        self.assertEqual(cliente_wa.calls[0]["to"], "5571999999999")
        self.assertEqual(
            cliente_wa.calls[0]["text"],
            montar_mensagem_etapa3(),
        )
        self.assertEqual(resultado["id_hash_msg_bot"], "wamid.bot.3")
        self.assertEqual(resultado["id_etapa_resultante"], 3)
        self.assertEqual(resultado["tipo_mensagem"], "text")
        self.assertNotIn("tratamento", resultado)

    def test_tratamentos_da_etapa3_preservam_a_etapa(self):
        casos = (
            (
                sender_module.enviar_etapa3_midia,
                montar_mensagem_midia_etapa3(),
                sender_module.TIPO_TRATAMENTO_MIDIA,
            ),
            (
                sender_module.enviar_etapa3_financeiro,
                montar_mensagem_financeiro_etapa3(),
                sender_module.TIPO_TRATAMENTO_FINANCEIRO,
            ),
            (
                sender_module.enviar_etapa3_contexto_nome_invalido,
                montar_mensagem_contexto_nome_invalido_etapa3(),
                sender_module.TIPO_TRATAMENTO_NOME_INVALIDO,
            ),
        )

        for funcao, mensagem, tipo_tratamento in casos:
            with self.subTest(funcao=funcao.__name__):
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

                self.assertEqual(cliente_wa.calls[0]["text"], mensagem)
                self.assertEqual(resultado["id_etapa_resultante"], 3)
                self.assertTrue(resultado["tratamento"])
                self.assertEqual(
                    resultado["tipo_tratamento"],
                    tipo_tratamento,
                )

    def test_meta_falhou_levanta_exception_controlada(self):
        cliente_wa = FakeClienteWa(
            erro=RuntimeError("meta indisponivel")
        )

        with patch.object(
            sender_module,
            "conta_wa",
            return_value=cliente_wa,
        ):
            with self.assertRaises(ErroEnvioMeta) as ctx:
                sender_module.enviar_etapa3(
                    "5571999999999",
                    "123456",
                )

        self.assertEqual(ctx.exception.id_etapa, 3)
        self.assertEqual(ctx.exception.cliente_telefone, "5571999999999")
        self.assertEqual(ctx.exception.phone_id_unidade, "123456")


if __name__ == "__main__":
    unittest.main()
